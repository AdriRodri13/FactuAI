from django.urls import path
from .views import OCRProcessView, OCRBatchProcessView, ModelReloadView

urlpatterns = [
    path('process/', OCRProcessView.as_view(), name='ocr-process'),
    path('process-batch/', OCRBatchProcessView.as_view(), name='ocr-batch-process'),
    path('reload-model/', ModelReloadView.as_view(), name='reload-model'),
]