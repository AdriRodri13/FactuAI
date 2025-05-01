from django.urls import path
from extractor.views import VistaExtraccionDatos

urlpatterns = [
    path('extraer/', VistaExtraccionDatos.as_view(), name='data-extractor'),
]