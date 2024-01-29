from django.shortcuts import render
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
import uuid

import requests
import json
from .forms import CropForm


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


class MesssoPDFCropAPIView(APIView):
    
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
        y_coordinate2 = letter[1] - table2_height - 30
        table2.wrapOn(temp_canvas, 0, 0)
        table2.drawOn(temp_canvas, 200, y_coordinate2)
    
    
    def find_text_coordinates(self, pdf_document, target_text):
        coordinates = []
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text = page.get_text("text")
            
            if target_text in text:
                rect = page.search_for(target_text)
                for r in rect:
                    bbox = fitz.Rect(r)
                    coordinates.append({
                        'x': bbox.x0,
                        'y': bbox.y0,
                        'width': bbox.width,
                        'height': bbox.height
                    })
        return coordinates

    def post(self, request, format=None):
        try:
            sku_names = []
            size_info = []
            sku_size_pairs = {}
            uploaded_file1 = request.FILES['pdf_file']
            pdf_bytes = uploaded_file1.read()
            pdf_document = fitz.open("pdf", pdf_bytes)
            extracted_data = defaultdict(int)
            # print("extracted_data>>..",extracted_data)
            # pattern = r'Description\nQTY\n1\s+(.*?)\s+'
            # pattern = r'Order No\.\s+(\b[^\d\W]+\b)(?!\s*Purchase Order No\.)'
            pattern = r'Order No\.\s+([^\s]+)'
            
            size_info = []  # List to store size information
            size_pattern = r'SKU\nSize\nQty\nColor\nOrder No\.\n[^\n]+\n([^\n]+)'


            fold_here_coordinates = self.find_text_coordinates(pdf_document, "Fold Here")
            # for idx, coord in enumerate(fold_here_coordinates, start=1):
            #     print(f"Page ==================>>>>>> y = {coord['y']}")
            # print("pattern>>>>>>>>>>>>>>>>>>>>",pattern)

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
                sku_matches = re.findall(pattern, text)

                size_matches = re.findall(size_pattern, text)
                if size_matches:
                    for size in size_matches:
                        size_info.append((size, page_num))
                
                if matches and size_matches:
                    sku_size_pairs[page_num] = (matches[0], size_matches[0])

            for page_num, (sku, size) in sku_size_pairs.items():
                sku_with_size = f"{sku} {size}"
                extracted_data[sku_with_size] += 1
                sku_names.append((sku_with_size, page_num))

            print(":::::::::<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>",sku_names)
            pdf_document.close()

            total_items = []
            all_data_values = [{"QTY": value, "SKU": key} for key, value in extracted_data.items()]
            print('all_data_values: ===== >>>>> ', all_data_values)

            total_order_quantity = 0
            for items in all_data_values:
                order_qty = max(1, items["QTY"])
                total_order_quantity += order_qty

            sublist_limit = 15
            sublists = [all_data_values[i:i + sublist_limit] for i in range(0, len(all_data_values), sublist_limit)]
            sublists[-1].append({"total_order_quantity": f"Total Package: {total_order_quantity}"})
            sublists[0].insert(0, {"QTY": "QTY", "SKU": "SKU"})
            

            sorted_pages = [page_num for page_num, _ in sorted([(i, sku_names[i]) for i in range(len(sku_names))], key=lambda x: x[1])]
            total_items.append({"total_order_quantity": total_order_quantity, "courier_partner": f"Courier Partner: {first_line}"})
            
        except Exception as e:
            raise

        pdf_form = UploadedPDFSerializer(data=request.data)
        crop_form = CropForm(request.data)
        if pdf_form.is_valid() and crop_form.is_valid():
            uploaded_pdf = pdf_form.save()
            pdf_path = uploaded_pdf.pdf_file.path

            api_endpoint = "https://ecropper-api-prod.azurewebsites.net/api/pdf/meesho-pdf-extract"
            files = {'pdfFile': ('pdffile.pdf', open(pdf_path, 'rb'))}
            response = requests.post(api_endpoint, files=files)

            response_data_str = response.text  
            response_data = json.loads(response_data_str)  

            y_values = [item["y"] for item in response_data]

            final_list_of_y = [str(float(value) + 356) if value.strip() else '0' for value in y_values]

            
            y = crop_form.cleaned_data['y']

            x = crop_form.cleaned_data['x']
            width = crop_form.cleaned_data['width']
            height = crop_form.cleaned_data['height']

            pdf_reader = PdfFileReader(pdf_path)
            pdf_writer = PdfFileWriter()
            for index, page_num in enumerate(sorted_pages):
                page = pdf_reader.getPage(page_num)


                if index < len(final_list_of_y):
                    y = float(final_list_of_y[index])
                    page.cropBox.upperLeft = (x, y)
                    page.cropBox.lowerRight = (x + width, y - height)
                    pdf_writer.addPage(page)

            last_index = len(sublists) - 1
            
            for index, pages in enumerate(sublists):
                output_list = [[value for value in page.values()] for page in pages]
                heading = "*" + " "*22 + "This Meesho label is provided by PDFTool" + " "*22 + "*"
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

# from django.http import FileResponse
# class DownloadCroppedPDF(APIView):
#     def delete(self, request, file_name, format=None):
#         pdf_path = os.path.join(settings.MEDIA_ROOT, file_name)
#         if os.path.exists(pdf_path):
#             # Open the file for reading
#             with open(pdf_path, 'rb') as pdf_file:
#                 response = FileResponse(pdf_file)
#                 response['Content-Type'] = 'application/pdf'
#                 response['Content-Disposition'] = f'attachment; filename="{file_name}"'
#                 os.remove(pdf_path)
#                 return Response({'Success': 'File deleted from backend'})
#         else:
#             return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

# # payload

# 	x = 0
# 	y = 835.1739
# 	width = 600
# 	height = 350.6048	
