from PyPDF2 import PdfFileReader, PdfFileWriter
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


class PDFCropAPIView(APIView):
    def post(self, request, format=None):
        try:
            uploaded_file1 = request.FILES['pdf_file']
            pdf_bytes = uploaded_file1.read()

            pdf_document = fitz.open("pdf", pdf_bytes)
            extracted_data = defaultdict(int)
            pattern = r'Description\nQTY\n1\s+(.*?)\s+'

            sku_names = []
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

            response_data = []
            response_data_extra = []
            new_pagedata1 = []
            new_pagedata2 = []
            new_pagedata3 = []
            new_pagedata4 = []

            static_data_fix = {
                "QTY": "QTY",
                "SKU": "SKU"
            }
            response_data.append(static_data_fix)

            if new_pagedata1:
                new_pagedata1.append(static_data_fix)

            total_order_quantity = 0
            for sku, qty in extracted_data.items():
                order_qty = max(1, qty)
                total_order_quantity += order_qty

                if len(response_data) <= 15:
                    response_data.append({"QTY": order_qty, "SKU": sku})
                elif len(new_pagedata1) <= 14:
                    new_pagedata1.append({"QTY": order_qty, "SKU": sku})
                elif len(new_pagedata2) <= 14:
                    new_pagedata2.append({"QTY": order_qty, "SKU": sku})
                elif len(new_pagedata3) <= 14:
                    new_pagedata3.append({"QTY": order_qty, "SKU": sku})
                else:
                    new_pagedata4.append({"QTY": order_qty, "SKU": sku})

            print("response_data:-----------> ", response_data)
            print("new_pagedata1:------------>", new_pagedata1)
            print("new_pagedata2:------------>", new_pagedata2)
            print("new_pagedata3:------------>", new_pagedata3)
            print("new_pagedata4:------------>", new_pagedata4)

            sorted_pages = [page_num for page_num, _ in sorted([(i, sku_names[i]) for i in range(len(sku_names))], key=lambda x: x[1])]
            
            if  new_pagedata1 and not new_pagedata2 and not new_pagedata3 and not new_pagedata4:
                total_order = f"Total Package: {total_order_quantity}" 
                new_pagedata1.append({"total_order_quantity": total_order})
            elif new_pagedata2 and not new_pagedata3 and not new_pagedata4:
                total_order = f"Total Package: {total_order_quantity}" 
                new_pagedata2.append({"total_order_quantity": total_order})
            elif new_pagedata3 and not new_pagedata4:
                total_order = f"Total Package: {total_order_quantity}" 
                new_pagedata3.append({"total_order_quantity": total_order})
            elif new_pagedata4:
                total_order = f"Total Package: {total_order_quantity}" 
                new_pagedata4.append({"total_order_quantity": total_order})
            else:
                total_order = f"Total Package: {total_order_quantity}" 

            courier_partner = f"Courier Partner: {first_line}"   
                
            # response_data_extra_lable = {"total_order_quantity": "Package","courier_partner":"Courier Partner"}
            # response_data_extra.append(response_data_extra_lable)

            response_data_extra.append({"total_order_quantity": total_order,"courier_partner":courier_partner})
            
        except Exception as e:
            print("ERRRRORRR =>",e)

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

#==============================================FIRST TABLE PAGE1 ==========================================================

            output_list = [[value for value in d.values()] for d in response_data]

            heading = "*                      This Flipkart label is provided by JD                         *"
            heading_row = [heading]

            output_list.insert(0, heading_row)

            temp_buffer = BytesIO()
            temp_canvas = canvas.Canvas(temp_buffer, pagesize=letter)

            data = output_list
            table = Table(data)
            style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                ('SPAN', (0, 0), (-1, 0)), 
                                ('FONTSIZE', (0, 0), (-1, -1), 6),
                                ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                ])
            table.setStyle(style)
            table.wrap(0, 0)
            table_height = table._height - 45

            page_height = letter[1]
            # Change height of table
            y_coordinate = page_height - table_height - 60
            table.wrapOn(temp_canvas, 0, 0)
            table.drawOn(temp_canvas, 200, y_coordinate)


#============================================== TABLE TWO PAGE 1 ===========================================================
            if not new_pagedata1:
                output_list2 = [[value for value in d.values()] for d in response_data_extra]

                heading2 = "Courier wise total package:"
                heading_row2 = [heading2]
                output_list2.insert(0, heading_row2)
                
                data = output_list2
                table2 = Table(data)
                print('table2:2222222 = > ', table2)
                style2 = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                    ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                    ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                    ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                    ('SPAN', (0, 0), (-1, 0)), 
                                    ('FONTSIZE', (0, 0), (-1, -1), 6),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                    
                                    ])
                table2.setStyle(style2)
                table2.wrap(0, 0) 
                table2_height = table2._height + 230 
                
                page_height2 = letter[1]
                y_coordinate2 = page_height2 - table2_height - 60  

                table2.wrapOn(temp_canvas, 0, 0)
                table2.drawOn(temp_canvas, 200, y_coordinate2)  

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



# ============================================FIRST TABLE PAGE 222222==============================================================

            if new_pagedata1 :
                output_list = [[value for value in d.values()] for d in new_pagedata1]
                
                heading = "*                      This Flipkart label is provided by JD                         *"

                heading_row = [heading]
                output_list.insert(0, heading_row)

                temp_buffer = BytesIO()
                temp_canvas = canvas.Canvas(temp_buffer, pagesize=letter)

                data = output_list
                table = Table(data)
                style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                    ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                    ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                    ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                    ('SPAN', (0, 0), (-1, 0)), 
                                    ('FONTSIZE', (0, 0), (-1, -1), 6),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                    
                                    ])
                table.setStyle(style)
                table.wrap(0, 0)
                table_height = table._height - 45

                page_height = letter[1]
                y_coordinate = page_height - table_height - 60

                table.wrapOn(temp_canvas, 0, 0)
                table.drawOn(temp_canvas, 200, y_coordinate)


    #==============================================SECOND TABLE 2nd PAGE ===========================================================
                if not new_pagedata3  and not new_pagedata2 and not new_pagedata4:
                    output_list2 = [[value for value in d.values()] for d in response_data_extra]

                    heading2 = "Courier wise total package:"
                    heading_row2 = [heading2]

                    # Add heading_row to the beginning of output_list
                    output_list2.insert(0, heading_row2)

                    data = output_list2
                    table2 = Table(data)
                    style2 = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                        ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                        ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                        ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                        ('SPAN', (0, 0), (-1, 0)), 
                                        ('FONTSIZE', (0, 0), (-1, -1), 6),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                        ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                        ])
                    table2.setStyle(style2)
                    table2.wrap(0, 0) 
                    table2_height = table2._height + 230  

                    page_height2 = letter[1]
                    y_coordinate2 = page_height2 - table2_height - 60  

                    table2.wrapOn(temp_canvas, 0, 0)
                    table2.drawOn(temp_canvas, 200, y_coordinate2)  

                temp_canvas.save()
                temp_buffer.seek(0)
                overlay_pdf = PdfFileReader(temp_buffer)
                overlay_page = overlay_pdf.getPage(0)
                pdf_writer.addPage(overlay_page)
                overlay_page.cropBox.upperLeft = (x, y)
                overlay_page.cropBox.lowerRight = (x + width, y - height)

                output_buffer = BytesIO()
                pdf_writer.write(output_buffer)
                output_buffer.seek(0)



# ============================================FIRST TABLE PAGE 3==============================================================

            if new_pagedata2:
                output_list = [[value for value in d.values()] for d in new_pagedata2]
                
                heading = "*                      This Flipkart label is provided by JD                         *"

                heading_row = [heading]
                output_list.insert(0, heading_row)

                temp_buffer = BytesIO()
                temp_canvas = canvas.Canvas(temp_buffer, pagesize=letter)

                data = output_list
                table = Table(data)
                style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                    ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                    ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                    ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                    ('SPAN', (0, 0), (-1, 0)), 
                                    ('FONTSIZE', (0, 0), (-1, -1), 6),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                    
                                    ])
                table.setStyle(style)
                table.wrap(0, 0)
                table_height = table._height - 45

                page_height = letter[1]
                y_coordinate = page_height - table_height - 60

                table.wrapOn(temp_canvas, 0, 0)
                table.drawOn(temp_canvas, 200, y_coordinate)


    #==============================================SECOND TABLE 3nd page ===========================================================
                if not new_pagedata3 and not new_pagedata4:
                    output_list2 = [[value for value in d.values()] for d in response_data_extra]

                    heading2 = "Courier wise total package:"
                    heading_row2 = [heading2]

                    output_list2.insert(0, heading_row2)

                    data = output_list2
                    table2 = Table(data)
                    style2 = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                        ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                        ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                        ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                        ('SPAN', (0, 0), (-1, 0)), 
                                        ('FONTSIZE', (0, 0), (-1, -1), 6),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                        ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                        ])
                    table2.setStyle(style2)
                    table2.wrap(0, 0) 
                    table2_height = table2._height + 230  

                    page_height2 = letter[1]
                    y_coordinate2 = page_height2 - table2_height - 60  

                    table2.wrapOn(temp_canvas, 0, 0)
                    table2.drawOn(temp_canvas, 200, y_coordinate2)  

                temp_canvas.save()
                temp_buffer.seek(0)
                overlay_pdf = PdfFileReader(temp_buffer)
                overlay_page = overlay_pdf.getPage(0)
                pdf_writer.addPage(overlay_page)
                overlay_page.cropBox.upperLeft = (x, y)
                overlay_page.cropBox.lowerRight = (x + width, y - height)

                output_buffer = BytesIO()
                pdf_writer.write(output_buffer)
                output_buffer.seek(0)


# ============================================FIRST TABLE PAGE 4==============================================================

            if new_pagedata3:
                output_list = [[value for value in d.values()] for d in new_pagedata3]
                
                heading = "*                      This Flipkart label is provided by JD                         *"

                heading_row = [heading]
                output_list.insert(0, heading_row)

                temp_buffer = BytesIO()
                temp_canvas = canvas.Canvas(temp_buffer, pagesize=letter)

                data = output_list
                table = Table(data)
                style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                    ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                    ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                    ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                    ('SPAN', (0, 0), (-1, 0)), 
                                    ('FONTSIZE', (0, 0), (-1, -1), 6),
                                    ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                    
                                    ])
                table.setStyle(style)
                table.wrap(0, 0)
                table_height = table._height - 45

                page_height = letter[1]
                y_coordinate = page_height - table_height - 60

                table.wrapOn(temp_canvas, 0, 0)
                table.drawOn(temp_canvas, 200, y_coordinate)


    #==============================================SECOND TABLE 4th page ===========================================================
                if not new_pagedata4:
                    output_list2 = [[value for value in d.values()] for d in response_data_extra]

                    heading2 = "Courier wise total package:"
                    heading_row2 = [heading2]

                    output_list2.insert(0, heading_row2)

                    data = output_list2
                    table2 = Table(data)
                    style2 = TableStyle([('BACKGROUND', (0, 0), (-1, 0), (0.7, 0.7, 0.7)),
                                        ('TEXTCOLOR', (0, 0), (-1, 0), (1, 1, 1)),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                        ('BACKGROUND', (0, 1), (-1, -1), (0.9, 0.9, 0.9)),
                                        ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
                                        ('SPAN', (0, 0), (-1, 0)), 
                                        ('FONTSIZE', (0, 0), (-1, -1), 6),
                                        ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Set bottom padding for the header row
                                        ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                                        ])
                    table2.setStyle(style2)
                    table2.wrap(0, 0) 
                    table2_height = table2._height + 230  

                    page_height2 = letter[1]
                    y_coordinate2 = page_height2 - table2_height - 60  

                    table2.wrapOn(temp_canvas, 0, 0)
                    table2.drawOn(temp_canvas, 200, y_coordinate2)  

                temp_canvas.save()
                temp_buffer.seek(0)
                overlay_pdf = PdfFileReader(temp_buffer)
                overlay_page = overlay_pdf.getPage(0)
                pdf_writer.addPage(overlay_page)
                overlay_page.cropBox.upperLeft = (x, y)
                overlay_page.cropBox.lowerRight = (x + width, y - height)

                output_buffer = BytesIO()
                pdf_writer.write(output_buffer)
                output_buffer.seek(0)

            output_pdf_path = 'output.pdf'
            with open(output_pdf_path, 'wb') as output_pdf:
                pdf_writer.write(output_pdf)

            with open(output_pdf_path, 'rb') as output_pdf:
                pdf_document = fitz.open(output_pdf)

                pdf_document.select(sorted_pages)
                for page_num in range(len(pdf_document)):
                    current_page = pdf_document[page_num]
                    text = current_page.get_text()

                    qty_pattern = r'QTY\s*:\s*(\d+)'
                    qty_match = re.search(qty_pattern, text)
                
                    if qty_match:
                        qty_value = qty_match.group(1)
                        value_below_qty_pattern = r'QTY\s*:\s*' + qty_value + r'\s*(\S.*)'
                        value_match = re.search(value_below_qty_pattern, text)
                        
                        if value_match:
                            value_below_qty = value_match.group(1)
                        else:
                            print(f"No value found below QTY on page {page_num + 1}.")
                    else:
                        pass
                pdf_document.close()

                x = 200
                y = 300
                width = 78.1853
                height = 17.5

                with open(output_pdf_path, 'rb') as output_pdf:
                    pdf_document = fitz.open(output_pdf)
                    region = fitz.Rect(x, y - height, x + width, y)
                    for page_num in range(len(pdf_document)):
                        current_page = pdf_document[page_num]
                        text = current_page.get_text("text", clip=region)

                        if text.strip(): 
                            pass
                pdf_document.close()

            output_pdf_path = os.path.join(settings.MEDIA_ROOT, 'output.pdf')
            
            with open(output_pdf_path, 'wb') as output_pdf:
                pdf_writer.write(output_pdf)

            file_url = settings.MEDIA_URL + 'output.pdf'
            
            response_data = {
                'message': 'PDF cropped successfully.',
                'file_path': file_url
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(pdf_form.errors, status=status.HTTP_400_BAD_REQUEST)

# ====================================================OVER FLIPKART=====================================================================================




class ExtractPDFData(APIView):
    def post(self, request, format=None):
        try:
            uploaded_file = request.FILES['pdf_file']
            print('uploaded_file: ', uploaded_file)
            pdf_bytes = uploaded_file.read()

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

            pdf_document.close()
            response_data = []
            total_order_quantity = 0

            for sku, qty in extracted_data.items():
                order_qty = max(1, qty)  
                total_order_quantity += order_qty
                response_data.append({"QTY": "1", "SKU": sku, "order": order_qty})

            response_data.append({"total_order_quantity": total_order_quantity,"courier_partner":first_line})
            print('first_line: ', first_line)

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

