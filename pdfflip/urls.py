
from . import views
from django.urls import path
from .views import PDFCropAPIView,ExtractPDFData
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    # path('flipkart',views.upload_pdf)
    path('api/crop-pdf/', PDFCropAPIView.as_view(), name='crop-pdf-api'),
    path('api/dict/', ExtractPDFData.as_view(), name='crop-pdf-api'),
    # path('download-pdf/<str:file_path>/', views.download_pdf, name='download-pdf'), 
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# For serving static files during development
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)