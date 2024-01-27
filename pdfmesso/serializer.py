from rest_framework import serializers
from .models import UploadedPDF2

class UploadedPDFSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedPDF2
        fields = '__all__'

        
from .models import ExtractedData2

class ExtractedDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractedData2
        fields = ('key', 'value')