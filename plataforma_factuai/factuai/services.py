# services.py (modificado)
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
        
        # URL base de la API
        self.base_url = 'https://api.ejemplo.com/api/'
        
        # Intentar usar la configuración de settings si existe
        if hasattr(settings, 'INVOICE_API_BASE_URL'):
            self.base_url = settings.INVOICE_API_BASE_URL
        
        # Clave API (obtener de settings)
        self.api_key = getattr(settings, 'INVOICE_API_KEY', 'default-key')
        
        self.timeout = getattr(settings, 'INVOICE_API_TIMEOUT', 30)
        
        # Inicializar sesión para conexiones persistentes
        self.session = requests.Session()
        
        # Configurar headers básicos
        self.session.headers.update({
            'Accept': 'application/json',
            'X-API-KEY': self.api_key  # Añadir el header de autenticación
        })
        
        # Deshabilitar verificación SSL para desarrollo
        self.session.verify = False
        
        # Logging para depuración
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"ApiService inicializado con base_url: {self.base_url}")
    
    def extract_invoice_data(self, ocr_id, image_path):
        """
        Envía una imagen a la API para OCR y extracción de datos
        
        Args:
            ocr_id: Identificador único para esta operación
            image_path: Ruta a la imagen para procesar
            
        Returns:
            dict: Datos estructurados de la factura
        """
        try:
            # Construir URL correcta
            url = f"{self.base_url.rstrip('/')}/extraer/"
            
            # Verificar que el archivo existe
            if not os.path.exists(image_path):
                self.logger.error(f"La imagen no existe en la ruta: {image_path}")
                return self._get_fallback_data(ocr_id)
            
            # Abrir el archivo para enviarlo
            with open(image_path, 'rb') as image_file:
                # Preparar archivo para envío multipart
                files = {
                    'imagen': (os.path.basename(image_path), image_file, 'image/jpeg')
                }
                
                # Realizar petición con logging detallado
                self.logger.info(f"Enviando imagen a {url}")
                
                # Usamos multipart/form-data para enviar archivos
                response = self.session.post(
                    url, 
                    files=files,
                    timeout=self.timeout
                )
            
            # Registrar respuesta para depuración
            self.logger.info(f"Respuesta: {response.status_code}")
            
            if response.status_code != 200:
                self.logger.error(f"Error en respuesta: {response.text}")
                return self._get_fallback_data(ocr_id)
            
            # Verificar si hay error
            response.raise_for_status()
            
            # Procesar respuesta JSON
            response_data = response.json()
            
            # Extraer el resultado del formato de respuesta
            if 'resultado' in response_data:
                result = response_data['resultado']
            else:
                result = response_data
            
            # Añadir manualmente el ocr_id al resultado para mantener la trazabilidad
            result['ocr_id'] = ocr_id
            
            return self._normalize_api_result(result)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error en comunicación con API: {e}")
            return self._get_fallback_data(ocr_id)
    
    def _get_fallback_data(self, ocr_id):
        """
        Genera datos simulados en caso de error para no interrumpir el flujo
        """
        self.logger.warning("Usando datos simulados debido al error de API")
        return {
            "ocr_id": ocr_id,
            "company": "Empresa Simulada",
            "invoice_number": f"F-{ocr_id[:8]}",
            "invoice_date": "23/04/2025",
            "raw_data": {
                "empresa": "Empresa Simulada",
                "numero_factura": f"F-{ocr_id[:8]}",
                "fecha": "23/04/2025"
            }
        }
    
    def _normalize_api_result(self, result):
        """
        Normaliza el resultado de la API para asegurar consistencia
        
        Args:
            result: Diccionario con la respuesta de la API
            
        Returns:
            dict: Resultado normalizado
        """
        # Asegurarse de que es un diccionario
        if not isinstance(result, dict):
            self.logger.warning(f"Respuesta API no es un diccionario: {result}")
            return {
                "ocr_id": "unknown",
                "company": "Desconocida",
                "invoice_number": "Sin número",
                "invoice_date": datetime.now().strftime('%d/%m/%Y'),
                "raw_data": {}
            }
        
        # Extraer campos principales y manejar casos posibles
        normalized = {
            "ocr_id": result.get("ocr_id", "unknown"),
            "company": result.get("empresa", "Desconocida").lower(),
            "invoice_number": result.get("numero_factura", "Sin número"),
            "invoice_date": result.get("fecha", datetime.now().strftime('%d/%m/%Y')),
            "raw_data": result
        }
        
        return normalized
    
class FileProcessingService:
    """Servicio para procesar archivos subidos y extraer páginas/imágenes"""
    
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

class InvoiceProcessor:
    """Orquestador para el procesamiento completo de facturas"""
    
    def __init__(self):
        from .services import FileProcessingService, ApiService
        self.file_service = FileProcessingService()
        self.api_service = ApiService()
    
    def process_invoice_document(self, invoice_document):
        """
        Procesa un documento de factura completo:
        1. Extrae imágenes del documento directamente en el directorio de medios
        2. Envía cada imagen a la API para OCR y extracción de datos
        3. Guarda los resultados
        """
        from .models import InvoicePage, ExtractedInvoice, InvoiceGroup, Empresa
        
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
            
            # Usar siempre año completo con 4 dígitos
            year = str(invoice_document.upload_date.year)
            month = str(invoice_document.upload_date.month).zfill(2)
            
            doc_dir = os.path.join(media_root, 'invoice_pages', year, month, doc_id)
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
                    from pdf2image import convert_from_path
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
            
            # Procesar cada imagen extraída
            ocr_items = []
            
            for img_data in extracted_images:
                image_path = img_data['path']
                
                # Verificar que la imagen existe
                if not os.path.exists(image_path):
                    logger.error(f"Imagen no encontrada para procesar: {image_path}")
                    continue
                
                # Procesar la imagen con la API
                try:
                    # Generar ID único para esta página
                    ocr_id = str(uuid.uuid4())
                    
                    # Enviar la imagen a la API para obtener texto OCR y datos extraídos
                    result = self.api_service.extract_invoice_data(ocr_id, image_path)
                    
                    # Crear página en la base de datos - ahora sin OCR local
                    page = InvoicePage(
                        invoice=invoice_document,
                        page_number=img_data['page_number'],
                        # Nota: ya no almacenamos texto OCR localmente, lo deja vacío
                        ocr_text=""
                    )
                    
                    # Guardar la imagen
                    with open(image_path, 'rb') as img_file:
                        page.image.save(
                            f"{doc_id}_page_{img_data['page_number']}.jpg",
                            img_file
                        )
                    
                    page.processed = True
                    page.save()
                    
                    # Preparar para crear ExtractedInvoice
                    ocr_items.append({
                        "ocr_id": ocr_id,
                        "result": result,
                        "page": page
                    })
                
                except Exception as e:
                    logger.error(f"Error procesando la imagen {image_path}: {e}")
                    continue
            
            # Si no hay elementos para procesar, terminar
            if not ocr_items:
                invoice_document.processed = True
                invoice_document.processing_error = "No se pudieron procesar las imágenes"
                invoice_document.save()
                return
            
            # Crear entradas en la base de datos con los resultados
            try:
                # Lista para guardar facturas creadas
                extracted_invoices = []
                
                # Procesar cada resultado 
                for item in ocr_items:
                    try:
                        page = item["page"]
                        result = item["result"]
                        
                        # Normalización de fecha
                        invoice_date = self.normalize_date(result.get("invoice_date", ""), result.get("raw_data", {}))
                        
                        # Guardar datos extraídos
                        extracted_invoice = ExtractedInvoice.objects.create(
                            page=page,
                            company=result.get("company", "Desconocida"),
                            invoice_number=result.get("invoice_number", "Sin número"),
                            invoice_date=invoice_date,
                            raw_data=result.get("raw_data", {})
                        )
                        
                        extracted_invoices.append(extracted_invoice)
                        logger.info(f"Procesado exitoso del OCR {item['ocr_id']} para página {page.page_number}")
                    
                    except Exception as e:
                        logger.error(f"Error procesando OCR {item['ocr_id']}: {e}")
                        # Continuar con el siguiente ítem en caso de error
                
                # Agrupar facturas con el mismo número
                try:
                    # Crear un diccionario para agrupar facturas por número y empresa
                    invoice_groups = {}
                    
                    for extracted_invoice in extracted_invoices:
                        company_name = extracted_invoice.company
                        invoice_number = extracted_invoice.invoice_number
                        
                        # Buscar empresa existente por el nombre detectado
                        empresa = Empresa.buscar_por_nombre(company_name)
                        
                        # Si no encuentra empresa, se usará el nombre detectado temporalmente
                        key = (company_name, invoice_number)
                        if key not in invoice_groups:
                            invoice_groups[key] = {
                                'invoices': [],
                                'empresa': empresa  # Puede ser None
                            }
                        invoice_groups[key]['invoices'].append(extracted_invoice)
                    
                    # Crear o actualizar grupos de facturas
                    for (company_name, invoice_number), data in invoice_groups.items():
                        invoices = data['invoices']
                        empresa = data['empresa']
                        
                        if not invoices:
                            continue
                        
                        # Usar la fecha de la primera factura para el grupo
                        first_invoice = invoices[0]
                        
                        # Crear o recuperar el grupo
                        try:
                            # Si tenemos empresa, buscar por ella
                            if empresa:
                                invoice_group, created = InvoiceGroup.objects.get_or_create(
                                    empresa=empresa,
                                    invoice_number=invoice_number,
                                    defaults={
                                        'company': company_name,  # Mantener el nombre original
                                        'invoice_date': first_invoice.invoice_date
                                    }
                                )
                                
                                # Si encontramos la empresa, registrar este nombre detectado
                                empresa.add_nombre_detectado(company_name)
                            else:
                                # Si no hay empresa, seguir usando el campo company
                                invoice_group, created = InvoiceGroup.objects.get_or_create(
                                    company=company_name,
                                    invoice_number=invoice_number,
                                    defaults={
                                        'invoice_date': first_invoice.invoice_date
                                    }
                                )
                                
                                # Marcar esta factura para revisión posterior (necesitará confirmar empresa)
                                invoice_group.necesita_revision = True
                                invoice_group.save()
                            
                            # Asociar todas las facturas al grupo
                            for invoice in invoices:
                                invoice.group = invoice_group
                                invoice.save()
                            
                            logger.info(f"Factura agrupada: {company_name} - {invoice_number} con {len(invoices)} páginas")
                        
                        except Exception as e:
                            logger.error(f"Error al agrupar factura {company_name} - {invoice_number}: {e}")
                            # Continuar con el siguiente grupo en caso de error
                    
                    # Marcar documento como procesado
                    invoice_document.processed = True
                    invoice_document.save()
                    
                except Exception as e:
                    logger.error(f"Error al agrupar facturas: {e}")
                    invoice_document.processing_error = f"Error al agrupar facturas: {e}"
                    invoice_document.save()
                    
            except Exception as e:
                logger.error(f"Error en el procesamiento general: {e}")
                invoice_document.processing_error = f"Error en el procesamiento: {e}"
                invoice_document.save()
        
        except Exception as e:
            logger.error(f"Error procesando documento {invoice_document.id}: {e}")
            invoice_document.processing_error = str(e)
            invoice_document.save()
    def normalize_date(self, date_str, raw_data=None):
        """
        Normaliza diferentes formatos de fecha para obtener un objeto date válido
        
        Args:
            date_str: String con la fecha en formato desconocido
            raw_data: Datos crudos de la API (pueden contener fechas adicionales)
            
        Returns:
            datetime.date: Objeto de fecha normalizado
        """
        # Usar la fecha actual como fallback
        today = datetime.now().date()
        
        # Si no hay fecha, devolver hoy
        if not date_str:
            # Intentar buscar en raw_data si está disponible
            if raw_data and isinstance(raw_data, dict):
                for key in ['fecha_factura', 'fecha', 'date', 'invoice_date']:
                    if key in raw_data and raw_data[key]:
                        date_str = raw_data[key]
                        break
            
            # Si aún no hay fecha, devolver hoy
            if not date_str:
                return today
        
        # Limpiar la cadena de fecha
        date_str = date_str.strip()
        
        # Lista de formatos a probar
        formats = [
            '%d/%m/%Y',  # 31/12/2023
            '%Y/%m/%d',  # 2023/12/31
            '%d-%m-%Y',  # 31-12-2023
            '%Y-%m-%d',  # 2023-12-31
            '%d.%m.%Y',  # 31.12.2023
            '%Y.%m.%d',  # 2023.12.31
            '%d %B %Y',  # 31 December 2023
            '%B %d, %Y', # December 31, 2023
            '%d/%m/%y',  # 31/12/23
            '%y/%m/%d',  # 23/12/31
        ]
        
        # Intentar parsing con cada formato
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                
                # Verificar que el año tiene 4 dígitos y es razonable
                if 2000 <= parsed_date.year <= 2100:
                    return parsed_date
                
                # Si el año tiene 2 dígitos (por ejemplo, 23), ajustar a 2023
                if parsed_date.year < 100:
                    current_century = today.year // 100 * 100
                    adjusted_year = current_century + parsed_date.year
                    return parsed_date.replace(year=adjusted_year)
                
                return parsed_date
            except ValueError:
                continue
        
        # Si no se puede parsear, intentar extraer solo el año, mes y día
        try:
            # Extraer números de la cadena
            import re
            numbers = re.findall(r'\d+', date_str)
            
            if len(numbers) >= 3:
                # Suponemos que el número más grande es el año si tiene 4 dígitos
                potential_year = max([int(n) for n in numbers if len(n) == 4], default=None)
                
                if potential_year and 2000 <= potential_year <= 2100:
                    # Encontramos un año válido, buscar otros números para mes y día
                    # Encontramos un año válido, buscar otros números para mes y día
                    other_numbers = [int(n) for n in numbers if int(n) != potential_year]
                    
                    if len(other_numbers) >= 2:
                        # Tomar los dos primeros como mes y día
                        potential_month = min(max(1, other_numbers[0]), 12)  # Asegurar entre 1-12
                        potential_day = min(max(1, other_numbers[1]), 31)    # Asegurar entre 1-31
                        
                        try:
                            return datetime(potential_year, potential_month, potential_day).date()
                        except ValueError:
                            # Si día/mes inválido, usar el 1 como fallback
                            return datetime(potential_year, 1, 1).date()
        except Exception:
            pass
        
        # Si todo falla, devolver la fecha actual
        return today