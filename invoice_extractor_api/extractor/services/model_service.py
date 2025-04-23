import os
import json
import logging
import re
import traceback
import concurrent.futures
from functools import lru_cache
from django.conf import settings
from transformers import T5Tokenizer, T5ForConditionalGeneration
import torch

logger = logging.getLogger(__name__)

class ModelService:
    """
    Servicio optimizado para interactuar con el modelo T5 fine-tuneado para la extracción 
    de información de facturas a partir de texto OCR.
    """
    _instance = None
    model = None
    tokenizer = None
    device = None
    max_workers = os.cpu_count() or 2  # Usar todos los cores disponibles o 2 como mínimo
    
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
        Carga el modelo T5 y el tokenizador desde la carpeta especificada,
        con optimizaciones para producción.
        """
        try:
            model_dir = settings.MODEL_DIR
            logger.info(f"Cargando modelo T5 desde: {model_dir}")
            
            # Verificar que la carpeta existe
            if not os.path.exists(model_dir):
                logger.error(f"La carpeta del modelo no existe: {model_dir}")
                self.model = None
                self.tokenizer = None
                return
            
            # Listar archivos en la carpeta para debugging
            files_in_dir = os.listdir(model_dir)
            logger.info(f"Archivos en la carpeta del modelo: {files_in_dir}")
            
            # Determinar el dispositivo (CPU o GPU)
            if torch.cuda.is_available():
                self.device = "cuda"
                # Establecer la semilla para reproducibilidad
                torch.cuda.manual_seed_all(42)
                # Optimizaciones para inferencia en GPU
                torch.backends.cudnn.benchmark = True
            else:
                self.device = "cpu"
                # Establecer número de threads para optimizar CPU
                torch.set_num_threads(self.max_workers)
            
            logger.info(f"Utilizando dispositivo: {self.device}")
            
            # Cargar el tokenizador con manejo de errores detallado
            try:
                logger.debug("Intentando cargar el tokenizador...")
                self.tokenizer = T5Tokenizer.from_pretrained(model_dir)
                logger.info("Tokenizador cargado correctamente")
            except Exception as e:
                logger.error(f"Error al cargar el tokenizador: {str(e)}")
                logger.error(traceback.format_exc())
                self.tokenizer = None
                return
            
            # Cargar el modelo con manejo de errores detallado y optimizaciones
            try:
                logger.debug("Intentando cargar el modelo T5...")
                
                # Configurar opciones de optimización
                model_config = {
                    'torchscript': True,  # Optimización con TorchScript
                    'return_dict': False  # Optimiza el rendimiento
                }
                
                # Cargar el modelo
                self.model = T5ForConditionalGeneration.from_pretrained(
                    model_dir, 
                    **model_config
                ).to(self.device)
                
                # Poner el modelo en modo evaluación (más eficiente)
                self.model.eval()
                
                logger.info("Modelo T5 cargado correctamente")
            except Exception as e:
                logger.error(f"Error al cargar el modelo T5: {str(e)}")
                logger.error(traceback.format_exc())
                self.model = None
                return
            
            # Probar el modelo con un texto de ejemplo
            try:
                logger.debug("Realizando prueba de inferencia...")
                test_text = "extrae_info: PRUEBA"
                inputs = self.tokenizer(test_text, return_tensors="pt", truncation=True, max_length=10).to(self.device)
                with torch.no_grad():  # No calcular gradientes en inferencia
                    _ = self.model.generate(**inputs, max_length=20)
                logger.info("Prueba de inferencia exitosa")
            except Exception as e:
                logger.error(f"Error en la prueba de inferencia: {str(e)}")
                logger.error(traceback.format_exc())
                # No marcamos el modelo como None aquí porque la prueba podría fallar
                # pero el modelo podría estar bien para otros inputs
            
        except Exception as e:
            logger.error(f"Error general al cargar el modelo T5: {str(e)}")
            logger.error(traceback.format_exc())
            self.model = None
            self.tokenizer = None
            self.device = None
    
    def reload_model(self):
        """
        Recarga el modelo, útil cuando se actualiza la carpeta del modelo.
        """
        logger.info("Recargando modelo T5...")
        # Liberar memoria explícitamente
        if self.model:
            del self.model
        if self.tokenizer:
            del self.tokenizer
        
        # Forzar limpieza de memoria en GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        self.model = None
        self.tokenizer = None
        self.device = None
        self._load_model()
        return self.model is not None and self.tokenizer is not None
    
    @lru_cache(maxsize=128)
    def _parse_model_output(self, output_text):
        """
        Analiza el texto de salida del modelo y extrae la información estructurada.
        Implementa caché para mejorar rendimiento con outputs repetidos.
        
        Args:
            output_text (str): Texto generado por el modelo T5
            
        Returns:
            dict: Diccionario con los campos extraídos
        """
        # Inicializar el diccionario de resultados
        result = {
            "company": None,
            "invoice_number": None,
            "invoice_date": None,
            "raw_data": {}
        }
        
        # Analizar la salida del modelo
        try:
            logger.debug(f"Analizando salida del modelo: {output_text}")
            
            # La salida puede ser un JSON directo o texto con formato específico
            if output_text.strip().startswith('{') and output_text.strip().endswith('}'):
                # Intentar parsear como JSON
                parsed_data = json.loads(output_text)
                logger.debug(f"Salida parseada como JSON: {parsed_data}")
                
                # Mapear campos conocidos
                result["company"] = parsed_data.get("empresa")
                result["invoice_number"] = parsed_data.get("numero_factura")
                result["invoice_date"] = parsed_data.get("fecha_factura") or parsed_data.get("fecha")
                result["raw_data"] = parsed_data
            
            # Intentar convertir a JSON - formato: "key": "value", "key2": "value2"
            elif '"empresa":' in output_text or '"numero_factura":' in output_text or '"fecha":' in output_text:
                try:
                    # Intentar formatear como JSON válido
                    json_str = '{' + output_text.replace('\\"', '"').strip('"\'') + '}'
                    # Reemplazar comillas simples por dobles si es necesario
                    json_str = json_str.replace("'", '"')
                    
                    parsed_data = json.loads(json_str)
                    logger.debug(f"Salida convertida a JSON: {parsed_data}")
                    
                    # Mapear campos conocidos
                    result["company"] = parsed_data.get("empresa")
                    result["invoice_number"] = parsed_data.get("numero_factura")
                    result["invoice_date"] = parsed_data.get("fecha_factura") or parsed_data.get("fecha")
                    result["raw_data"] = parsed_data
                except json.JSONDecodeError:
                    logger.warning(f"No se pudo convertir a JSON: {output_text}")
                    # Continuar con el enfoque de búsqueda de patrones
            
            # Si todavía no hay datos, buscar patrones en el texto
            if result["company"] is None and result["invoice_number"] is None and result["invoice_date"] is None:
                logger.debug("Buscando patrones en el texto.")
                
                # Empresa - buscar patrones como "empresa: X" o "empresa": "X"
                company_patterns = [
                    r'empresa:\s*"?([^,"]+)"?',
                    r'"empresa":\s*"([^"]+)"',
                    r"'empresa':\s*'([^']+)'"
                ]
                for pattern in company_patterns:
                    company_match = re.search(pattern, output_text, re.IGNORECASE)
                    if company_match:
                        result["company"] = company_match.group(1).strip()
                        break
                
                # Número de factura
                invoice_patterns = [
                    r'numero_factura:\s*"?([^,"]+)"?',
                    r'"numero_factura":\s*"([^"]+)"',
                    r"'numero_factura':\s*'([^']+)'"
                ]
                for pattern in invoice_patterns:
                    invoice_match = re.search(pattern, output_text, re.IGNORECASE)
                    if invoice_match:
                        result["invoice_number"] = invoice_match.group(1).strip()
                        break
                
                # Fecha - buscar tanto fecha_factura como fecha
                date_patterns = [
                    r'fecha_factura:\s*"?([^,"]+)"?',
                    r'"fecha_factura":\s*"([^"]+)"',
                    r"'fecha_factura':\s*'([^']+)'",
                    r'fecha:\s*"?([^,"]+)"?',
                    r'"fecha":\s*"([^"]+)"',
                    r"'fecha':\s*'([^']+)'"
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, output_text, re.IGNORECASE)
                    if date_match:
                        result["invoice_date"] = date_match.group(1).strip()
                        break
            
            # Guardar el texto completo en raw_data si no se ha hecho ya
            if not result["raw_data"]:
                result["raw_data"] = {
                    "output_text": output_text,
                    "empresa": result["company"],
                    "numero_factura": result["invoice_number"],
                    "fecha_factura": result["invoice_date"]
                }
            
            logger.info(f"Extracción completada: empresa={result['company']}, factura={result['invoice_number']}, fecha={result['invoice_date']}")
        
        except Exception as e:
            logger.error(f"Error al parsear la salida del modelo: {str(e)}")
            logger.error(traceback.format_exc())
            result["raw_data"] = {"error": str(e), "output_text": output_text}
        
        return result
    
    def process_text(self, text):
        """
        Procesa el texto OCR utilizando el modelo T5 fine-tuneado y extrae la información relevante.
        
        Args:
            text (str): Texto OCR de la factura
            
        Returns:
            dict: Diccionario con la información extraída (empresa, número de factura, fecha)
        """
        if self.model is None or self.tokenizer is None:
            logger.error("El modelo T5 no está cargado correctamente")
            return {
                "company": None,
                "invoice_number": None,
                "invoice_date": None,
                "raw_data": {"error": "Modelo no disponible"}
            }
        
        try:
            # Preparar el texto de entrada con el prefijo adecuado
            input_text = "extrae_info: " + text.strip()
            logger.debug(f"Procesando texto: {input_text[:100]}...")
            
            # Tokenizar la entrada
            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                truncation=True,
                padding="max_length",
                max_length=512
            ).to(self.device)
            
            # Generar la predicción sin calcular gradientes (más eficiente)
            logger.debug("Generando predicción...")
            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_length=128,
                    num_beams=4,
                    early_stopping=True
                )
            
            # Decodificar el resultado
            predicted_text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
            logger.debug(f"Predicción generada: {predicted_text}")
            
            # Analizar y estructurar la salida
            result = self._parse_model_output(predicted_text)
            
            logger.info(f"Procesamiento exitoso para entrada: {text[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error al procesar el texto con el modelo T5: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "company": None,
                "invoice_number": None,
                "invoice_date": None,
                "raw_data": {"error": str(e)}
            }
    
    def process_batch(self, texts):
        """
        Procesa múltiples textos OCR en paralelo para mejor rendimiento.
        
        Args:
            texts (list): Lista de textos OCR a procesar
            
        Returns:
            list: Lista de resultados de extracción
        """
        results = []
        
        # Verificar si el modelo está disponible
        if self.model is None or self.tokenizer is None:
            logger.error("El modelo T5 no está cargado correctamente para procesamiento por lotes")
            return [
                {
                    "company": None,
                    "invoice_number": None,
                    "invoice_date": None,
                    "raw_data": {"error": "Modelo no disponible"}
                } for _ in texts
            ]
        
        # Procesar textos en paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Enviar trabajos al executor
            future_to_text = {executor.submit(self.process_text, text): text for text in texts}
            
            # Recoger resultados a medida que se completan
            for future in concurrent.futures.as_completed(future_to_text):
                text = future_to_text[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error en procesamiento paralelo: {str(e)}")
                    results.append({
                        "company": None,
                        "invoice_number": None,
                        "invoice_date": None,
                        "raw_data": {"error": str(e)}
                    })
        
        return results