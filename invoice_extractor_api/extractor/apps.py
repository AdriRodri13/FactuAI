from django.apps import AppConfig
import os
import logging
import sys

logger = logging.getLogger(__name__)

class ExtractorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'extractor'
    
    def ready(self):
        """
        Inicializa el modelo cuando se inicia la aplicación
        """
        # Evitamos inicializar el modelo durante las migraciones
        if 'makemigrations' in sys.argv or 'migrate' in sys.argv:
            return
            
        # Importamos aquí para evitar importaciones circulares
        logger.info("Inicializando el modelo desde apps.py...")
        
        try:
            from .services.model_service import ModelService
            
            # Aseguramos que la carpeta del modelo existe
            from django.conf import settings
            model_dir = settings.MODEL_DIR
            if not os.path.exists(model_dir):
                logger.error(f"La carpeta del modelo no existe: {model_dir}")
                return
                
            # Listamos archivos para debugging
            files = os.listdir(model_dir)
            logger.info(f"Archivos en la carpeta del modelo: {files}")
            
            # Inicializamos el modelo - esto debería cargarlo en memoria
            model_service = ModelService()
            if model_service.model is None:
                logger.error("El modelo no se inicializó correctamente")
            else:
                logger.info("Modelo inicializado correctamente desde apps.py")
                
        except Exception as e:
            # Registramos el error pero permitimos que la aplicación inicie
            logger.error(f"Error al inicializar el modelo desde apps.py: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())