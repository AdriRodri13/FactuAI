from rest_framework import serializers

class OCRInputSerializer(serializers.Serializer):
    """
    Serializador para los datos de entrada del OCR.
    """
    texto_ocr = serializers.CharField(required=True, help_text="Texto extraído mediante OCR")
