import os
import json
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Q
from django.db.models.functions import ExtractYear, ExtractMonth, ExtractDay
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import InvoiceDocument, InvoicePage, ExtractedInvoice, InvoiceGroup, Empresa
from .services import InvoiceProcessor
from .forms import UploadFileForm
from plataforma_factuai import settings

from django.contrib.auth.decorators import login_required
import shutil
from django.db import transaction
import uuid

@ensure_csrf_cookie
def upload_view(request):
    """Vista principal para subir archivos de facturas"""
    if request.method == 'POST':
        files = request.FILES.getlist('file')
        
        # Validación manual
        if not files:
            messages.error(request, 'No se ha seleccionado ningún archivo.')
            return render(request, 'factuai/upload.html', {'form': UploadFileForm()})
        
        invalid_files = []
        for file in files:
            # Verificar tamaño
            if file.size > settings.MAX_UPLOAD_SIZE:
                invalid_files.append(f'El archivo {file.name} es demasiado grande. Máximo permitido: {settings.MAX_UPLOAD_SIZE/(1024*1024)}MB.')
            
            # Verificar extensión
            ext = os.path.splitext(file.name)[1][1:].lower()
            if ext not in settings.ALLOWED_EXTENSIONS:
                invalid_files.append(f'El formato del archivo {file.name} no está permitido. Formatos válidos: {", ".join(settings.ALLOWED_EXTENSIONS)}')
        
        if invalid_files:
            for msg in invalid_files:
                messages.error(request, msg)
            return render(request, 'factuai/upload.html', {'form': UploadFileForm()})
        
        # Procesar archivos válidos
        uploaded_docs = []
        for file in files:
            # Obtener la extensión del archivo
            extension = os.path.splitext(file.name)[1][1:].lower()
            
            # Crear el documento de factura
            invoice_doc = InvoiceDocument(
                original_filename=file.name,
                file=file,
                file_type=extension
            )
            invoice_doc.save()
            uploaded_docs.append(invoice_doc)
            
            # Procesar documento directamente
            try:
                processor = InvoiceProcessor()
                processor.process_invoice_document(invoice_doc)
            except Exception as e:
                # Registrar el error y continuar con el siguiente archivo
                invoice_doc.processing_error = str(e)
                invoice_doc.save()
        
        messages.success(request, f'Se han subido {len(uploaded_docs)} archivos correctamente.')
        return redirect('factuai:dashboard')
    else:
        # GET request
        form = UploadFileForm()
    
    return render(request, 'factuai/upload.html', {'form': form})

def dashboard_view(request):
    """Vista de dashboard con resumen de facturas procesadas"""
    # Obtener documentos subidos recientemente
    recent_documents = InvoiceDocument.objects.all().order_by('-upload_date')[:10]
    
    # Obtener estadísticas
    total_documents = InvoiceDocument.objects.count()
    processed_documents = InvoiceDocument.objects.filter(processed=True).count()
    error_documents = InvoiceDocument.objects.exclude(processing_error=None).count()
    total_pages = InvoicePage.objects.count()
    
    # Obtener empresas más frecuentes
    top_empresas = Empresa.objects.annotate(
        facturas_count=Count('facturas')
    ).order_by('-facturas_count')[:5]
    
    # Facturas pendientes de asignación
    facturas_pendientes = InvoiceGroup.objects.filter(
        empresa__isnull=True, 
        necesita_revision=True
    ).count()
    
    context = {
        'recent_documents': recent_documents,
        'total_documents': total_documents,
        'processed_documents': processed_documents,
        'error_documents': error_documents,
        'total_pages': total_pages,
        'top_empresas': top_empresas,
        'facturas_pendientes': facturas_pendientes,
    }
    
    return render(request, 'factuai/dashboard.html', context)

def empresa_list_view(request):
    """Vista para listar y gestionar empresas"""
    # Obtener todas las empresas con conteo de facturas
    empresas = Empresa.objects.annotate(
        facturas_count=Count('facturas')
    ).order_by('nombre')
    
    # Obtener facturas pendientes de asignación
    facturas_pendientes = InvoiceGroup.objects.filter(
        empresa__isnull=True, 
        necesita_revision=True
    ).count()
    
    context = {
        'empresas': empresas,
        'facturas_pendientes': facturas_pendientes,
    }
    
    return render(request, 'factuai/empresa_list.html', context)

def empresa_facturas_view(request, empresa_id):
    """Vista de detalle de una empresa"""
    # Obtener la empresa por su ID
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    
    # Obtener años disponibles para esta empresa usando valores distintos
    years_query = InvoiceGroup.objects.filter(empresa=empresa)
    years_query = years_query.annotate(year=ExtractYear('invoice_date'))
    years_query = years_query.values('year').distinct().order_by('-year')
    
    # Convertir a objetos datetime para mantener compatibilidad con el template
    from datetime import datetime
    years = [datetime(year=year['year'], month=1, day=1) for year in years_query]
    
    # Obtener todas las facturas de esta empresa para paginación
    facturas = InvoiceGroup.objects.filter(empresa=empresa).order_by('-invoice_date')
    
    # Paginar resultados
    paginator = Paginator(facturas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'empresa': empresa,
        'years': years,
        'page_obj': page_obj,
    }
    
    return render(request, 'factuai/empresa_facturas.html', context)

def year_detail_view(request, empresa_nombre, year):
    """Vista con facturas de una empresa en un año específico"""
    # Convertir el año a entero para asegurar consistencia
    year_int = int(year)
    
    # Buscar empresa por nombre
    empresa = get_object_or_404(Empresa, nombre=empresa_nombre)
    
    # Obtener meses disponibles para esta empresa y año
    months_query = InvoiceGroup.objects.filter(
        empresa=empresa, 
        invoice_date__year=year_int
    )
    months_query = months_query.annotate(month=ExtractMonth('invoice_date'))
    months_query = months_query.values('month').distinct().order_by('-month')
    
    # Convertir a objetos datetime para mantener compatibilidad con el template
    from datetime import datetime
    months = [datetime(year=year_int, month=month['month'], day=1) for month in months_query]
    
    # Obtener todas las facturas de este año
    invoices = InvoiceGroup.objects.filter(
        empresa=empresa, 
        invoice_date__year=year_int
    ).order_by('-invoice_date')
    
    # Paginar resultados
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'empresa': empresa,
        'year': year,
        'months': months,
        'page_obj': page_obj,
    }
    
    return render(request, 'factuai/year_detail.html', context)

def month_detail_view(request, empresa_nombre, year, month):
    """Vista con facturas de una empresa en un mes específico"""
    # Convertir el año y mes a enteros para asegurar consistencia
    year_int = int(year)
    month_int = int(month)
    
    # Buscar empresa por nombre
    empresa = get_object_or_404(Empresa, nombre=empresa_nombre)
    
    # Obtener días con facturas para este mes
    days_query = InvoiceGroup.objects.filter(
        empresa=empresa, 
        invoice_date__year=year_int,
        invoice_date__month=month_int
    )
    days_query = days_query.annotate(day=ExtractDay('invoice_date'))
    days_query = days_query.values('day').distinct().order_by('-day')
    
    # Convertir a objetos datetime para mantener compatibilidad con el template
    days = []
    for day_item in days_query:
        try:
            days.append(datetime(year=year_int, month=month_int, day=day_item['day']))
        except ValueError:
            # Ignorar días inválidos
            continue
    
    # Obtener todas las facturas de este mes
    invoices = InvoiceGroup.objects.filter(
        empresa=empresa, 
        invoice_date__year=year_int,
        invoice_date__month=month_int
    ).order_by('-invoice_date')
    
    # Obtener el nombre del mes
    month_name = datetime(year_int, month_int, 1).strftime('%B')
    
    context = {
        'empresa': empresa,
        'year': year,
        'month': month,
        'month_name': month_name,
        'days': days,
        'invoices': invoices,
    }
    
    return render(request, 'factuai/month_detail.html', context)

def day_detail_view(request, empresa_nombre, year, month, day):
    """Vista con facturas de una empresa en un día específico"""
    # Convertir a enteros
    year_int = int(year)
    month_int = int(month)
    day_int = int(day)
    
    # Buscar empresa por nombre
    empresa = get_object_or_404(Empresa, nombre=empresa_nombre)
    
    # Obtener facturas de este día específico
    invoices = InvoiceGroup.objects.filter(
        empresa=empresa, 
        invoice_date__year=year_int,
        invoice_date__month=month_int,
        invoice_date__day=day_int
    ).order_by('-invoice_date')
    
    context = {
        'empresa': empresa,
        'year': year,
        'month': month,
        'day': day,
        'date': datetime(year_int, month_int, day_int).strftime('%d de %B de %Y'),
        'invoices': invoices,
    }
    
    return render(request, 'factuai/day_detail.html', context)

def invoice_detail_view(request, invoice_id):
    """Vista detalle de una factura"""
    # Buscar primero en InvoiceGroup
    try:
        invoice_group = get_object_or_404(InvoiceGroup, pk=invoice_id)
        
        # Obtener todas las páginas de esta factura
        invoice_pages = invoice_group.extracted_invoices.all().order_by('page__page_number')
        
        # Obtener la primera página para mostrar detalles
        first_invoice = invoice_pages.first()
        
        # Obtener la empresa asociada
        empresa = invoice_group.empresa
        
        # Obtener todas las empresas disponibles para selección
        empresas_disponibles = Empresa.objects.all().order_by('nombre')
        
        context = {
            'invoice_group': invoice_group,
            'invoice': first_invoice,
            'invoice_pages': invoice_pages,
            'page': first_invoice.page if first_invoice else None,
            'document': first_invoice.page.invoice if first_invoice else None,
            'is_grouped': True,
            'pages_count': invoice_pages.count(),
            'empresa': empresa,
            'empresas_disponibles': empresas_disponibles
        }
        
        return render(request, 'factuai/invoice_detail.html', context)
        
    except:
        # Si no se encuentra el grupo, buscar en ExtractedInvoice (para compatibilidad)
        invoice = get_object_or_404(ExtractedInvoice, pk=invoice_id)
        
        # Verificar si pertenece a un grupo
        if invoice.group:
            # Redirigir a la vista del grupo
            return redirect('factuai:invoice_detail', invoice_id=invoice.group.id)
        
        # Intentar encontrar la empresa
        empresa = None
        if invoice.group and invoice.group.empresa:
            empresa = invoice.group.empresa
        else:
            # Buscar por nombre de empresa
            empresa_obj = Empresa.buscar_por_nombre(invoice.company)
            if empresa_obj:
                empresa = empresa_obj
        
        # Obtener todas las empresas disponibles para selección
        empresas_disponibles = Empresa.objects.all().order_by('nombre')
        
        context = {
            'invoice': invoice,
            'page': invoice.page,
            'document': invoice.page.invoice,
            'is_grouped': False,
            'pages_count': 1,
            'empresa': empresa,
            'empresas_disponibles': empresas_disponibles
        }
        
        return render(request, 'factuai/invoice_detail.html', context)

def invoice_page_view(request, invoice_id, page_number):
    """Vista para mostrar una página específica de una factura agrupada"""
    invoice_group = get_object_or_404(InvoiceGroup, pk=invoice_id)
    
    # Obtener la página específica
    try:
        invoice_page = invoice_group.extracted_invoices.filter(
            page__page_number=page_number
        ).first()
    except:
        # Si no se encuentra la página, obtener la primera
        invoice_page = invoice_group.extracted_invoices.order_by('page__page_number').first()
    
    if not invoice_page:
        messages.error(request, "No se encontró la página solicitada")
        return redirect('factuai:invoice_detail', invoice_id=invoice_id)
    
    # Obtener todas las páginas para navegación
    invoice_pages = invoice_group.extracted_invoices.all().order_by('page__page_number')
    
    context = {
        'invoice_group': invoice_group,
        'invoice': invoice_page,
        'invoice_pages': invoice_pages,
        'page': invoice_page.page,
        'document': invoice_page.page.invoice,
        'is_grouped': True,
        'pages_count': invoice_pages.count(),
        'current_page': page_number
    }
    
    return render(request, 'factuai/invoice_detail.html', context)

@require_POST
def process_status_view(request):
    """API interna para consultar estado de procesamiento de un documento"""
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        
        if not document_id:
            return JsonResponse({'error': 'ID de documento no proporcionado'}, status=400)
        
        document = get_object_or_404(InvoiceDocument, pk=document_id)
        
        # Obtener información de páginas procesadas
        total_pages = InvoicePage.objects.filter(invoice=document).count()
        processed_pages = InvoicePage.objects.filter(invoice=document, processed=True).count()
        
        response_data = {
            'id': str(document.id),
            'processed': document.processed,
            'error': document.processing_error,
            'total_pages': total_pages,
            'processed_pages': processed_pages,
            'progress': int(processed_pages / max(total_pages, 1) * 100) if total_pages > 0 else 0
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
def process_extracted_invoice(request):
    """API para procesar y agrupar las facturas extraídas"""
    try:
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id')
        
        if not invoice_id:
            return JsonResponse({'error': 'ID de factura no proporcionado'}, status=400)
        
        invoice = get_object_or_404(ExtractedInvoice, pk=invoice_id)
        
        # Crear o obtener grupo de facturas
        invoice_group, created = InvoiceGroup.objects.get_or_create(
            company=invoice.company,
            invoice_number=invoice.invoice_number,
            defaults={
                'invoice_date': invoice.invoice_date
            }
        )
        
        # Asociar factura al grupo
        invoice.group = invoice_group
        invoice.save()
        
        return JsonResponse({
            'success': True,
            'group_id': str(invoice_group.id),
            'created': created
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def eliminar_todos_datos(request):
    """Vista simple para eliminar todos los datos de facturas"""
    if request.method == 'GET':
        try:
            with transaction.atomic():
                # Eliminar todos los registros en orden inverso de dependencia
                ExtractedInvoice.objects.all().delete()
                InvoiceGroup.objects.all().delete()  # Añadir eliminación de grupos
                InvoicePage.objects.all().delete()
                InvoiceDocument.objects.all().delete()
                
                # Eliminar directorios físicos
                media_root = settings.MEDIA_ROOT
                directorio_facturas = os.path.join(media_root, 'invoices')
                directorio_paginas = os.path.join(media_root, 'invoice_pages')
                
                if os.path.exists(directorio_facturas):
                    shutil.rmtree(directorio_facturas)
                
                if os.path.exists(directorio_paginas):
                    shutil.rmtree(directorio_paginas)
                
                messages.success(request, 'Todos los datos han sido eliminados correctamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar datos: {str(e)}')
        
        return redirect('factuai:dashboard')
    
    # Si es GET, mostrar página de confirmación
    return render(request, 'factuai/eliminar_datos.html')

# views.py (añadir al final)

def empresa_list_view(request):
    """Vista para listar y gestionar empresas"""
    empresas = Empresa.objects.all().order_by('nombre')
    
    # Obtener facturas pendientes de asignación
    facturas_pendientes = InvoiceGroup.objects.filter(
        empresa__isnull=True, 
        necesita_revision=True
    ).order_by('-invoice_date')[:10]
    
    context = {
        'empresas': empresas,
        'facturas_pendientes': facturas_pendientes,
    }
    
    return render(request, 'factuai/empresa_list.html', context)

def empresa_detail_view(request, empresa_id):
    """Vista de detalle de una empresa"""
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    
    # Obtener facturas de esta empresa
    facturas = InvoiceGroup.objects.filter(empresa=empresa).order_by('-invoice_date')
    
    # Obtener años disponibles a partir de las fechas de facturas
    years = facturas.dates('invoice_date', 'year', order='DESC').distinct()
    
    # Paginar resultados
    paginator = Paginator(facturas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'empresa': empresa,
        'page_obj': page_obj,
        'years': years,  # Añadir los años al contexto
    }
    
    return render(request, 'factuai/empresa_detail.html', context)

@require_POST
def empresa_create_view(request):
    """Vista para crear una nueva empresa"""
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre', '').strip()
        
        if not nombre:
            return JsonResponse({'error': 'El nombre de la empresa es obligatorio'}, status=400)
        
        # Verificar si ya existe
        empresa_existente = Empresa.objects.filter(nombre__iexact=nombre).first()
        if empresa_existente:
            return JsonResponse({'error': 'Ya existe una empresa con este nombre'}, status=400)
        
        # Crear empresa
        empresa = Empresa.objects.create(
            nombre=nombre,
            nif=data.get('nif', ''),
            direccion=data.get('direccion', ''),
            telefono=data.get('telefono', ''),
            email=data.get('email', '')
        )
        
        return JsonResponse({
            'success': True,
            'id': str(empresa.id),
            'nombre': empresa.nombre
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

import traceback

@require_POST
def asignar_empresa_factura(request):
    """Vista para asignar una empresa a facturas, gestionando múltiples páginas de la misma factura"""
    try:
        data = json.loads(request.body)
        factura_ids = data.get('factura_id')
        empresa_id = data.get('empresa_id')
        
        # Convertir a lista si es un solo ID
        if not isinstance(factura_ids, list):
            factura_ids = [factura_ids]
        
        if not factura_ids or not empresa_id:
            return JsonResponse({'error': 'Factura y Empresa son obligatorios'}, status=400)
        
        # Obtener empresa
        try:
            empresa = Empresa.objects.get(pk=empresa_id)
        except Empresa.DoesNotExist:
            return JsonResponse({'error': f'Empresa con ID {empresa_id} no encontrada'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Error al buscar empresa: {str(e)}'}, status=500)
        
        # Procesar todas las facturas
        processed_count = 0
        errors = []
        
        # 1. Primero, agrupamos los InvoiceGroup por número de factura
        facturas_por_numero = {}
        
        for factura_id in factura_ids:
            try:
                # Convertir el ID a UUID si es string
                if isinstance(factura_id, str):
                    try:
                        factura_id_uuid = uuid.UUID(factura_id)
                    except ValueError:
                        errors.append(f"ID de factura no es un UUID válido: {factura_id}")
                        continue
                else:
                    factura_id_uuid = factura_id
                
                # Obtener factura
                factura = InvoiceGroup.objects.get(pk=factura_id_uuid)
                
                # Agrupar por número de factura
                num_factura = factura.invoice_number
                if num_factura not in facturas_por_numero:
                    facturas_por_numero[num_factura] = []
                
                facturas_por_numero[num_factura].append(factura)
                
            except InvoiceGroup.DoesNotExist:
                errors.append(f"Factura con ID {factura_id} no encontrada")
                continue
            except Exception as e:
                errors.append(f"Error general al procesar factura ID {factura_id}: {str(e)}")
                continue
        
        # 2. Ahora procesamos cada grupo de facturas con el mismo número
        for num_factura, facturas_grupo in facturas_por_numero.items():
            try:
                # Verificar si ya existe una factura con este número para esta empresa
                existing_factura = InvoiceGroup.objects.filter(
                    empresa=empresa, 
                    invoice_number=num_factura
                ).first()
                
                if existing_factura:
                    # Para todas las facturas de este grupo, necesitamos:
                    # 1. Reasignar sus ExtractedInvoice al grupo existente
                    # 2. Eliminar los grupos vacíos
                    for factura in facturas_grupo:
                        # Registrar el nombre detectado para mejorar OCR futuro
                        if factura.company:
                            empresa.add_nombre_detectado(factura.company)
                        
                        # Reasignar todos los ExtractedInvoice a la factura existente
                        for extracted in factura.extracted_invoices.all():
                            extracted.group = existing_factura
                            extracted.save()
                        
                        # Si estaba vacía (todos los extractos reasignados), eliminarla
                        if factura.extracted_invoices.count() == 0:
                            factura.delete()
                        
                        processed_count += 1
                    
                else:
                    # Tomar la primera factura del grupo y asignarle la empresa
                    primera_factura = facturas_grupo[0]
                    
                    # Guardar nombre detectado
                    if primera_factura.company:
                        empresa.add_nombre_detectado(primera_factura.company)
                    
                    # Asignar empresa
                    primera_factura.empresa = empresa
                    primera_factura.necesita_revision = False
                    primera_factura.save()
                    
                    processed_count += 1
                    
                    # Si hay más facturas en el grupo, reasignar sus extractos
                    if len(facturas_grupo) > 1:
                        for factura in facturas_grupo[1:]:
                            # Guardar nombre detectado
                            if factura.company:
                                empresa.add_nombre_detectado(factura.company)
                            
                            # Reasignar todos los ExtractedInvoice a la primera factura
                            for extracted in factura.extracted_invoices.all():
                                extracted.group = primera_factura
                                extracted.save()
                            
                            # Si estaba vacía (todos los extractos reasignados), eliminarla
                            if factura.extracted_invoices.count() == 0:
                                factura.delete()
                            
                            processed_count += 1
            
            except Exception as e:
                errors.append(f"Error procesando grupo de facturas {num_factura}: {str(e)}")
                continue
        
        # Preparar respuesta
        if processed_count > 0:
            response_data = {
                'success': True,
                'empresa_nombre': empresa.nombre,
                'processed_count': processed_count,
                'total_count': len(factura_ids)
            }
            
            if errors:
                response_data['partial_success'] = True
                response_data['errors'] = errors
            
            return JsonResponse(response_data)
        else:
            error_response = {
                'success': False,
                'error': 'No se pudo asignar ninguna factura',
                'errors': errors
            }
            return JsonResponse(error_response, status=400)
        
    except json.JSONDecodeError as e:
        return JsonResponse({'error': f'Error al decodificar JSON: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error general: {str(e)}'}, status=500)

def facturas_pendientes_view(request):
    """Vista para mostrar facturas pendientes de asignación de empresa"""
    # Obtener facturas pendientes
    facturas_pendientes = InvoiceGroup.objects.filter(
        empresa__isnull=True,
        necesita_revision=True
    ).order_by('-invoice_date')
    
    # Agrupar por número de factura
    facturas_agrupadas = {}
    for factura in facturas_pendientes:
        if factura.invoice_number in facturas_agrupadas:
            # Si ya existe una factura con este número, la agregamos a la lista
            facturas_agrupadas[factura.invoice_number]['items'].append(factura)
        else:
            # Si es la primera factura con este número, creamos la entrada
            facturas_agrupadas[factura.invoice_number] = {
                'items': [factura],
                'count': 1,
                # Usamos la primera factura como representante del grupo
                'representative': factura
            }
    
    # Convertir el diccionario agrupado a una lista para la plantilla
    facturas = []
    for numero, grupo in facturas_agrupadas.items():
        # Tomamos la primera factura como representativa del grupo
        factura_rep = grupo['representative']
        # Añadimos la cantidad de facturas con el mismo número
        factura_rep.duplicates_count = len(grupo['items'])
        # Añadimos los IDs de todas las facturas del grupo
        factura_rep.all_ids = [str(f.id) for f in grupo['items']]
        facturas.append(factura_rep)
    
    # Obtener todas las empresas para el selector
    empresas = Empresa.objects.all().order_by('nombre')
    
    context = {
        'facturas': facturas,
        'empresas': empresas,
    }
    
    return render(request, 'factuai/facturas_pendientes.html', context)

#EMPRESAS
def detalle_empresa(request, empresa_id):
    empresa = get_object_or_404(Empresa, id = empresa_id)
    return render(request, "factuai/empresas/detalle.html", {"empresa":empresa})

@require_POST
def actualizar_empresa(request, empresa_id):
    """Vista para actualizar los datos de una empresa"""
    try:
        empresa = get_object_or_404(Empresa, id=empresa_id)
        data = json.loads(request.body)
        
        # Actualizar campos
        empresa.nombre = data.get('nombre', empresa.nombre)
        empresa.nif = data.get('nif', empresa.nif)
        empresa.direccion = data.get('direccion', empresa.direccion)
        empresa.telefono = data.get('telefono', empresa.telefono)
        empresa.email = data.get('email', empresa.email)
        
        # Guardar cambios
        empresa.save()
        
        # Preparar datos para la respuesta
        empresa_data = {
            'id': str(empresa.id),
            'nombre': empresa.nombre,
            'nif': empresa.nif,
            'direccion': empresa.direccion,
            'telefono': empresa.telefono,
            'email': empresa.email,
            'fecha_actualizacion': empresa.fecha_actualizacion.isoformat()
        }
        
        return JsonResponse({
            'success': True,
            'empresa': empresa_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@require_POST
def eliminar_empresa(request, empresa_id):
    """Vista para eliminar una empresa"""
    try:
        empresa = get_object_or_404(Empresa, id=empresa_id)
        nombre = empresa.nombre
        
        # Eliminar la empresa
        empresa.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Empresa {nombre} eliminada correctamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)