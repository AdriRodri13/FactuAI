from django.db import models
from django.utils import timezone
import os
import uuid

def invoice_file_path(instance, filename):
    """Genera ruta para guardar archivos de facturas organizados por fecha"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    
    # Asegurar que usamos el año completo (4 dígitos)
    year = str(instance.upload_date.year)
    month = str(instance.upload_date.month).zfill(2)  # Asegurar formato 01, 02, etc.
    
    return os.path.join('invoices', year, month, filename)

def invoice_page_path(instance, filename):
    """Genera ruta para guardar imágenes extraídas de las facturas"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    
    # Asegurar que usamos el año completo (4 dígitos)
    year = str(instance.invoice.upload_date.year)
    month = str(instance.invoice.upload_date.month).zfill(2)  # Asegurar formato 01, 02, etc.
    
    return os.path.join('invoice_pages', year, month, filename)

# models.py (añadir al final)

class Empresa(models.Model):
    """Modelo para representar empresas emisoras de facturas"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=255, unique=True, help_text="Nombre oficial de la empresa")
    nombre_normalizado = models.CharField(
        max_length=255, 
        unique=True, 
        help_text="Nombre normalizado para búsquedas (sin acentos, minúsculas)",
        db_index=True
    )
    # Posibles nombres detectados para esta empresa (para tener referencia y facilitar coincidencias futuras)
    nombres_detectados = models.JSONField(default=list, blank=True, help_text="Lista de nombres previamente detectados por OCR")
    
    # Datos adicionales que podrían ser útiles
    nif = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['nombre']
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
    
    def __str__(self):
        return self.nombre
    
    def save(self, *args, **kwargs):
        """Normalizar nombre al guardar"""
        import unicodedata
        
        # Normalizar a minúsculas y sin acentos
        if self.nombre and not self.nombre_normalizado:
            nombre_norm = self.nombre.lower()
            # Eliminar acentos
            nombre_norm = unicodedata.normalize('NFKD', nombre_norm).encode('ASCII', 'ignore').decode('utf-8')
            self.nombre_normalizado = nombre_norm
            
        super().save(*args, **kwargs)
    
    def add_nombre_detectado(self, nombre):
        """Agrega un nombre detectado si no existe ya"""
        if not self.nombres_detectados:
            self.nombres_detectados = []
            
        # Convertir a lista si es necesario (por si acaso)
        if isinstance(self.nombres_detectados, str):
            import json
            self.nombres_detectados = json.loads(self.nombres_detectados)
            
        # Solo agregar si no existe
        if nombre and nombre not in self.nombres_detectados:
            self.nombres_detectados.append(nombre)
            self.save()
            return True
        return False
    
    @classmethod
    def buscar_por_nombre(cls, nombre_busqueda):
        """
        Busca empresas que coincidan con el nombre proporcionado
        Primero busca coincidencias exactas, luego por normalización, luego en nombres detectados
        """
        import unicodedata
        
        # Normalizar nombre de búsqueda
        nombre_norm = nombre_busqueda.lower()
        nombre_norm = unicodedata.normalize('NFKD', nombre_norm).encode('ASCII', 'ignore').decode('utf-8')
        
        # Intentar buscar coincidencia exacta primero
        try:
            return cls.objects.get(nombre__iexact=nombre_busqueda)
        except cls.DoesNotExist:
            pass
        
        # Intentar buscar por nombre normalizado
        try:
            return cls.objects.get(nombre_normalizado__iexact=nombre_norm)
        except cls.DoesNotExist:
            pass
        
        # Buscar en nombres detectados (esto requerirá revisar cada empresa)
        empresas = cls.objects.all()
        for empresa in empresas:
            if empresa.nombres_detectados and nombre_busqueda in empresa.nombres_detectados:
                return empresa
        
        # No se encontró coincidencia
        return None

class InvoiceDocument(models.Model):
    """Modelo para documentos originales subidos por el usuario"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=invoice_file_path)
    file_type = models.CharField(max_length=10)  # pdf, jpg, png, zip, rar
    upload_date = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.original_filename
    
    class Meta:
        ordering = ['-upload_date']
        
class InvoiceGroup(models.Model):
    """Modelo para agrupar varias páginas/extractos de la misma factura"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Cambiar a ForeignKey a Empresa, manteniendo el campo company para compatibilidad
    empresa = models.ForeignKey(
        'Empresa', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='facturas'
    )
    company = models.CharField(max_length=255, help_text="Nombre detectado originalmente (para compatibilidad)")
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    necesita_revision = models.BooleanField(
        default=False, 
        help_text="Indica si esta factura necesita revisión manual de la empresa"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Cambiamos unique_together para usar empresa en vez de company
        unique_together = ('empresa', 'invoice_number')
        ordering = ['-invoice_date', 'company']
    
    def __str__(self):
        empresa_nombre = self.empresa.nombre if self.empresa else self.company
        return f"{empresa_nombre} - {self.invoice_number}"
    
    @property
    def pages_count(self):
        """Retorna el número de páginas en esta factura"""
        return self.extracted_invoices.count()
    
    @property
    def first_page(self):
        """Retorna la primera página de la factura para vista previa"""
        return self.extracted_invoices.order_by('page__page_number').first()
    
    @property
    def document(self):
        """Retorna el documento original relacionado con esta factura"""
        first_page = self.first_page
        if first_page:
            return first_page.page.invoice
        return None

class InvoicePage(models.Model):
    """Modelo para páginas individuales extraídas de documentos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(InvoiceDocument, related_name='pages', on_delete=models.CASCADE)
    page_number = models.IntegerField()
    image = models.ImageField(upload_to=invoice_page_path)
    ocr_text = models.TextField(blank=True, null=True)
    processed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['invoice', 'page_number']
        unique_together = ('invoice', 'page_number')

class ExtractedInvoice(models.Model):
    """Modelo para información extraída de facturas procesadas por la API"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.OneToOneField(InvoicePage, related_name='extracted_data', on_delete=models.CASCADE)
    company = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    raw_data = models.JSONField()  # Para guardar todos los datos obtenidos de la API
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    group = models.ForeignKey(
        InvoiceGroup, 
        related_name='extracted_invoices', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    def __str__(self):
        return f"{self.company} - {self.invoice_number}"
    
    class Meta:
        ordering = ['-invoice_date', 'company']
        
