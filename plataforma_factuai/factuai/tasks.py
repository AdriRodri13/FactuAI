import logging
from celery import shared_task
from django.utils import timezone
from .models import InvoiceDocument
from .services import InvoiceProcessor

logger = logging.getLogger(__name__)

@shared_task
def process_invoice_task(document_id):
    """
    Tarea asíncrona para procesar un documento de factura
    
    Args:
        document_id: ID del documento InvoiceDocument a procesar
    """
    try:
        # Obtener el documento
        document = InvoiceDocument.objects.get(pk=document_id)
        
        # Si ya está procesado, no hacer nada
        if document.processed:
            return f"Documento {document_id} ya procesado anteriormente"
        
        # Procesar el documento
        processor = InvoiceProcessor()
        processor.process_invoice_document(document)
        
        return f"Documento {document_id} procesado correctamente"
    
    except InvoiceDocument.DoesNotExist:
        logger.error(f"Documento no encontrado: {document_id}")
        return f"Error: Documento {document_id} no encontrado"
    
    except Exception as e:
        logger.error(f"Error procesando documento {document_id}: {e}")
        
        # Actualizar el documento con el error
        try:
            document = InvoiceDocument.objects.get(pk=document_id)
            document.processing_error = str(e)
            document.save()
        except Exception:
            pass
        
        return f"Error procesando documento {document_id}: {str(e)}"

@shared_task
def retry_failed_documents():
    """Tarea periódica para reintentar documentos con errores"""
    failed_docs = InvoiceDocument.objects.filter(
        processed=False
    ).exclude(processing_error=None)
    
    logger.info(f"Reintentando procesar {failed_docs.count()} documentos fallidos")
    
    for doc in failed_docs:
        # Limpiar el error anterior
        doc.processing_error = None
        doc.save()
        
        # Encolar para procesamiento
        process_invoice_task.delay(str(doc.id))
    
    return f"Reencolados {failed_docs.count()} documentos para reprocesamiento"

@shared_task
def cleanup_old_temporary_files():
    """Tarea periódica para limpiar archivos temporales antiguos"""
    # Implementar lógica para limpiar archivos temporales si es necesario
    pass