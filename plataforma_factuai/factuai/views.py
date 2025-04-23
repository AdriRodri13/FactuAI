import os
import json
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import InvoiceDocument, InvoicePage, ExtractedInvoice
from .services import InvoiceProcessor
from .forms import UploadFileForm
from .tasks import process_invoice_task
from plataforma_factuai import settings

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
    top_companies = ExtractedInvoice.objects.values('company').annotate(
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
    companies = ExtractedInvoice.objects.values('company').annotate(
        count=Count('company')
    ).order_by('company')
    
    context = {
        'companies': companies,
    }
    
    return render(request, 'factuai/company_list.html', context)

def company_detail_view(request, company):
    """Vista con detalles de las facturas de una empresa específica"""
    # Obtener años disponibles para esta empresa
    years = ExtractedInvoice.objects.filter(company=company).dates('invoice_date', 'year').order_by('-invoice_date')
    
    # Obtener facturas recientes de esta empresa
    recent_invoices = ExtractedInvoice.objects.filter(company=company).order_by('-invoice_date')[:10]
    
    context = {
        'company': company,
        'years': years,
        'recent_invoices': recent_invoices,
    }
    
    return render(request, 'factuai/company_detail.html', context)

def year_detail_view(request, company, year):
    """Vista con facturas de una empresa en un año específico"""
    # Obtener meses disponibles para esta empresa y año
    months = ExtractedInvoice.objects.filter(
        company=company, 
        invoice_date__year=year
    ).dates('invoice_date', 'month').order_by('-invoice_date')
    
    # Obtener todas las facturas de este año
    invoices = ExtractedInvoice.objects.filter(
        company=company, 
        invoice_date__year=year
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
    # Obtener días con facturas para este mes
    days = ExtractedInvoice.objects.filter(
        company=company, 
        invoice_date__year=year,
        invoice_date__month=month
    ).dates('invoice_date', 'day').order_by('-invoice_date')
    
    # Obtener todas las facturas de este mes
    invoices = ExtractedInvoice.objects.filter(
        company=company, 
        invoice_date__year=year,
        invoice_date__month=month
    ).order_by('-invoice_date')
    
    context = {
        'company': company,
        'year': year,
        'month': month,
        'month_name': datetime(year, month, 1).strftime('%B'),
        'days': days,
        'invoices': invoices,
    }
    
    return render(request, 'factuai/month_detail.html', context)

def day_detail_view(request, company, year, month, day):
    """Vista con facturas de una empresa en un día específico"""
    # Obtener facturas de este día específico
    invoices = ExtractedInvoice.objects.filter(
        company=company, 
        invoice_date__year=year,
        invoice_date__month=month,
        invoice_date__day=day
    ).order_by('-invoice_date')
    
    context = {
        'company': company,
        'year': year,
        'month': month,
        'day': day,
        'date': datetime(year, month, day).strftime('%d de %B de %Y'),
        'invoices': invoices,
    }
    
    return render(request, 'factuai/day_detail.html', context)

def invoice_detail_view(request, invoice_id):
    """Vista detalle de una factura específica"""
    invoice = get_object_or_404(ExtractedInvoice, pk=invoice_id)
    
    context = {
        'invoice': invoice,
        'page': invoice.page,
        'document': invoice.page.invoice,
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