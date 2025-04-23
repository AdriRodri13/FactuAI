from django.contrib import admin
from django.utils.html import format_html
from .models import InvoiceDocument, InvoicePage, ExtractedInvoice

class InvoicePageInline(admin.TabularInline):
    model = InvoicePage
    extra = 0
    readonly_fields = ['preview_image', 'processed']
    fields = ['page_number', 'preview_image', 'processed']
    
    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.image.url)
        return "Sin imagen"
    
    preview_image.short_description = "Vista previa"

@admin.register(InvoiceDocument)
class InvoiceDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_filename', 'file_type', 'upload_date', 'processed', 'has_error']
    list_filter = ['processed', 'file_type', 'upload_date']
    search_fields = ['original_filename']
    date_hierarchy = 'upload_date'
    readonly_fields = ['preview_file', 'upload_date', 'processed']
    inlines = [InvoicePageInline]
    
    def preview_file(self, obj):
        if obj.file:
            if obj.file_type in ['jpg', 'jpeg', 'png']:
                return format_html('<img src="{}" width="200" />', obj.file.url)
            return format_html('<a href="{}" target="_blank">Ver archivo original</a>', obj.file.url)
        return "Sin archivo"
    
    def has_error(self, obj):
        if obj.processing_error:
            return format_html('<span style="color: red;">Sí</span>')
        return format_html('<span style="color: green;">No</span>')
    
    preview_file.short_description = "Vista previa"
    has_error.short_description = "Error"

class ExtractedInvoiceInline(admin.StackedInline):
    model = ExtractedInvoice
    extra = 0
    readonly_fields = ['company', 'invoice_number', 'invoice_date', 'raw_data_formatted']
    fields = ['company', 'invoice_number', 'invoice_date', 'raw_data_formatted']
    
    def raw_data_formatted(self, obj):
        if obj.raw_data:
            import json
            formatted = json.dumps(obj.raw_data, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        return "Sin datos"
    
    raw_data_formatted.short_description = "Datos extraídos"

@admin.register(InvoicePage)
class InvoicePageAdmin(admin.ModelAdmin):
    list_display = ['id', 'invoice_link', 'page_number', 'preview_image', 'processed']
    list_filter = ['processed', 'invoice__file_type']
    search_fields = ['invoice__original_filename', 'ocr_text']
    readonly_fields = ['preview_image', 'ocr_text_formatted']
    inlines = [ExtractedInvoiceInline]
    
    def invoice_link(self, obj):
        return format_html('<a href="{}">{}</a>', 
                          f'/admin/factuai/invoicedocument/{obj.invoice.id}/change/',
                          obj.invoice.original_filename)
    
    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.image.url)
        return "Sin imagen"
    
    def ocr_text_formatted(self, obj):
        if obj.ocr_text:
            return format_html('<pre style="max-height: 300px; overflow-y: auto;">{}</pre>', obj.ocr_text)
        return "Sin texto OCR"
    
    invoice_link.short_description = "Documento"
    preview_image.short_description = "Vista previa"
    ocr_text_formatted.short_description = "Texto OCR"

@admin.register(ExtractedInvoice)
class ExtractedInvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'company', 'invoice_number', 'invoice_date', 'page_link', 'created_at']
    list_filter = ['company', 'invoice_date', 'created_at']
    search_fields = ['company', 'invoice_number', 'page__invoice__original_filename']
    date_hierarchy = 'invoice_date'
    readonly_fields = ['page_preview', 'raw_data_formatted']
    
    def page_link(self, obj):
        return format_html('<a href="{}">{} (Pág. {})</a>', 
                          f'/admin/factuai/invoicepage/{obj.page.id}/change/',
                          obj.page.invoice.original_filename,
                          obj.page.page_number)
    
    def page_preview(self, obj):
        if obj.page and obj.page.image:
            return format_html('<img src="{}" width="300" />', obj.page.image.url)
        return "Sin imagen"
    
    def raw_data_formatted(self, obj):
        if obj.raw_data:
            import json
            formatted = json.dumps(obj.raw_data, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        return "Sin datos"
    
    page_link.short_description = "Página"
    page_preview.short_description = "Vista previa"
    raw_data_formatted.short_description = "Datos extraídos"