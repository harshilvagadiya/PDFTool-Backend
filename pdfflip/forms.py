from django import forms
from .models import UploadedPDF

class UploadPDFForm(forms.ModelForm):
    class Meta:
        model = UploadedPDF
        fields = ('pdf_file',)

class CropForm(forms.Form):
    x = forms.FloatField()
    y = forms.FloatField()
    width = forms.FloatField()
    height = forms.FloatField()
