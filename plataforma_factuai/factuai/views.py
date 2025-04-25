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

from .models import InvoiceDocument, InvoicePage, ExtractedInvoice, InvoiceGroup
from .services import InvoiceProcessor
from .forms import UploadFileForm
from .tasks import process_invoice_task
from plataforma_factuai import settings

from django.contrib.auth.decorators import login_required
import shutil
from django.db import transaction

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
    
    # Obtener empresas más frecuentes (ahora usando InvoiceGroup)
    top_companies = InvoiceGroup.objects.values('company').annotate(
        count=Count('company')
    ).order_by('-count')[:5]
    
    context = {
        'recent_documents': recent_documents,
        'total_documents': total_documents,
        'processed_documents': processed_documents,
        'error_documents': error_documents,
        'total_pages': total_pages,
        'top_companies': top_companies,
    }
    
    return render(request, 'factuai/dashboard.html', context)

def company_list_view(request):
    """Vista para listar todas las empresas con facturas"""
    # Ahora usamos InvoiceGroup para contar facturas únicas, no páginas
    companies = InvoiceGroup.objects.values('company').annotate(
        count=Count('id')
    ).order_by('company')
    
    context = {
        'companies': companies,
    }
    
    return render(request, 'factuai/company_list.html', context)

def company_detail_view(request, company):
    """Vista con detalles de las facturas de una empresa específica"""
    # Obtener años disponibles para esta empresa usando valores distintos
    years_query = InvoiceGroup.objects.filter(company=company)
    years_query = years_query.annotate(year=ExtractYear('invoice_date'))
    years_query = years_query.values('year').distinct().order_by('-year')
    
    # Convertir a objetos datetime para mantener compatibilidad con el template
    from datetime import datetime
    years = [datetime(year=year['year'], month=1, day=1) for year in years_query]
    
    # Obtener facturas recientes de esta empresa
    recent_invoices = InvoiceGroup.objects.filter(company=company).order_by('-invoice_date')[:10]
    
    context = {
        'company': company,
        'years': years,
        'recent_invoices': recent_invoices,
    }
    
    return render(request, 'factuai/company_detail.html', context)

def year_detail_view(request, company, year):
    """Vista con facturas de una empresa en un año específico"""
    # Convertir el año a entero para asegurar consistencia
    year_int = int(year)
    
    # Obtener meses disponibles para esta empresa y año
    months_query = InvoiceGroup.objects.filter(
        company=company, 
        invoice_date__year=year_int
    )
    months_query = months_query.annotate(month=ExtractMonth('invoice_date'))
    months_query = months_query.values('month').distinct().order_by('-month')
    
    # Convertir a objetos datetime para mantener compatibilidad con el template
    from datetime import datetime
    months = [datetime(year=year_int, month=month['month'], day=1) for month in months_query]
    
    # Obtener todas las facturas de este año
    invoices = InvoiceGroup.objects.filter(
        company=company, 
        invoice_date__year=year_int
    ).order_by('-invoice_date')
    
    # Paginar resultados
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'company': company,
        'year': year,
        'months': months,
        'page_obj': page_obj,
    }
    
    return render(request, 'factuai/year_detail.html', context)

def month_detail_view(request, company, year, month):
    """Vista con facturas de una empresa en un mes específico"""
    # Convertir el año y mes a enteros para asegurar consistencia
    year_int = int(year)
    month_int = int(month)
    
    # Obtener días con facturas para este mes
    days_query = InvoiceGroup.objects.filter(
        company=company, 
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
        company=company, 
        invoice_date__year=year_int,
        invoice_date__month=month_int
    ).order_by('-invoice_date')
    
    # Obtener el nombre del mes
    month_name = datetime(year_int, month_int, 1).strftime('%B')
    
    context = {
        'company': company,
        'year': year,
        'month': month,
        'month_name': month_name,
        'days': days,
        'invoices': invoices,
    }
    
    return render(request, 'factuai/month_detail.html', context)

def day_detail_view(request, company, year, month, day):
    """Vista con facturas de una empresa en un día específico"""
    # Convertir a enteros
    year_int = int(year)
    month_int = int(month)
    day_int = int(day)
    
    # Obtener facturas de este día específico
    invoices = InvoiceGroup.objects.filter(
        company=company, 
        invoice_date__year=year_int,
        invoice_date__month=month_int,
        invoice_date__day=day_int
    ).order_by('-invoice_date')
    
    context = {
        'company': company,
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
        
        context = {
            'invoice_group': invoice_group,
            'invoice': first_invoice,
            'invoice_pages': invoice_pages,
            'page': first_invoice.page if first_invoice else None,
            'document': first_invoice.page.invoice if first_invoice else None,
            'is_grouped': True,
            'pages_count': invoice_pages.count()
        }
        
        return render(request, 'factuai/invoice_detail.html', context)
        
    except:
        # Si no se encuentra el grupo, buscar en ExtractedInvoice (para compatibilidad)
        invoice = get_object_or_404(ExtractedInvoice, pk=invoice_id)
        
        # Verificar si pertenece a un grupo
        if invoice.group:
            # Redirigir a la vista del grupo
            return redirect('factuai:invoice_detail', invoice_id=invoice.group.id)
        
        context = {
            'invoice': invoice,
            'page': invoice.page,
            'document': invoice.page.invoice,
            'is_grouped': False,
            'pages_count': 1
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