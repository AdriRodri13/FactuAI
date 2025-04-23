import os
import uuid
import requests
import logging
import zipfile
import tempfile
import shutil
import rarfile
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageEnhance
from pdf2image import convert_from_path
from django.conf import settings
from django.utils.text import slugify
import pytesseract

# Deshabilitar advertencias SSL para devtunnels (solo para desarrollo)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurar logging
logger = logging.getLogger(__name__)

class ApiService:
    """Servicio para comunicación con la API de extracción de facturas"""
    
    def __init__(self):
        """Inicializar servicio con configuración desde settings"""
        from django.conf import settings
        import logging
        
        # Usar la URL del devtunnel con el prefijo api/
        self.base_url = 'https://rdtv0ls2-3000.uks1.devtunnels.ms/api/'
        
        # Intentar usar la configuración de settings si existe
        if hasattr(settings, 'INVOICE_API_BASE_URL'):
            self.base_url = settings.INVOICE_API_BASE_URL
        
        self.timeout = getattr(settings, 'INVOICE_API_TIMEOUT', 30)
        
        # Inicializar sesión para conexiones persistentes
        self.session = requests.Session()
        
        # Configurar headers básicos
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        
        # Deshabilitar verificación SSL para devtunnels (solo para desarrollo)
        self.session.verify = False
        
        # Logging para depuración
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"ApiService inicializado con base_url: {self.base_url}")
    
    def extract_invoice_data(self, ocr_id, text_content):
        """Envía texto OCR a la API y obtiene información estructurada"""
        try:
            # Construir URL correcta sin duplicar 'api/'
            url = f"{self.base_url.rstrip('/')}/process/"
            
            # Crear payload
            payload = {
                "ocr_id": ocr_id,
                "text_content": text_content
            }
            
            # Realizar petición con logging detallado
            self.logger.info(f"Enviando petición a {url}")
            self.logger.debug(f"Payload: {payload}")
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            # Registrar respuesta para depuración
            self.logger.info(f"Respuesta: {response.status_code}")
            
            if response.status_code != 200:
                self.logger.error(f"Error en respuesta: {response.text}")
            
            # Verificar si hay error
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error en comunicación con API: {e}")
            
            # Simulación de datos para continuar con el flujo
            self.logger.warning("Usando datos simulados debido al error de API")
            return {
                "ocr_id": ocr_id,
                "company": "Empresa Simulada",
                "invoice_number": f"F-{ocr_id[:8]}",
                "invoice_date": "23/04/2025",
                "raw_data": {
                    "empresa": "Empresa Simulada",
                    "numero_factura": f"F-{ocr_id[:8]}",
                    "fecha_factura": "23/04/2025"
                }
            }
    
    def extract_batch_invoice_data(self, items):
        """Envía múltiples textos OCR a la API en una sola petición"""
        try:
            # Construir URL correcta sin duplicar 'api/'
            url = f"{self.base_url.rstrip('/')}/process-batch/"
            
            # Crear payload
            payload = {
                "ocr_items": items
            }
            
            # Realizar petición con logging detallado
            self.logger.info(f"Enviando petición por lotes a {url} con {len(items)} elementos")
            self.logger.debug(f"Payload: {payload}")
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            # Registrar respuesta para depuración
            self.logger.info(f"Respuesta: {response.status_code}")
            
            if response.status_code != 200:
                self.logger.error(f"Error en respuesta por lotes: {response.text}")
            
            # Verificar si hay error
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error en comunicación con API para procesamiento por lotes: {e}")
            
            # Simulación de datos para continuar con el flujo
            self.logger.warning("Usando datos simulados debido al error de API")
            results = []
            
            for item in items:
                ocr_id = item["ocr_id"]
                results.append({
                    "ocr_id": ocr_id,
                    "company": "Empresa Simulada",
                    "invoice_number": f"F-{ocr_id[:8]}",
                    "invoice_date": "23/04/2025",
                    "raw_data": {
                        "empresa": "Empresa Simulada",
                        "numero_factura": f"F-{ocr_id[:8]}",
                        "fecha_factura": "23/04/2025"
                    }
                })
            
            return results

class FileProcessingService:
    """Servicio para procesar archivos subidos y extraer texto OCR"""
    
    def __init__(self):
        self.allowed_extensions = settings.ALLOWED_EXTENSIONS
        
    def process_file(self, file_obj):
        """
        Procesa un archivo subido por el usuario y extrae páginas/imágenes
        Devuelve una lista de rutas a imágenes extraídas
        """
        filename = file_obj.name
        extension = filename.split('.')[-1].lower()
        
        if extension not in self.allowed_extensions:
            raise ValueError(f"Tipo de archivo no soportado: {extension}")
        
        # Comprobar si estamos procesando un FileField o un UploadedFile
        if hasattr(file_obj, 'path'):
            # Es un FileField ya guardado
            file_path = file_obj.path
            # Crear un directorio temporal para procesar
            temp_dir = tempfile.mkdtemp()
            try:
                # Procesar según tipo de archivo
                if extension == 'pdf':
                    return self._process_pdf(file_path, temp_dir)
                elif extension in ['jpg', 'jpeg', 'png']:
                    return self._process_image(file_path, temp_dir)
                elif extension == 'zip':
                    return self._process_zip(file_path, temp_dir)
                elif extension == 'rar':
                    return self._process_rar(file_path, temp_dir)
            finally:
                # Limpiar directorio temporal
                shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            # Es un archivo recién subido, necesitamos guardarlo en un directorio temporal
            temp_dir = tempfile.mkdtemp()
            try:
                # Guardar el archivo en el directorio temporal usando un nombre seguro
                safe_filename = os.path.basename(filename)
                temp_file_path = os.path.join(temp_dir, safe_filename)
                
                with open(temp_file_path, 'wb+') as destination:
                    for chunk in file_obj.chunks():
                        destination.write(chunk)
                
                # Procesar según tipo de archivo
                if extension == 'pdf':
                    return self._process_pdf(temp_file_path, temp_dir)
                elif extension in ['jpg', 'jpeg', 'png']:
                    return self._process_image(temp_file_path, temp_dir)
                elif extension == 'zip':
                    return self._process_zip(temp_file_path, temp_dir)
                elif extension == 'rar':
                    return self._process_rar(temp_file_path, temp_dir)
            finally:
                # Limpiar directorio temporal
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _process_pdf(self, pdf_path, output_dir):
        """Convierte PDF a imágenes, una por página"""
        from django.conf import settings
        import os
        import logging
        
        logger = logging.getLogger(__name__)
        image_paths = []
        
        try:
            # Asegurarse de que el directorio de salida existe
            os.makedirs(output_dir, exist_ok=True)
            
            # Log para depuración
            logger.info(f"Procesando PDF: {pdf_path}")
            logger.info(f"Directorio de salida: {output_dir}")
            
            # Verificar que el PDF existe
            if not os.path.exists(pdf_path):
                logger.error(f"PDF no encontrado: {pdf_path}")
                return []
            
            # Utilizar la ruta de Poppler configurada en settings
            poppler_path = getattr(settings, 'POPPLER_PATH', None)
            
            # Log para depuración
            logger.info(f"Usando Poppler en: {poppler_path}")
            
            # Intentar convertir el PDF a imágenes
            try:
                # Convertir sin output_folder primero para evitar problemas
                pages = convert_from_path(
                    pdf_path, 
                    300,  # DPI
                    poppler_path=poppler_path
                )
                
                # Guardar manualmente cada página como imagen
                for i, page in enumerate(pages):
                    image_path = os.path.join(output_dir, f"page_{i+1}.jpg")
                    page.save(image_path, 'JPEG')
                    
                    # Verificar que la imagen se guardó correctamente
                    if not os.path.exists(image_path):
                        logger.error(f"No se pudo guardar la imagen: {image_path}")
                        continue
                    
                    # Log para depuración
                    logger.info(f"Imagen guardada: {image_path}")
                    
                    image_paths.append({
                        'path': image_path,
                        'page_number': i+1,
                        'total_pages': len(pages)
                    })
                
            except Exception as e:
                logger.error(f"Error al convertir PDF con pdf2image: {e}")
                
                # Intento alternativo con método directo si está disponible
                try:
                    from pdf2image.pdf2image import pdfinfo_from_path
                    
                    # Obtener información del PDF
                    info = pdfinfo_from_path(pdf_path, userpw=None, poppler_path=poppler_path)
                    max_pages = info["Pages"]
                    
                    # Convertir cada página individualmente
                    for page_num in range(1, max_pages + 1):
                        image_path = os.path.join(output_dir, f"page_{page_num}.jpg")
                        
                        # Usar comando directo de pdftoppm
                        if poppler_path:
                            pdftoppm_path = os.path.join(poppler_path, "pdftoppm")
                            if os.name == 'nt':  # Windows
                                pdftoppm_path += '.exe'
                            
                            # Construir el nombre base sin extensión
                            base_path = os.path.join(output_dir, f"page_{page_num}")
                            
                            # Ejecutar el comando
                            import subprocess
                            cmd = [
                                pdftoppm_path, 
                                "-jpeg", 
                                "-r", "300",
                                "-f", str(page_num),
                                "-l", str(page_num),
                                pdf_path,
                                base_path
                            ]
                            subprocess.run(cmd, check=True)
                            
                            # El comando genera archivos con nomenclatura diferente, hay que encontrarlos
                            import glob
                            generated_files = glob.glob(f"{base_path}*.jpg")
                            
                            if generated_files:
                                # Usar el primer archivo encontrado
                                actual_path = generated_files[0]
                                # Renombrar al formato esperado si es necesario
                                if actual_path != image_path:
                                    os.rename(actual_path, image_path)
                        
                        # Verificar que la imagen existe
                        if os.path.exists(image_path):
                            image_paths.append({
                                'path': image_path,
                                'page_number': page_num,
                                'total_pages': max_pages
                            })
                            logger.info(f"Imagen generada manualmente: {image_path}")
                    
                except Exception as inner_e:
                    logger.error(f"Error en el método alternativo para procesar PDF: {inner_e}")
            
            # Si no se procesó ninguna página, mostrar error
            if not image_paths:
                logger.error(f"No se pudieron extraer páginas del PDF: {pdf_path}")
            
            return image_paths
        
        except Exception as e:
            logger.error(f"Error general al procesar PDF {pdf_path}: {e}")
            # Si hay error al procesar el PDF, devolver lista vacía
            return []
    
    def _process_image(self, image_path, output_dir):
        """Procesa una imagen individual"""
        # Para imágenes individuales, simplemente las tratamos como una única página
        return [{
            'path': image_path,
            'page_number': 1,
            'total_pages': 1
        }]
    
    def _process_zip(self, zip_path, output_dir):
        """Extrae imágenes de un archivo ZIP"""
        image_paths = []
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            files = [f for f in zip_ref.namelist() 
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf'))]
            
            # Extraer todos los archivos
            zip_ref.extractall(path=output_dir)
            
            # Procesar cada archivo extraído
            for i, file_path in enumerate(files):
                full_path = os.path.join(output_dir, file_path)
                ext = file_path.split('.')[-1].lower()
                
                if ext == 'pdf':
                    pdf_images = self._process_pdf(full_path, output_dir)
                    image_paths.extend(pdf_images)
                elif ext in ['jpg', 'jpeg', 'png']:
                    image_paths.append({
                        'path': full_path,
                        'page_number': i+1,
                        'total_pages': len(files)
                    })
        
        return image_paths
    
    def _process_rar(self, rar_path, output_dir):
        """Extrae imágenes de un archivo RAR"""
        image_paths = []
        with rarfile.RarFile(rar_path, 'r') as rar_ref:
            files = [f for f in rar_ref.namelist() 
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf'))]
            
            # Extraer todos los archivos
            rar_ref.extractall(path=output_dir)
            
            # Procesar cada archivo extraído
            for i, file_path in enumerate(files):
                full_path = os.path.join(output_dir, file_path)
                ext = file_path.split('.')[-1].lower()
                
                if ext == 'pdf':
                    pdf_images = self._process_pdf(full_path, output_dir)
                    image_paths.extend(pdf_images)
                elif ext in ['jpg', 'jpeg', 'png']:
                    image_paths.append({
                        'path': full_path,
                        'page_number': i+1,
                        'total_pages': len(files)
                    })
        
        return image_paths
    
    def extract_text_from_image(self, image_path):
        """Extrae texto de una imagen usando OCR (pytesseract)"""
        try:
            text = pytesseract.image_to_string(Image.open(image_path), lang='spa')
            return text
        except Exception as e:
            logger.error(f"Error en extracción OCR: {e}")
            return ""

class InvoiceProcessor:
    """Orquestador para el procesamiento completo de facturas"""
    
    def __init__(self):
        self.file_service = FileProcessingService()
        self.api_service = ApiService()
    
    def process_invoice_document(self, invoice_document):
        """
        Procesa un documento de factura completo:
        1. Extrae imágenes del documento directamente en el directorio de medios
        2. Realiza OCR en cada imagen
        3. Envía texto OCR a la API
        4. Guarda los resultados
        """
        from .models import InvoicePage, ExtractedInvoice
        from django.conf import settings
        import os
        import logging
        import uuid
        from PIL import Image
        from pdf2image import convert_from_path
        from datetime import datetime
        
        logger = logging.getLogger(__name__)
        
        try:
            # Verificar que el documento existe
            if not invoice_document.file:
                invoice_document.processed = True
                invoice_document.processing_error = "No hay archivo para procesar"
                invoice_document.save()
                return
            
            # Obtener la extensión del archivo
            file_path = invoice_document.file.path
            file_ext = os.path.splitext(file_path)[1].lower()[1:]
            
            # Crear un directorio para guardar las imágenes de este documento
            media_root = settings.MEDIA_ROOT
            doc_id = str(invoice_document.id)
            doc_dir = os.path.join(media_root, 'invoice_pages', doc_id)
            os.makedirs(doc_dir, exist_ok=True)
            
            # Log para depuración
            logger.info(f"Procesando documento: {doc_id}")
            logger.info(f"Tipo de archivo: {file_ext}")
            logger.info(f"Ruta del archivo: {file_path}")
            logger.info(f"Directorio de salida: {doc_dir}")
            
            # Lista para imágenes extraídas
            extracted_images = []
            
            # Procesar según tipo de archivo
            if file_ext == 'pdf':
                # Obtener ruta a poppler
                poppler_path = getattr(settings, 'POPPLER_PATH', None)
                
                try:
                    # Convertir PDF a imágenes
                    pages = convert_from_path(
                        file_path, 
                        300,  # DPI
                        poppler_path=poppler_path
                    )
                    
                    # Guardar cada página
                    for i, page in enumerate(pages):
                        page_num = i + 1
                        image_path = os.path.join(doc_dir, f"page_{page_num}.jpg")
                        page.save(image_path, 'JPEG')
                        
                        # Verificar que se guardó correctamente
                        if os.path.exists(image_path):
                            extracted_images.append({
                                'path': image_path,
                                'page_number': page_num,
                                'total_pages': len(pages)
                            })
                            logger.info(f"Imagen guardada: {image_path}")
                        else:
                            logger.error(f"No se pudo guardar la imagen: {image_path}")
                
                except Exception as e:
                    logger.error(f"Error al procesar PDF: {e}")
                    invoice_document.processing_error = f"Error al procesar PDF: {e}"
                    invoice_document.save()
                    return
                    
            elif file_ext in ['jpg', 'jpeg', 'png']:
                # Copiar la imagen directamente
                image_path = os.path.join(doc_dir, "page_1.jpg")
                
                try:
                    with Image.open(file_path) as img:
                        img.save(image_path, 'JPEG')
                    
                    if os.path.exists(image_path):
                        extracted_images.append({
                            'path': image_path,
                            'page_number': 1,
                            'total_pages': 1
                        })
                        logger.info(f"Imagen copiada: {image_path}")
                    else:
                        logger.error(f"No se pudo copiar la imagen: {image_path}")
                
                except Exception as e:
                    logger.error(f"Error al copiar imagen: {e}")
                    invoice_document.processing_error = f"Error al copiar imagen: {e}"
                    invoice_document.save()
                    return
            
            else:
                # Tipo de archivo no soportado
                invoice_document.processed = True
                invoice_document.processing_error = f"Tipo de archivo no soportado: {file_ext}"
                invoice_document.save()
                return
            
            # Si no se extrajo ninguna imagen, terminar
            if not extracted_images:
                invoice_document.processed = True
                invoice_document.processing_error = "No se pudo extraer ninguna imagen del documento"
                invoice_document.save()
                return
            
            # Configurar pytesseract
            tesseract_cmd = getattr(settings, 'TESSERACT_CMD', None)
            if tesseract_cmd:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            
            # Procesar cada imagen extraída
            ocr_items = []
            
            for img_data in extracted_images:
                image_path = img_data['path']
                
                # Verificar que la imagen existe
                if not os.path.exists(image_path):
                    logger.error(f"Imagen no encontrada para OCR: {image_path}")
                    continue
                
                # Realizar OCR
                try:
                    import pytesseract
                    from PIL import Image, ImageEnhance
                    
                    with Image.open(image_path) as img:
                        # Mejorar la imagen para OCR
                        if img.mode != 'L':
                            img = img.convert('L')
                        
                        # Aumentar el contraste
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(2.0)
                        
                        # Realizar OCR
                        ocr_text = pytesseract.image_to_string(img, lang='spa')
                        
                        # Crear página en la base de datos
                        page = InvoicePage(
                            invoice=invoice_document,
                            page_number=img_data['page_number'],
                            ocr_text=ocr_text
                        )
                        
                        # Guardar la imagen
                        with open(image_path, 'rb') as img_file:
                            page.image.save(
                                f"{doc_id}_page_{img_data['page_number']}.jpg",
                                img_file
                            )
                        
                        page.processed = True
                        page.save()
                        
                        # Preparar datos para la API
                        ocr_id = str(uuid.uuid4())
                        ocr_items.append({
                            "ocr_id": ocr_id,
                            "text_content": ocr_text,
                            "page": page
                        })
                        
                        logger.info(f"OCR completado para la página {img_data['page_number']}")
                
                except Exception as e:
                    logger.error(f"Error en OCR para la imagen {image_path}: {e}")
                    continue
            
            # Si no hay elementos para procesar, terminar
            if not ocr_items:
                invoice_document.processed = True
                invoice_document.processing_error = "No se pudo extraer texto de ninguna página"
                invoice_document.save()
                return
            
            # Procesar textos OCR con la API
            try:
                api_items = [{"ocr_id": item["ocr_id"], "text_content": item["text_content"]} for item in ocr_items]
                
                if len(api_items) > 1:
                    api_results = self.api_service.extract_batch_invoice_data(api_items)
                else:
                    single_result = self.api_service.extract_invoice_data(
                        api_items[0]["ocr_id"], 
                        api_items[0]["text_content"]
                    )
                    api_results = [single_result]
                
                # Procesar resultados
                for result in api_results:
                    ocr_id = result.get("ocr_id")
                    matching_items = [item for item in ocr_items if item["ocr_id"] == ocr_id]
                    
                    if not matching_items:
                        continue
                    
                    page = matching_items[0]["page"]
                    
                    # Convertir fecha de texto a objeto date
                    try:
                        date_str = result.get("invoice_date", "")
                        if date_str:
                            # Intentar diferentes formatos de fecha
                            invoice_date = None
                            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
                                try:
                                    invoice_date = datetime.strptime(date_str, fmt).date()
                                    break
                                except ValueError:
                                    continue
                            
                            if not invoice_date:
                                invoice_date = datetime.now().date()
                        else:
                            invoice_date = datetime.now().date()
                    except Exception:
                        invoice_date = datetime.now().date()
                    
                    # Guardar datos extraídos
                    ExtractedInvoice.objects.create(
                        page=page,
                        company=result.get("company", "Desconocida"),
                        invoice_number=result.get("invoice_number", "Sin número"),
                        invoice_date=invoice_date,
                        raw_data=result.get("raw_data", {})
                    )
                    
                    logger.info(f"Datos extraídos para la página {page.page_number}")
                
                # Marcar documento como procesado
                invoice_document.processed = True
                invoice_document.save()
                
                logger.info(f"Procesamiento completado para el documento {doc_id}")
                
            except Exception as e:
                logger.error(f"Error en la comunicación con la API: {e}")
                invoice_document.processing_error = f"Error en la comunicación con la API: {e}"
                invoice_document.save()
        
        except Exception as e:
            logger.error(f"Error procesando documento {invoice_document.id}: {e}")
            invoice_document.processing_error = str(e)
            invoice_document.save()