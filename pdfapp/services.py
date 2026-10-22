import os
import io
import zipfile
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import pymupdf
from pypdf import PdfReader, PdfWriter
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from django.conf import settings

def ensure_dirs():
    """Ensure media directories exist."""
    uploads_dir = Path(settings.MEDIA_ROOT) / 'uploads'
    processed_dir = Path(settings.MEDIA_ROOT) / 'processed'
    thumbs_dir = Path(settings.MEDIA_ROOT) / 'thumbnails'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir, processed_dir, thumbs_dir

def cleanup_old_files(max_age_seconds: int = 7200):
    """Clean up media files older than max_age_seconds (default 2 hours)."""
    try:
        now = time.time()
        for folder_name in ['uploads', 'processed', 'thumbnails']:
            folder = Path(settings.MEDIA_ROOT) / folder_name
            if folder.exists():
                for item in folder.iterdir():
                    try:
                        if item.is_file() and (now - item.stat().st_mtime > max_age_seconds):
                            item.unlink(missing_ok=True)
                        elif item.is_dir() and (now - item.stat().st_mtime > max_age_seconds):
                            shutil.rmtree(item, ignore_errors=True)
                    except Exception:
                        pass
    except Exception:
        pass


def generate_thumbnails(pdf_path: str, session_id: str, max_pages: int = 60) -> Dict[str, Any]:
    """
    Renders pages of a PDF to fast preview PNG thumbnails.
    Returns list of relative thumbnail URLs and total pages.
    """
    _, _, thumbs_dir = ensure_dirs()
    session_thumb_dir = thumbs_dir / session_id
    session_thumb_dir.mkdir(parents=True, exist_ok=True)

    thumbnails = []
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    pages_to_render = min(total_pages, max_pages)

    for i in range(pages_to_render):
        page = doc[i]
        # 96 DPI zoom factor = 96/72 = 1.33 for fast, crisp thumbnail
        zoom = 1.33
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        thumb_filename = f"thumb_page_{i + 1}.png"
        thumb_path = session_thumb_dir / thumb_filename
        pix.save(str(thumb_path))
        
        thumbnails.append({
            'page_number': i + 1,
            'index': i,
            'url': f"{settings.MEDIA_URL}thumbnails/{session_id}/{thumb_filename}",
            'width': pix.width,
            'height': pix.height
        })

    doc.close()
    return {
        'total_pages': total_pages,
        'rendered_count': pages_to_render,
        'thumbnails': thumbnails
    }


def merge_pdfs(file_paths: List[str], output_path: str) -> str:
    """Merge multiple PDF files into one output PDF."""
    if not file_paths:
        raise ValueError("No files provided to merge.")
    
    result_doc = pymupdf.open()
    for fp in file_paths:
        doc = pymupdf.open(fp)
        result_doc.insert_pdf(doc)
        doc.close()
    
    result_doc.save(output_path, garbage=3, deflate=True)
    result_doc.close()
    return output_path


def parse_page_ranges(range_str: str, max_pages: int) -> List[int]:
    """
    Parse a range string like '1-3, 5, 8-10' into 0-indexed page integers.
    """
    selected_pages = []
    parts = [p.strip() for p in range_str.split(',') if p.strip()]
    for part in parts:
        if '-' in part:
            bounds = part.split('-')
            if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                start = max(1, int(bounds[0].strip()))
                end = min(max_pages, int(bounds[1].strip()))
                for p in range(start, end + 1):
                    if (p - 1) not in selected_pages:
                        selected_pages.append(p - 1)
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= max_pages and (p - 1) not in selected_pages:
                selected_pages.append(p - 1)
    return selected_pages


def split_pdf(file_path: str, mode: str, range_str: str, output_path: str, zip_path: str) -> Dict[str, Any]:
    """
    Split a PDF by range or separate into all individual pages.
    """
    doc = pymupdf.open(file_path)
    total_pages = len(doc)

    if mode == 'range':
        # Extract specific pages into one combined PDF
        page_indices = parse_page_ranges(range_str, total_pages)
        if not page_indices:
            raise ValueError(f"Invalid page range: '{range_str}'. Total pages: {total_pages}")
        
        new_doc = pymupdf.open()
        for idx in page_indices:
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)
        
        new_doc.save(output_path, garbage=3, deflate=True)
        new_doc.close()
        doc.close()
        return {'is_zip': False, 'file_path': output_path, 'page_count': len(page_indices)}

    elif mode == 'extract_all':
        # Split every page into its own PDF and zip them together
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for i in range(total_pages):
                page_doc = pymupdf.open()
                page_doc.insert_pdf(doc, from_page=i, to_page=i)
                pdf_bytes = page_doc.write(garbage=3, deflate=True)
                page_doc.close()
                zf.writestr(f"page_{i + 1}.pdf", pdf_bytes)
        
        doc.close()
        return {'is_zip': True, 'file_path': zip_path, 'page_count': total_pages}
    
    doc.close()
    raise ValueError("Invalid split mode specified.")


def compress_pdf(file_path: str, output_path: str, level: str = 'recommended') -> Dict[str, Any]:
    """
    Compress a PDF using PyMuPDF stream deflation, garbage collection, and image downsampling.
    """
    doc = pymupdf.open(file_path)
    original_size = os.path.getsize(file_path)

    # For recommended or extreme, optionally compress/downscale embedded images
    if level in ['extreme', 'recommended']:
        target_dpi = 100 if level == 'extreme' else 150
        quality = 60 if level == 'extreme' else 75

        for page in doc:
            img_list = page.get_images(full=True)
            for img_info in img_list:
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image and base_image.get("image"):
                        img_bytes = base_image["image"]
                        image = Image.open(io.BytesIO(img_bytes))
                        
                        # Downscale if excessively large
                        w, h = image.size
                        if w > 1200 or h > 1200:
                            ratio = min(1200 / w, 1200 / h)
                            new_size = (int(w * ratio), int(h * ratio))
                            image = image.resize(new_size, Image.Resampling.LANCZOS)
                        
                        if image.mode in ('RGBA', 'P'):
                            image = image.convert('RGB')
                        
                        out_buffer = io.BytesIO()
                        image.save(out_buffer, format="JPEG", quality=quality, optimize=True)
                        doc.update_stream(xref, out_buffer.getvalue())
                except Exception:
                    continue

    # PyMuPDF garbage collection: 4 = purge unreferenced, compact streams, remove duplicate objects
    doc.save(
        output_path,
        garbage=4,
        deflate=True,
        clean=True,
        deflate_images=True,
        deflate_fonts=True
    )
    doc.close()

    new_size = os.path.getsize(output_path)
    # If compression somehow resulted in a larger file (rare), use original
    if new_size > original_size:
        shutil.copyfile(file_path, output_path)
        new_size = original_size

    saved_bytes = max(0, original_size - new_size)
    savings_pct = round((saved_bytes / original_size) * 100, 1) if original_size > 0 else 0

    return {
        'original_size': original_size,
        'new_size': new_size,
        'saved_bytes': saved_bytes,
        'savings_pct': savings_pct
    }


def pdf_to_images(file_path: str, output_dir: str, img_format: str = 'jpg', dpi: int = 150) -> Dict[str, Any]:
    """
    Render PDF pages to high-quality images.
    Returns single image path or zip file path.
    """
    doc = pymupdf.open(file_path)
    total_pages = len(doc)
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    ext = 'jpg' if img_format.lower() in ['jpg', 'jpeg'] else 'png'

    if total_pages == 1:
        # Single page, return single image directly
        page = doc[0]
        pix = page.get_pixmap(matrix=mat, alpha=(ext == 'png'))
        single_path = os.path.join(output_dir, f"page_1.{ext}")
        pix.save(single_path)
        doc.close()
        return {'is_zip': False, 'file_path': single_path, 'page_count': 1, 'filename': f"page_1.{ext}"}

    # Multiple pages, package into ZIP
    zip_path = os.path.join(output_dir, f"converted_images.zip")
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(total_pages):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat, alpha=(ext == 'png'))
            img_bytes = pix.tobytes(ext)
            zf.writestr(f"page_{i + 1}.{ext}", img_bytes)

    doc.close()
    return {'is_zip': True, 'file_path': zip_path, 'page_count': total_pages, 'filename': "converted_images.zip"}


def images_to_pdf(image_paths: List[str], output_path: str, orientation: str = 'auto', margin: str = 'none') -> str:
    """
    Convert a list of images into a single clean PDF document.
    """
    if not image_paths:
        raise ValueError("No images provided.")

    doc = pymupdf.open()
    # A4 dimensions in points: 595.3 x 841.9
    A4_W, A4_H = 595.3, 841.9
    margin_pts = 0
    if margin == 'small':
        margin_pts = 20
    elif margin == 'big':
        margin_pts = 50

    for img_path in image_paths:
        with Image.open(img_path) as im:
            iw, ih = im.size

        # Determine target page width and height
        if orientation == 'portrait':
            pw, ph = A4_W, A4_H
        elif orientation == 'landscape':
            pw, ph = A4_H, A4_W
        else: # auto
            pw, ph = (A4_H, A4_W) if iw > ih else (A4_W, A4_H)

        usable_w = pw - (2 * margin_pts)
        usable_h = ph - (2 * margin_pts)

        # Scale image to fit usable area preserving aspect ratio
        scale = min(usable_w / iw, usable_h / ih)
        dest_w = iw * scale
        dest_h = ih * scale
        x0 = margin_pts + (usable_w - dest_w) / 2
        y0 = margin_pts + (usable_h - dest_h) / 2
        rect = pymupdf.Rect(x0, y0, x0 + dest_w, y0 + dest_h)

        page = doc.new_page(width=pw, height=ph)
        page.insert_image(rect, filename=img_path)

    doc.save(output_path, garbage=3, deflate=True)
    doc.close()
    return output_path


def rotate_pdf(file_path: str, output_path: str, angle: int = 90) -> str:
    """Rotate all pages in a PDF document by angle (clockwise: 90, 180, 270)."""
    doc = pymupdf.open(file_path)
    for page in doc:
        page.set_rotation((page.rotation + angle) % 360)
    doc.save(output_path, garbage=3, deflate=True)
    doc.close()
    return output_path


def protect_pdf(file_path: str, output_path: str, password: str) -> str:
    """Encrypt a PDF with AES-256 and set password."""
    if not password:
        raise ValueError("Password cannot be empty.")
    
    doc = pymupdf.open(file_path)
    # Permissions: allow printing and copying text, but require password to open
    perm = pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_COPY
    doc.save(
        output_path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw=password,
        user_pw=password,
        permissions=perm
    )
    doc.close()
    return output_path


def unlock_pdf(file_path: str, output_path: str, password: str) -> str:
    """Decrypt a PDF document using password."""
    doc = pymupdf.open(file_path)
    if doc.is_encrypted:
        success = doc.authenticate(password)
        if not success:
            doc.close()
            raise ValueError("Incorrect password provided for encrypted PDF.")
    
    # Save decrypted
    doc.save(output_path, encryption=pymupdf.PDF_ENCRYPT_NONE)
    doc.close()
    return output_path


def add_watermark(file_path: str, output_path: str, text: str, opacity: float = 0.35, 
                  position: str = 'center', rotation: int = 45, font_size: int = 42,
                  color_hex: str = '#E11D48') -> str:
    """Add customized text watermark to every page of the PDF."""
    if not text:
        raise ValueError("Watermark text cannot be empty.")

    doc = pymupdf.open(file_path)
    r_color = HexColor(color_hex)
    red, green, blue = r_color.red, r_color.green, r_color.blue

    for page in doc:
        pw = page.rect.width
        ph = page.rect.height

        # Calculate watermark coordinates
        if position == 'top':
            x, y = pw / 2, ph * 0.15
        elif position == 'bottom':
            x, y = pw / 2, ph * 0.85
        elif position == 'diagonal':
            x, y = pw / 2, ph / 2
            rotation = 45
        else: # center
            x, y = pw / 2, ph / 2

        # Create overlay PDF page in memory
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(pw, ph))
        can.saveState()
        can.setFont("Helvetica-Bold", font_size)
        can.setFillColorRGB(red, green, blue, alpha=opacity)
        can.translate(x, y)
        can.rotate(rotation)
        can.drawCentredString(0, 0, text)
        can.restoreState()
        can.save()
        packet.seek(0)

        # Merge stamp into PyMuPDF page
        stamp_doc = pymupdf.open("pdf", packet.read())
        page.show_pdf_page(page.rect, stamp_doc, 0)
        stamp_doc.close()

    doc.save(output_path, garbage=3, deflate=True)
    doc.close()
    return output_path


def add_page_numbers(file_path: str, output_path: str, format_str: str = 'Page {n} of {total}',
                     position: str = 'bottom-center', margin: int = 30, start_number: int = 1) -> str:
    """Add clean page numbers to every page of the PDF."""
    doc = pymupdf.open(file_path)
    total_pages = len(doc)

    for i, page in enumerate(doc):
        current_num = start_number + i
        label = format_str.replace('{n}', str(current_num)).replace('{total}', str(total_pages + start_number - 1))
        
        pw = page.rect.width
        ph = page.rect.height

        # Calculate coordinates (ReportLab canvas 0,0 is bottom-left)
        if 'bottom' in position:
            y = margin
        else: # top
            y = ph - margin

        if 'left' in position:
            x = margin
            align = 'left'
        elif 'right' in position:
            x = pw - margin
            align = 'right'
        else: # center
            x = pw / 2
            align = 'center'

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(pw, ph))
        can.setFont("Helvetica", 10)
        can.setFillColorRGB(0.2, 0.25, 0.3)
        if align == 'center':
            can.drawCentredString(x, y, label)
        elif align == 'right':
            can.drawRightString(x, y, label)
        else:
            can.drawString(x, y, label)
        can.save()
        packet.seek(0)

        stamp_doc = pymupdf.open("pdf", packet.read())
        page.show_pdf_page(page.rect, stamp_doc, 0)
        stamp_doc.close()

    doc.save(output_path, garbage=3, deflate=True)
    doc.close()
    return output_path


def organize_pdf(file_path: str, output_path: str, page_order: List[int], 
                 page_rotations: Optional[Dict[str, int]] = None) -> str:
    """
    Rearrange, delete, and rotate pages based on user interaction.
    page_order is a list of 0-based original page indexes in their new order.
    """
    doc = pymupdf.open(file_path)
    total = len(doc)
    page_rotations = page_rotations or {}

    new_doc = pymupdf.open()
    for new_idx, orig_idx in enumerate(page_order):
        if 0 <= orig_idx < total:
            new_doc.insert_pdf(doc, from_page=orig_idx, to_page=orig_idx)
            # Apply rotation if present
            rot = page_rotations.get(str(orig_idx), 0)
            if rot:
                page = new_doc[new_idx]
                page.set_rotation((page.rotation + rot) % 360)

    if len(new_doc) == 0:
        new_doc.close()
        doc.close()
        raise ValueError("Cannot create an empty PDF. At least one page must remain.")

    new_doc.save(output_path, garbage=3, deflate=True)
    new_doc.close()
    doc.close()
    return output_path


def extract_text_pdf(file_path: str, output_path: str) -> Dict[str, Any]:
    """Extract all text from PDF and save as a UTF-8 text file."""
    doc = pymupdf.open(file_path)
    full_text = []
    
    for i, page in enumerate(doc):
        page_text = page.get_text("text").strip()
        full_text.append(f"==================== Page {i + 1} ====================\n\n{page_text}\n")

    text_content = "\n".join(full_text)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text_content)

    total_pages = len(doc)
    doc.close()
    return {
        'file_path': output_path,
        'page_count': total_pages,
        'character_count': len(text_content),
        'word_count': len(text_content.split()),
        'preview_snippet': text_content[:1500]
    }
