from django import forms
from .models import UploadedPDF2

class UploadPDFForm(forms.ModelForm):
    class Meta:
        model = UploadedPDF2
        fields = ('pdf_file',)

class CropForm(forms.Form):
    x = forms.FloatField()
    y = forms.FloatField()
    width = forms.FloatField()
    height = forms.FloatField()
