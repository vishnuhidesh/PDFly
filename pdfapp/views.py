import os
import uuid
import json
import mimetypes
from pathlib import Path
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .constants import TOOLS, TOOLS_BY_SLUG, CATEGORIES
from . import services

def index_view(request):
    """Homepage listing all PDF tools with filters and search."""
    services.cleanup_old_files()
    return render(request, 'home.html', {
        'tools': TOOLS,
        'categories': CATEGORIES,
        'active_category': 'All',
    })


def tool_view(request, slug):
    """Workspace view for an individual PDF tool."""
    tool = TOOLS_BY_SLUG.get(slug)
    if not tool:
        raise Http404("Tool not found")

    services.cleanup_old_files()
    return render(request, 'tool_page.html', {
        'tool': tool,
        'all_tools': TOOLS,
    })


@csrf_exempt
def api_preview(request):
    """
    Accepts an uploaded PDF and returns generated thumbnails for each page.
    Used for interactive tools like Organize, Split, and Rotate.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No PDF file provided.'}, status=400)

    pdf_file = request.FILES['file']
    session_id = str(uuid.uuid4())
    uploads_dir, _, _ = services.ensure_dirs()
    
    file_path = uploads_dir / f"{session_id}_{pdf_file.name}"
    with open(file_path, 'wb+') as dest:
        for chunk in pdf_file.chunks():
            dest.write(chunk)

    try:
        thumb_data = services.generate_thumbnails(str(file_path), session_id)
        return JsonResponse({
            'success': True,
            'session_id': session_id,
            'file_name': pdf_file.name,
            'file_path': str(file_path),
            'total_pages': thumb_data['total_pages'],
            'thumbnails': thumb_data['thumbnails']
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Failed to generate preview: {str(e)}"}, status=500)


@csrf_exempt
def api_process(request, slug):
    """
    Handles PDF processing for all 12 tools via AJAX.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)

    tool = TOOLS_BY_SLUG.get(slug)
    if not tool:
        return JsonResponse({'success': False, 'error': 'Invalid tool specified.'}, status=404)

    uploads_dir, processed_dir, _ = services.ensure_dirs()
    task_id = str(uuid.uuid4())

    try:
        # 1. MERGE PDF
        if slug == 'merge-pdf':
            uploaded_files = request.FILES.getlist('files')
            order_json = request.POST.get('file_order')
            
            if not uploaded_files or len(uploaded_files) < 2:
                return JsonResponse({'success': False, 'error': 'Please provide at least 2 PDF files to merge.'})

            saved_paths = []
            name_map = {}
            for f in uploaded_files:
                save_name = f"{task_id}_{f.name}"
                p = uploads_dir / save_name
                with open(p, 'wb+') as dest:
                    for chunk in f.chunks():
                        dest.write(chunk)
                saved_paths.append(str(p))
                name_map[f.name] = str(p)

            # Reorder if provided
            if order_json:
                try:
                    ordered_names = json.loads(order_json)
                    ordered_paths = [name_map[n] for n in ordered_names if n in name_map]
                    if len(ordered_paths) == len(saved_paths):
                        saved_paths = ordered_paths
                except Exception:
                    pass

            out_filename = f"merged_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)
            services.merge_pdfs(saved_paths, out_path)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': 'merged_document.pdf',
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': f"Successfully merged {len(saved_paths)} PDF documents."
            })

        # 2. SPLIT PDF
        elif slug == 'split-pdf':
            pdf_file = request.FILES.get('file')
            mode = request.POST.get('mode', 'range')  # 'range' or 'extract_all'
            range_val = request.POST.get('range', '1')

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please select a PDF to split.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_pdf = str(processed_dir / f"split_{task_id[:8]}.pdf")
            out_zip = str(processed_dir / f"split_pages_{task_id[:8]}.zip")

            result = services.split_pdf(input_path, mode, range_val, out_pdf, out_zip)
            res_filename = os.path.basename(result['file_path'])

            return JsonResponse({
                'success': True,
                'file_id': res_filename,
                'filename': 'split_result.zip' if result['is_zip'] else 'split_pages.pdf',
                'download_url': f"/download/{res_filename}/",
                'file_size': os.path.getsize(result['file_path']),
                'message': f"Successfully extracted {result['page_count']} pages."
            })

        # 3. COMPRESS PDF
        elif slug == 'compress-pdf':
            pdf_file = request.FILES.get('file')
            level = request.POST.get('level', 'recommended')

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please select a PDF to compress.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_filename = f"compressed_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            stats = services.compress_pdf(input_path, out_path, level=level)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"compressed_{pdf_file.name}",
                'download_url': f"/download/{out_filename}/",
                'original_size': stats['original_size'],
                'file_size': stats['new_size'],
                'saved_bytes': stats['saved_bytes'],
                'savings_pct': stats['savings_pct'],
                'message': f"PDF compressed! Saved {stats['savings_pct']}% of file size."
            })

        # 4. ORGANIZE PDF
        elif slug == 'organize-pdf':
            pdf_file = request.FILES.get('file')
            page_order_str = request.POST.get('page_order')  # JSON array of indices
            rotations_str = request.POST.get('page_rotations', '{}')

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please upload a PDF to organize.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            page_order = json.loads(page_order_str) if page_order_str else None
            rotations = json.loads(rotations_str) if rotations_str else {}

            if not page_order:
                return JsonResponse({'success': False, 'error': 'Invalid page ordering specified.'})

            out_filename = f"organized_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            services.organize_pdf(input_path, out_path, page_order, page_rotations=rotations)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"organized_{pdf_file.name}",
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': f"PDF organized with {len(page_order)} pages."
            })

        # 5. PDF TO JPG / PNG
        elif slug == 'pdf-to-jpg':
            pdf_file = request.FILES.get('file')
            img_format = request.POST.get('format', 'jpg')
            dpi = int(request.POST.get('dpi', 150))

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please select a PDF to convert.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            result = services.pdf_to_images(input_path, str(processed_dir), img_format=img_format, dpi=dpi)
            res_filename = os.path.basename(result['file_path'])

            return JsonResponse({
                'success': True,
                'file_id': res_filename,
                'filename': result['filename'],
                'download_url': f"/download/{res_filename}/",
                'file_size': os.path.getsize(result['file_path']),
                'message': f"Converted {result['page_count']} page(s) to {img_format.upper()}."
            })

        # 6. JPG / IMAGES TO PDF
        elif slug == 'jpg-to-pdf':
            images = request.FILES.getlist('files')
            orientation = request.POST.get('orientation', 'auto')
            margin = request.POST.get('margin', 'none')

            if not images:
                return JsonResponse({'success': False, 'error': 'Please upload at least one image.'})

            saved_images = []
            for img in images:
                p = uploads_dir / f"{task_id}_{img.name}"
                with open(p, 'wb+') as dest:
                    for chunk in img.chunks():
                        dest.write(chunk)
                saved_images.append(str(p))

            out_filename = f"converted_images_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            services.images_to_pdf(saved_images, out_path, orientation=orientation, margin=margin)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': 'images_to_pdf.pdf',
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': f"Converted {len(saved_images)} image(s) into PDF."
            })

        # 7. ROTATE PDF
        elif slug == 'rotate-pdf':
            pdf_file = request.FILES.get('file')
            angle = int(request.POST.get('angle', 90))

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please select a PDF file to rotate.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_filename = f"rotated_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            services.rotate_pdf(input_path, out_path, angle=angle)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"rotated_{pdf_file.name}",
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': f"Document successfully rotated by {angle}°."
            })

        # 8. PROTECT PDF
        elif slug == 'protect-pdf':
            pdf_file = request.FILES.get('file')
            password = request.POST.get('password', '').strip()

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please upload a PDF file.'})
            if not password:
                return JsonResponse({'success': False, 'error': 'Password cannot be empty.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_filename = f"protected_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            services.protect_pdf(input_path, out_path, password=password)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"protected_{pdf_file.name}",
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': "PDF encrypted and password protected successfully."
            })

        # 9. UNLOCK PDF
        elif slug == 'unlock-pdf':
            pdf_file = request.FILES.get('file')
            password = request.POST.get('password', '').strip()

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please upload an encrypted PDF.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_filename = f"unlocked_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            services.unlock_pdf(input_path, out_path, password=password)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"unlocked_{pdf_file.name}",
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': "PDF unlocked and security restrictions removed."
            })

        # 10. ADD WATERMARK
        elif slug == 'watermark-pdf':
            pdf_file = request.FILES.get('file')
            text = request.POST.get('text', 'CONFIDENTIAL').strip()
            opacity = float(request.POST.get('opacity', 0.35))
            position = request.POST.get('position', 'center')
            rotation = int(request.POST.get('rotation', 45))
            font_size = int(request.POST.get('font_size', 42))
            color_hex = request.POST.get('color', '#E11D48')

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please upload a PDF file.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_filename = f"watermarked_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            services.add_watermark(input_path, out_path, text=text, opacity=opacity,
                                   position=position, rotation=rotation,
                                   font_size=font_size, color_hex=color_hex)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"watermarked_{pdf_file.name}",
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': "Watermark applied to all pages successfully."
            })

        # 11. PAGE NUMBERS
        elif slug == 'page-numbers':
            pdf_file = request.FILES.get('file')
            format_str = request.POST.get('format', 'Page {n} of {total}')
            position = request.POST.get('position', 'bottom-center')
            start_num = int(request.POST.get('start_num', 1))

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please upload a PDF file.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_filename = f"numbered_{task_id[:8]}.pdf"
            out_path = str(processed_dir / out_filename)

            services.add_page_numbers(input_path, out_path, format_str=format_str,
                                      position=position, start_number=start_num)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"numbered_{pdf_file.name}",
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'message': "Page numbers added across all pages."
            })

        # 12. PDF TO TEXT
        elif slug == 'pdf-to-text':
            pdf_file = request.FILES.get('file')

            if not pdf_file:
                return JsonResponse({'success': False, 'error': 'Please upload a PDF file.'})

            input_path = str(uploads_dir / f"{task_id}_{pdf_file.name}")
            with open(input_path, 'wb+') as dest:
                for chunk in pdf_file.chunks():
                    dest.write(chunk)

            out_filename = f"extracted_{task_id[:8]}.txt"
            out_path = str(processed_dir / out_filename)

            info = services.extract_text_pdf(input_path, out_path)

            return JsonResponse({
                'success': True,
                'file_id': out_filename,
                'filename': f"{Path(pdf_file.name).stem}.txt",
                'download_url': f"/download/{out_filename}/",
                'file_size': os.path.getsize(out_path),
                'preview_snippet': info['preview_snippet'],
                'word_count': info['word_count'],
                'character_count': info['character_count'],
                'message': f"Extracted {info['word_count']} words across {info['page_count']} pages."
            })

        return JsonResponse({'success': False, 'error': 'Unsupported tool.'}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def download_view(request, file_id):
    """Securely streams the processed file for user download."""
    _, processed_dir, _ = services.ensure_dirs()
    # Prevent directory traversal
    clean_id = os.path.basename(file_id)
    target_path = processed_dir / clean_id

    if not target_path.exists():
        raise Http404("The requested file does not exist or has expired.")

    content_type, _ = mimetypes.guess_type(str(target_path))
    content_type = content_type or 'application/octet-stream'

    response = FileResponse(open(target_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{clean_id}"'
    return response


@csrf_exempt
def api_cleanup(request, file_id):
    """Allows user to instantly delete the processed file."""
    if request.method == 'POST':
        _, processed_dir, _ = services.ensure_dirs()
        clean_id = os.path.basename(file_id)
        target_path = processed_dir / clean_id
        if target_path.exists():
            try:
                target_path.unlink()
                return JsonResponse({'success': True, 'message': 'File deleted successfully.'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})
