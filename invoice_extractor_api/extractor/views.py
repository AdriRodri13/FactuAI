import logging
import time
import traceback
import torch
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from django.db import transaction
from django.conf import settings

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
        start_time = time.time()
        serializer = OCRInputSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        ocr_id = serializer.validated_data['ocr_id']
        text_content = serializer.validated_data['text_content']
        
        try:
            # Procesar con el modelo
            model_service = ModelService()
            
            # Verificar si el modelo está disponible
            if model_service.model is None or model_service.tokenizer is None:
                logger.error(f"Modelo o tokenizador no disponible para OCR {ocr_id}")
                return Response(
                    {
                        'ocr_id': ocr_id,
                        'company': None,
                        'invoice_number': None,
                        'invoice_date': None,
                        'raw_data': {'error': 'Modelo no disponible', 'details': 'El modelo no se cargó correctamente'}
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Verificar si ya existe este OCR_ID para evitar duplicados
            try:
                existing_request = OCRRequest.objects.get(ocr_id=ocr_id)
                # Si existe y está configurado para actualizar, actualizar el contenido
                if getattr(settings, 'UPDATE_EXISTING_OCR', False):
                    existing_request.text_content = text_content
                    existing_request.save()
                    
                    # Obtener los datos extraídos existentes o crear nuevos
                    try:
                        extracted_data = ExtractedData.objects.get(ocr_request=existing_request)
                        # Procesar de nuevo el texto
                        extraction_result = model_service.process_text(text_content)
                        
                        # Actualizar los campos
                        extracted_data.company = extraction_result.get('company')
                        extracted_data.invoice_number = extraction_result.get('invoice_number')
                        extracted_data.invoice_date = extraction_result.get('invoice_date')
                        extracted_data.raw_json = extraction_result.get('raw_data')
                        extracted_data.save()
                    except ExtractedData.DoesNotExist:
                        # Procesar el texto y crear un nuevo registro de datos extraídos
                        extraction_result = model_service.process_text(text_content)
                        ExtractedData.objects.create(
                            ocr_request=existing_request,
                            company=extraction_result.get('company'),
                            invoice_number=extraction_result.get('invoice_number'),
                            invoice_date=extraction_result.get('invoice_date'),
                            raw_json=extraction_result.get('raw_data')
                        )
                else:
                    # Si no está configurado para actualizar, devolver un error de duplicado
                    return Response(
                        {'error': f'Ya existe un OCR con ID: {ocr_id}'},
                        status=status.HTTP_409_CONFLICT
                    )
            except OCRRequest.DoesNotExist:
                # Si no existe, procesarlo normalmente
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
            
            # Obtener los datos más recientes de la base de datos
            ocr_request = OCRRequest.objects.get(ocr_id=ocr_id)
            extracted_data = ExtractedData.objects.get(ocr_request=ocr_request)
            
            # Preparar respuesta
            response_data = {
                'ocr_id': ocr_id,
                'company': extracted_data.company,
                'invoice_number': extracted_data.invoice_number,
                'invoice_date': extracted_data.invoice_date,
                'raw_data': extracted_data.raw_json
            }
            
            # Registrar el tiempo de procesamiento
            processing_time = time.time() - start_time
            logger.info(f"OCR {ocr_id} procesado en {processing_time:.2f} segundos")
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error al procesar OCR {ocr_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'Error al procesar la solicitud: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OCRBatchProcessView(APIView):
    """
    Endpoint optimizado para procesar múltiples textos OCR en lote
    """
    @swagger_auto_schema(
        request_body=OCRBatchInputSerializer,
        responses={200: OCRResponseSerializer(many=True)}
    )
    def post(self, request):
        """
        Procesa múltiples textos OCR y extrae información relevante para cada uno.
        
        Recibe una lista de textos OCR con sus identificadores y devuelve la información
        extraída para cada uno utilizando procesamiento en paralelo.
        """
        start_time = time.time()
        serializer = OCRBatchInputSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        ocr_items = serializer.validated_data['ocr_items']
        model_service = ModelService()
        
        # Verificar si el modelo está disponible
        if model_service.model is None or model_service.tokenizer is None:
            logger.error("Modelo o tokenizador no disponible para procesamiento por lotes")
            return Response(
                {'error': 'Modelo no disponible'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        try:
            # Extraer los textos para procesamiento paralelo
            texts = [item['text_content'] for item in ocr_items]
            ocr_ids = [item['ocr_id'] for item in ocr_items]
            
            # Procesar todos los textos en paralelo
            extraction_results = model_service.process_batch(texts)
            
            # Guardar resultados en la base de datos y preparar respuesta
            results = []
            with transaction.atomic():
                for i, (ocr_id, text_content, extraction_result) in enumerate(zip(ocr_ids, texts, extraction_results)):
                    try:
                        # Comprobar si ya existe
                        try:
                            ocr_request = OCRRequest.objects.get(ocr_id=ocr_id)
                            if getattr(settings, 'UPDATE_EXISTING_OCR', False):
                                # Actualizar si existe y está permitido
                                ocr_request.text_content = text_content
                                ocr_request.save()
                                
                                try:
                                    extracted_data = ExtractedData.objects.get(ocr_request=ocr_request)
                                    extracted_data.company = extraction_result.get('company')
                                    extracted_data.invoice_number = extraction_result.get('invoice_number')
                                    extracted_data.invoice_date = extraction_result.get('invoice_date')
                                    extracted_data.raw_json = extraction_result.get('raw_data')
                                    extracted_data.save()
                                except ExtractedData.DoesNotExist:
                                    ExtractedData.objects.create(
                                        ocr_request=ocr_request,
                                        company=extraction_result.get('company'),
                                        invoice_number=extraction_result.get('invoice_number'),
                                        invoice_date=extraction_result.get('invoice_date'),
                                        raw_json=extraction_result.get('raw_data')
                                    )
                            else:
                                # Si no está permitido actualizar, usar los datos existentes
                                logger.warning(f"OCR ID duplicado en lote: {ocr_id}. Usando datos existentes.")
                                extracted_data = ExtractedData.objects.get(ocr_request=ocr_request)
                                extraction_result = {
                                    'company': extracted_data.company,
                                    'invoice_number': extracted_data.invoice_number,
                                    'invoice_date': extracted_data.invoice_date,
                                    'raw_data': extracted_data.raw_json
                                }
                        except OCRRequest.DoesNotExist:
                            # Crear nuevo registro
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
                        
                        # Añadir a resultados
                        results.append({
                            'ocr_id': ocr_id,
                            'company': extraction_result.get('company'),
                            'invoice_number': extraction_result.get('invoice_number'),
                            'invoice_date': extraction_result.get('invoice_date'),
                            'raw_data': extraction_result.get('raw_data')
                        })
                    except Exception as e:
                        logger.error(f"Error procesando ítem {i} (OCR ID: {ocr_id}): {str(e)}")
                        logger.error(traceback.format_exc())
                        # Añadir un resultado de error pero continuar con el resto
                        results.append({
                            'ocr_id': ocr_id,
                            'company': None,
                            'invoice_number': None,
                            'invoice_date': None,
                            'raw_data': {'error': str(e)}
                        })
            
            # Registrar el tiempo de procesamiento
            processing_time = time.time() - start_time
            logger.info(f"Lote de {len(ocr_items)} OCRs procesado en {processing_time:.2f} segundos")
            
            return Response(results, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error general al procesar OCR en lote: {str(e)}")
            logger.error(traceback.format_exc())
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
            start_time = time.time()
            model_service = ModelService()
            success = model_service.reload_model()
            
            # Registrar el tiempo de recarga
            reload_time = time.time() - start_time
            logger.info(f"Recarga del modelo completada en {reload_time:.2f} segundos")
            
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
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'Error al recargar el modelo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ModelStatusView(APIView):
    """
    Endpoint para verificar el estado del modelo
    """
    def get(self, request):
        """
        Verifica si el modelo está cargado correctamente y devuelve información
        sobre su estado actual.
        """
        try:
            model_service = ModelService()
            
            # Comprobar estado del modelo
            model_loaded = model_service.model is not None
            tokenizer_loaded = model_service.tokenizer is not None
            device = model_service.device
            
            # Obtener información del sistema
            import platform
            import psutil
            
            status_info = {
                'model_loaded': model_loaded,
                'tokenizer_loaded': tokenizer_loaded,
                'device': device,
                'cuda_available': torch.cuda.is_available(),
                'system_info': {
                    'platform': platform.platform(),
                    'python_version': platform.python_version(),
                    'cpu_count': psutil.cpu_count(),
                    'memory_available': f"{psutil.virtual_memory().available / (1024 * 1024 * 1024):.2f} GB",
                    'memory_total': f"{psutil.virtual_memory().total / (1024 * 1024 * 1024):.2f} GB",
                    'memory_percent': f"{psutil.virtual_memory().percent}%"
                }
            }
            
            # Si el modelo está cargado, añadir una prueba simple
            if model_loaded and tokenizer_loaded:
                try:
                    start_time = time.time()
                    test_result = model_service.process_text("Empresa: Test\nNúmero: 12345\nFecha: 01/01/2025")
                    inference_time = time.time() - start_time
                    
                    status_info['test_inference'] = {
                        'success': True,
                        'time': f"{inference_time:.2f} segundos",
                        'result': test_result
                    }
                except Exception as e:
                    status_info['test_inference'] = {
                        'success': False,
                        'error': str(e)
                    }
            
            return Response(status_info, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error al verificar estado del modelo: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'Error al verificar estado del modelo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )