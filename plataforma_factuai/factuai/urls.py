from django.urls import path
from . import views

app_name = 'factuai'

urlpatterns = [
    # Página principal para subir documentos
    path('', views.upload_view, name='upload'),
    
    # Vista de dashboard/listado de facturas
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Vistas para navegación por categorías
    path('empresa/<str:empresa_nombre>/<int:year>/', views.year_detail_view, name='year_detail'),
    path('empresa/<str:empresa_nombre>/<int:year>/<int:month>/', views.month_detail_view, name='month_detail'),
    path('empresa/<str:empresa_nombre>/<int:year>/<int:month>/<int:day>/', views.day_detail_view, name='day_detail'),
    
    # Vista detalle de factura específica
    path('invoice/<uuid:invoice_id>/', views.invoice_detail_view, name='invoice_detail'),
    
    # API interna para actualizar estado del procesamiento (AJAX)
    path('api/process-status/', views.process_status_view, name='process_status'),
    
    # Vista de acciones
    path('dashboard/borrar/', views.eliminar_todos_datos, name='delete_invoices'),
    
    path('invoice/<uuid:invoice_id>/page/<int:page_number>/', views.invoice_page_view, name='invoice_page'),
    path('api/process-invoice/', views.process_extracted_invoice, name='process_invoice'),
    
    # NUEVAS RUTAS PARA EMPRESAS
    path('empresas/', views.empresa_list_view, name='empresa_list'),
    path('empresas/<uuid:empresa_id>/', views.empresa_facturas_view, name='empresa_facturas'),
    path('empresas/create/', views.empresa_create_view, name='empresa_create'),
    path('facturas/pendientes/', views.facturas_pendientes_view, name='facturas_pendientes'),
    path('facturas/asignar-empresa/', views.asignar_empresa_factura, name='asignar_empresa'),
    
    #EMPRESAS
    path('empresa/<uuid:empresa_id>/', views.detalle_empresa, name='empresa_detalle'),
    path('empresa/actualizar/<uuid:empresa_id>/', views.actualizar_empresa, name='empresa_update'),
    path('empresa/eliminar/<uuid:empresa_id>/', views.eliminar_empresa, name='empresa_delete'),
]