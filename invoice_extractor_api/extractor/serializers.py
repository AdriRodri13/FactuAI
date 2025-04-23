from rest_framework import serializers
from .models import OCRRequest, ExtractedData

class OCRRequestSerializer(serializers.ModelSerializer):
    """
    Serializador para las solicitudes de OCR
    """
    class Meta:
        model = OCRRequest
        fields = ['ocr_id', 'text_content', 'created_at']
        read_only_fields = ['created_at']

class ExtractedDataSerializer(serializers.ModelSerializer):
    """
    Serializador para los datos extraídos
    """
    class Meta:
        model = ExtractedData
        fields = ['company', 'invoice_number', 'invoice_date', 'raw_json', 'processed_at']
        read_only_fields = ['processed_at']

class OCRInputSerializer(serializers.Serializer):
    """
    Serializador para validar los datos de entrada de la API
    """
    ocr_id = serializers.CharField(max_length=255, required=True, 
                                 help_text="Identificador único del OCR")
    text_content = serializers.CharField(required=True, 
                                       help_text="Contenido del texto OCR")

class OCRBatchInputSerializer(serializers.Serializer):
    """
    Serializador para validar múltiples OCRs en una sola solicitud
    """
    ocr_items = serializers.ListField(
        child=OCRInputSerializer(),
        min_length=1,
        help_text="Lista de ítems OCR para procesar en lote"
    )

class OCRResponseSerializer(serializers.Serializer):
    """
    Serializador para la respuesta de la API
    """
    ocr_id = serializers.CharField(max_length=255, 
                                  help_text="Identificador único del OCR")
    company = serializers.CharField(max_length=255, allow_null=True, 
                                  help_text="Empresa extraída del OCR")
    invoice_number = serializers.CharField(max_length=100, allow_null=True, 
                                         help_text="Número de factura extraído del OCR")
    invoice_date = serializers.CharField(max_length=100, allow_null=True, 
                                       help_text="Fecha de factura extraída del OCR")
    raw_data = serializers.JSONField(allow_null=True, 
                                   help_text="Datos JSON completos extraídos")