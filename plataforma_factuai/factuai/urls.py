from django.urls import path
from . import views

app_name = 'factuai'

urlpatterns = [
    # Página principal para subir documentos
    path('', views.upload_view, name='upload'),
    
    # Vista de dashboard/listado de facturas
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Vistas para navegación por categorías
    path('companies/', views.company_list_view, name='company_list'),
    path('companies/<str:company>/', views.company_detail_view, name='company_detail'),
    path('companies/<str:company>/<int:year>/', views.year_detail_view, name='year_detail'),
    path('companies/<str:company>/<int:year>/<int:month>/', views.month_detail_view, name='month_detail'),
    path('companies/<str:company>/<int:year>/<int:month>/<int:day>/', views.day_detail_view, name='day_detail'),
    
    # Vista detalle de factura específica
    path('invoice/<uuid:invoice_id>/', views.invoice_detail_view, name='invoice_detail'),
    
    # API interna para actualizar estado del procesamiento (AJAX)
    path('api/process-status/', views.process_status_view, name='process_status'),
]