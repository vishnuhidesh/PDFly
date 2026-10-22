# PDFly (Django + PyMuPDF)

A modern, professional online PDF suite (**PDFly**) built with **Django** and powered by **PyMuPDF**, **ReportLab**, and **Pillow**.

---

## ✨ Features & Tools

The application provides a complete suite of 12 PDF manipulation tools:

### 1. Organize & Split
- **Merge PDF**: Combine multiple PDFs into a single file with custom drag-and-drop reordering.
- **Split PDF**: Extract custom page ranges (e.g. `1-3, 5, 8-10`) or extract all pages as individual PDFs packaged into a ZIP.
- **Organize PDF**: Interactive page thumbnail grid — drag to reorder pages, rotate individual pages 90°, or delete unwanted pages before export.
- **Rotate PDF**: Rotate pages 90° clockwise, 180°, or 270° counter-clockwise.

### 2. Optimize & Convert
- **Compress PDF**: Smart stream optimization, garbage collection, and image downscaling. Displays original vs. compressed size and savings percentage.
- **PDF to JPG / PNG**: Render PDF pages into high-resolution images (at 150 or 300 DPI), bundled as individual files or a ZIP archive.
- **JPG / Images to PDF**: Convert JPG, PNG, and WebP images to a standardized PDF with customizable page orientation (Auto, Portrait, Landscape) and margins.
- **PDF to Text**: Extract all text content with page-by-page demarcation into a searchable `.txt` file with in-browser snippet preview.

### 3. Edit & Security
- **Protect PDF**: Encrypt documents with AES-256 standard encryption and password protection.
- **Unlock PDF**: Permanently decrypt password-protected PDF files.
- **Add Watermark**: Stamp text watermarks with customizable text, opacity, rotation angle, position (Center, Diagonal, Top, Bottom), and color.
- **Page Numbers**: Add page numbering across all pages with custom formatting (`Page {n} of {total}`) and 6 position presets.

---

## 🎨 UI & Design Principles
- **Modern & Professional**: Clean, uncluttered interface inspired by Linear, Stripe, and modern document utilities.
- **Dark Mode & Light Mode**: Built-in instant theme switcher persisted via `localStorage`.
- **Live Search & Category Filters**: Real-time filtering by category (Organize, Optimize, Convert, Edit, Security) and keyword search.
- **Drag-and-Drop Dropzone**: Native file dropzones supporting single and multi-file selection.
- **Privacy First**: Files are stored temporarily in `media/` and can be purged immediately via the "Delete now" button, or automatically purged after 2 hours.

---

## 🚀 How to Run Locally

### 1. Install Dependencies
```bash
python -m pip install django pypdf pymupdf reportlab pillow requests
```

### 2. Run Database Migrations
```bash
python manage.py migrate
```

### 3. Start Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```

Open your browser and navigate to:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 📂 Project Structure
```text
PDFUtils/
├── manage.py
├── pdfsite/                  # Django project root configuration
│   ├── settings.py           # Configured apps, media/static, upload limits
│   ├── urls.py               # Main URL router
│   ├── wsgi.py
│   └── asgi.py
├── pdfapp/                   # Core application
│   ├── constants.py          # Tool definitions, categories, metadata
│   ├── context_processors.py # Injects tools & categories into all templates
│   ├── services.py           # PyMuPDF, ReportLab & Pillow processing engine
│   ├── views.py              # AJAX processing endpoints, preview, download
│   └── urls.py               # Application routes
├── templates/
│   ├── base.html             # Base layout, navigation, dark mode, footer
│   ├── home.html             # Homepage with tool grid & search
│   └── tool_page.html        # Interactive workspace, dropzone & options
├── static/
│   ├── css/main.css          # Design system & tokens (dark/light themes)
│   └── js/app.js             # Drag-drop, sorting, previews, fetch API
└── media/                    # Local storage for uploads, processed files, thumbs
```
