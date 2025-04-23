from django.db import models
from django.utils import timezone
import os
import uuid

def invoice_file_path(instance, filename):
    """Genera ruta para guardar archivos de facturas organizados por fecha"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('invoices', str(instance.upload_date.year), 
                        str(instance.upload_date.month), filename)

def invoice_page_path(instance, filename):
    """Genera ruta para guardar imágenes extraídas de las facturas"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('invoice_pages', str(instance.invoice.upload_date.year), 
                        str(instance.invoice.upload_date.month), filename)

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
    
    def __str__(self):
        return f"{self.company} - {self.invoice_number}"
    
    class Meta:
        ordering = ['-invoice_date', 'company']