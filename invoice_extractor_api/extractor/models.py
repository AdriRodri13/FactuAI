from django.db import models
from django.utils import timezone

class OCRRequest(models.Model):
    """
    Modelo para almacenar las solicitudes de OCR
    """
    ocr_id = models.CharField(max_length=255, unique=True, help_text="Identificador único del OCR")
    text_content = models.TextField(help_text="Contenido del texto OCR")
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"OCR Request {self.ocr_id}"

class ExtractedData(models.Model):
    """
    Modelo para almacenar los datos extraídos del OCR
    """
    ocr_request = models.OneToOneField(OCRRequest, on_delete=models.CASCADE, related_name='extracted_data')
    company = models.CharField(max_length=255, null=True, blank=True, help_text="Empresa extraída del OCR")
    invoice_number = models.CharField(max_length=100, null=True, blank=True, help_text="Número de factura extraído del OCR")
    invoice_date = models.CharField(max_length=100, null=True, blank=True, help_text="Fecha de factura extraída del OCR")
    raw_json = models.JSONField(null=True, blank=True, help_text="JSON completo extraído del modelo")
    processed_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Extracted Data for {self.ocr_request.ocr_id}"