from django.db import models

class UploadedPDF(models.Model):
    pdf_file = models.FileField(upload_to='uploads/')


class ExtractedData(models.Model):
    key = models.CharField(max_length=255)
    value = models.TextField()