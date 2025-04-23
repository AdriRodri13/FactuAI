import os
import json
import logging
from django.conf import settings
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import torch

logger = logging.getLogger(__name__)

class ModelService:
    """
    Servicio para interactuar con el modelo de Hugging Face para la extracción de información
    de facturas a partir de texto OCR.
    """
    _instance = None
    model = None
    tokenizer = None
    
    def __new__(cls):
        """
        Implementación del patrón Singleton para asegurar que solo hay una instancia
        del modelo cargada en memoria.
        """
        if cls._instance is None:
            cls._instance = super(ModelService, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance
    
    def _load_model(self):
        """
        Carga el modelo y el tokenizador desde la carpeta especificada.
        """
        try:
            model_dir = settings.MODEL_DIR
            logger.info(f"Cargando modelo desde: {model_dir}")
            
            # Cargar el modelo y el tokenizador
            self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
            
            logger.info("Modelo cargado correctamente")
        except Exception as e:
            logger.error(f"Error al cargar el modelo: {str(e)}")
            # Si hay un error, establecemos el modelo como None para manejarlo adecuadamente
            self.model = None
            self.tokenizer = None
    
    def reload_model(self):
        """
        Recarga el modelo, útil cuando se actualiza la carpeta del modelo.
        """
        logger.info("Recargando modelo...")
        self.model = None
        self.tokenizer = None
        self._load_model()
        return self.model is not None
    
    def process_text(self, text):
        """
        Procesa el texto OCR y extrae la información relevante.
        
        Args:
            text (str): Texto OCR de la factura
            
        Returns:
            dict: Diccionario con la información extraída (empresa, número de factura, fecha)
        """
        if self.model is None or self.tokenizer is None:
            logger.error("El modelo no está cargado correctamente")
            return {
                "company": None,
                "invoice_number": None,
                "invoice_date": None,
                "raw_data": {"error": "Modelo no disponible"}
            }
        
        try:
            # En un caso real, aquí utilizarías el modelo para extraer la información
            # Por ahora, simularemos la extracción con una implementación básica
            
            # Tokenizar el texto
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            
            # Realizar la inferencia (esto es una simulación)
            # En un caso real, usarías algo como:
            # outputs = self.model(**inputs)
            
            # Simulamos la extracción de información
            # En una implementación real, esto vendría del modelo
            # Para simular, buscaremos patrones simples en el texto
            
            # Extraer empresa (simulado)
            company = None
            if "empresa:" in text.lower():
                company_start = text.lower().find("empresa:") + len("empresa:")
                company_end = text.find("\n", company_start)
                if company_end == -1:
                    company_end = len(text)
                company = text[company_start:company_end].strip()
            
            # Extraer número de factura (simulado)
            invoice_number = None
            if "factura" in text.lower() and "número" in text.lower():
                inv_start = text.lower().find("número") + len("número")
                inv_end = text.find("\n", inv_start)
                if inv_end == -1:
                    inv_end = len(text)
                invoice_number = text[inv_start:inv_end].strip()
            elif "nº" in text.lower():
                inv_start = text.lower().find("nº") + len("nº")
                inv_end = text.find("\n", inv_start)
                if inv_end == -1:
                    inv_end = len(text)
                invoice_number = text[inv_start:inv_end].strip()
            
            # Extraer fecha (simulado)
            invoice_date = None
            if "fecha" in text.lower():
                date_start = text.lower().find("fecha") + len("fecha")
                date_end = text.find("\n", date_start)
                if date_end == -1:
                    date_end = len(text)
                invoice_date = text[date_start:date_end].strip()
            
            # Construir la respuesta
            result = {
                "company": company,
                "invoice_number": invoice_number,
                "invoice_date": invoice_date,
                "raw_data": {
                    "company": company,
                    "invoice_number": invoice_number,
                    "invoice_date": invoice_date
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error al procesar el texto: {str(e)}")
            return {
                "company": None,
                "invoice_number": None,
                "invoice_date": None,
                "raw_data": {"error": str(e)}
            }

# NOTA: En una implementación real, el código anterior sería reemplazado por la 
# integración con tu modelo fine-tuneado de Hugging Face. El código actual es
# una simulación para que la API funcione mientras se desarrolla/mejora el modelo.