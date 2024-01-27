
from . import views
from django.urls import path
from .views import *
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('api/crop-pdf/flipkart/', PDFCropAPIView.as_view(), name='crop-pdf-api'),
    path('api/download-cropped-pdf/<str:file_name>/', DownloadCroppedPDF.as_view(), name='download-cropped-pdf'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# For serving static files during development
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)