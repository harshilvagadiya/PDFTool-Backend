import datetime
from PyPDF4 import PdfFileReader, PdfFileWriter
from .serializer import UploadedPDFSerializer
import fitz
import re
from collections import defaultdict
from reportlab.pdfgen import canvas
import os
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from io import BytesIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .forms import CropForm
import uuid

style = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), (1, 1, 1)), 
    ('TEXTCOLOR', (0, 0), (-1, 0), (0, 0, 0)),  
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('BACKGROUND', (0, 1), (-1, -1), (1, 1, 1)),
    ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
    ('SPAN', (0, 0), (-1, 0)),
    ('FONTSIZE', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
])
class PDFCropAPIView(APIView):

    def make_table_header(self, output_list, heading, style):
        output_list.insert(0, [heading])
        temp_buffer = BytesIO()
        temp_canvas = canvas.Canvas(temp_buffer, pagesize=letter)
        table = Table(output_list)
        table.setStyle(style)
        table.wrap(0, 0)
        table_height = table._height - 45
        y_coordinate = letter[1] - table_height - 60
        table.wrapOn(temp_canvas, 0, 0)
        table.drawOn(temp_canvas, 200, y_coordinate)
        return temp_canvas, temp_buffer

    def make_total_table(self, temp_canvas, output_list2, heading, style):
        output_list2.insert(0, [heading])
        table2 = Table(output_list2)
        table2.setStyle(style)
        table2.wrap(0, 0)
        table2_height = table2._height + 230
        y_coordinate2 = letter[1] - table2_height - 60
        table2.wrapOn(temp_canvas, 0, 0)
        table2.drawOn(temp_canvas, 200, y_coordinate2)


    def post(self, request, format=None):
        try:
            sku_names = []
            uploaded_file1 = request.FILES['pdf_file']
            pdf_bytes = uploaded_file1.read()
            pdf_document = fitz.open("pdf", pdf_bytes)
            extracted_data = defaultdict(int)
            pattern = r'Description\nQTY\n1\s+(.*?)\s+'

            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text = page.get_text("text")
                lines = text.split('\n')

                if len(lines) >= 2:
                    first_line = lines[1].strip()
                    unique_first_lines = set()
                    if first_line not in unique_first_lines:
                        unique_first_lines.add(first_line)

                matches = re.findall(pattern, text)
                for match in matches:
                    extracted_data[match] += 1
                sku_names.append((matches[0], page_num))
            pdf_document.close()

            total_items = []
            all_data_values = [{"QTY": value, "SKU": key} for key, value in extracted_data.items()]

            total_order_quantity = 0
            for items in all_data_values:
                order_qty = max(1, items["QTY"])
                total_order_quantity += order_qty

            sublist_limit = 13
            sublists = [all_data_values[i:i + sublist_limit] for i in range(0, len(all_data_values), sublist_limit)]
            sublists[-1].append({"total_order_quantity": f"Total Package: {total_order_quantity}"})
            sublists[0].insert(0, {"QTY": "QTY", "SKU": "SKU"})


            sku_counts = defaultdict(int)
            for sku_name, _ in sku_names:
                sku_counts[sku_name] += 1

            sorted_pages = sorted(
                [(page_num, sku_names[page_num]) for page_num in range(len(sku_names))],
                key=lambda x: (sku_counts[x[1][0]], x[1])  
            )
            sorted_pages = [page_num for page_num, _ in sorted_pages]
            
            total_items.append({"total_order_quantity": total_order_quantity, "courier_partner": f"Courier Partner: {first_line}"})

        except Exception as e:
            raise

        pdf_form = UploadedPDFSerializer(data=request.data)
        crop_form = CropForm(request.data)
        if pdf_form.is_valid() and crop_form.is_valid():
            uploaded_pdf = pdf_form.save()
            pdf_path = uploaded_pdf.pdf_file.path
            x = crop_form.cleaned_data['x']
            y = crop_form.cleaned_data['y']
            width = crop_form.cleaned_data['width']
            height = crop_form.cleaned_data['height']

            pdf_reader = PdfFileReader(pdf_path)
            pdf_writer = PdfFileWriter()
            for page_num in sorted_pages:
                page = pdf_reader.getPage(page_num)
                page.cropBox.upperLeft = (x, y)
                page.cropBox.lowerRight = (x + width, y - height)
                pdf_writer.addPage(page)

            last_index = len(sublists) - 1
            
            for index, pages in enumerate(sublists):
                output_list = [[value for value in page.values()] for page in pages]
                heading = "*" + " "*22 + "This Flipkart label is provided by PDFTool" + " "*22 + "*"
                temp_canvas, temp_buffer = self.make_table_header(output_list, heading, style)

                output_list2 = [[value for value in ti.values()] for ti in total_items]

                if index == last_index:
                    heading = "Courier wise total package"
                    self.make_total_table(temp_canvas, output_list2, heading, style)

                temp_canvas.save()
                temp_buffer.seek(0)
                overlay_pdf = PdfFileReader(temp_buffer)
                overlay_page = overlay_pdf.getPage(0)
                overlay_page.cropBox.upperLeft = (x, y)
                overlay_page.cropBox.lowerRight = (x + width, y - height)
                pdf_writer.addPage(overlay_page)
                output_buffer = BytesIO()
                pdf_writer.write(output_buffer)
                output_buffer.seek(0)

            unique_id = str(uuid.uuid4())[:8]
            output_pdf_path = os.path.join(settings.MEDIA_ROOT, f'output_{unique_id}.pdf')

            with open(output_pdf_path, 'wb') as output_pdf:
                pdf_writer.write(output_pdf)
            os.remove(pdf_path)

            pdf_path = os.path.join(settings.MEDIA_ROOT, output_pdf_path)

            with open(pdf_path, 'wb') as output_pdf:
                pdf_writer.write(output_pdf)

            file_url = os.path.join(settings.MEDIA_URL, output_pdf_path)

            response_data = {
                'message': 'PDF cropped successfully.',
                'file_path': os.path.join(settings.MEDIA_URL, f'output_{unique_id}.pdf'),
                'file_name': f'output_{unique_id}.pdf'
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(pdf_form.errors, status=status.HTTP_400_BAD_REQUEST)

# ====================================================OVER FLIPKART=====================================================================================


from django.http import FileResponse
class DownloadCroppedPDF(APIView):
    def get(self, request, file_name, format=None):
        pdf_path = os.path.join(settings.MEDIA_ROOT, file_name)
        if os.path.exists(pdf_path):
            # Open the file for reading
            with open(pdf_path, 'rb') as pdf_file:
                response = FileResponse(pdf_file)
                response['Content-Type'] = 'application/pdf'
                response['Content-Disposition'] = f'attachment; filename="{file_name}"'
                os.remove(pdf_path)
                return Response({'Success': 'File deleted from backend'})
        else:
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)