import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from django.db import transaction

from .models import OCRRequest, ExtractedData
from .serializers import (
    OCRInputSerializer,
    OCRBatchInputSerializer,
    OCRResponseSerializer,
)
from .services.model_service import ModelService

logger = logging.getLogger(__name__)

class OCRProcessView(APIView):
    """
    Endpoint para procesar un solo texto OCR
    """
    @swagger_auto_schema(
        request_body=OCRInputSerializer,
        responses={200: OCRResponseSerializer}
    )
    def post(self, request):
        """
        Procesa un texto OCR y extrae información relevante.
        
        Recibe un texto OCR con su identificador y devuelve la información extraída.
        """
        serializer = OCRInputSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        ocr_id = serializer.validated_data['ocr_id']
        text_content = serializer.validated_data['text_content']
        
        try:
            # Procesar con el modelo
            model_service = ModelService()
            extraction_result = model_service.process_text(text_content)
            
            # Guardar solicitud y resultado en la base de datos
            with transaction.atomic():
                ocr_request = OCRRequest.objects.create(
                    ocr_id=ocr_id,
                    text_content=text_content
                )
                
                ExtractedData.objects.create(
                    ocr_request=ocr_request,
                    company=extraction_result.get('company'),
                    invoice_number=extraction_result.get('invoice_number'),
                    invoice_date=extraction_result.get('invoice_date'),
                    raw_json=extraction_result.get('raw_data')
                )
            
            # Preparar respuesta
            response_data = {
                'ocr_id': ocr_id,
                'company': extraction_result.get('company'),
                'invoice_number': extraction_result.get('invoice_number'),
                'invoice_date': extraction_result.get('invoice_date'),
                'raw_data': extraction_result.get('raw_data')
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error al procesar OCR {ocr_id}: {str(e)}")
            return Response(
                {'error': f'Error al procesar la solicitud: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OCRBatchProcessView(APIView):
    """
    Endpoint para procesar múltiples textos OCR en lote
    """
    @swagger_auto_schema(
        request_body=OCRBatchInputSerializer,
        responses={200: OCRResponseSerializer(many=True)}
    )
    def post(self, request):
        """
        Procesa múltiples textos OCR y extrae información relevante para cada uno.
        
        Recibe una lista de textos OCR con sus identificadores y devuelve la información
        extraída para cada uno.
        """
        serializer = OCRBatchInputSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        ocr_items = serializer.validated_data['ocr_items']
        model_service = ModelService()
        results = []
        
        try:
            with transaction.atomic():
                for item in ocr_items:
                    ocr_id = item['ocr_id']
                    text_content = item['text_content']
                    
                    # Procesar con el modelo
                    extraction_result = model_service.process_text(text_content)
                    
                    # Guardar solicitud y resultado en la base de datos
                    ocr_request = OCRRequest.objects.create(
                        ocr_id=ocr_id,
                        text_content=text_content
                    )
                    
                    ExtractedData.objects.create(
                        ocr_request=ocr_request,
                        company=extraction_result.get('company'),
                        invoice_number=extraction_result.get('invoice_number'),
                        invoice_date=extraction_result.get('invoice_date'),
                        raw_json=extraction_result.get('raw_data')
                    )
                    
                    # Preparar respuesta
                    results.append({
                        'ocr_id': ocr_id,
                        'company': extraction_result.get('company'),
                        'invoice_number': extraction_result.get('invoice_number'),
                        'invoice_date': extraction_result.get('invoice_date'),
                        'raw_data': extraction_result.get('raw_data')
                    })
            
            return Response(results, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error al procesar OCR en lote: {str(e)}")
            return Response(
                {'error': f'Error al procesar las solicitudes en lote: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ModelReloadView(APIView):
    """
    Endpoint para recargar el modelo
    """
    def post(self, request):
        """
        Recarga el modelo desde la carpeta configurada.
        Útil después de actualizar los archivos del modelo.
        """
        try:
            model_service = ModelService()
            success = model_service.reload_model()
            
            if success:
                return Response(
                    {'message': 'Modelo recargado correctamente'},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': 'Error al recargar el modelo'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error al recargar el modelo: {str(e)}")
            return Response(
                {'error': f'Error al recargar el modelo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )