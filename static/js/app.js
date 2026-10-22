/**
 * PDFly - Modern Frontend Architecture
 */

// Theme Management (Dark / Light Mode)
(function initTheme() {
  const savedTheme = localStorage.getItem('pdf_theme') || 
    (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', savedTheme);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const target = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  localStorage.setItem('pdf_theme', target);
}

// Toast Notifications
function showToast(message, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${message}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Global Tool Controller
class ToolController {
  constructor(config) {
    this.config = config;
    this.files = [];
    this.pages = []; // For organize tool
    this.pageRotations = {}; // page_index -> angle
    this.deletedPages = new Set();
    this.currentSessionId = null;

    this.dropzone = document.getElementById('dropzone');
    this.fileInput = document.getElementById('fileInput');
    this.workspace = document.getElementById('fileWorkspace');
    this.resultScreen = document.getElementById('resultScreen');
    this.processingModal = document.getElementById('processingModal');
    this.actionBtn = document.getElementById('actionBtn');

    this.initEvents();
  }

  initEvents() {
    if (!this.dropzone || !this.fileInput) return;

    // Dropzone click
    this.dropzone.addEventListener('click', () => this.fileInput.click());

    // File input change
    this.fileInput.addEventListener('change', (e) => {
      this.handleFiles(e.target.files);
    });

    // Drag and drop events
    ['dragenter', 'dragover'].forEach(name => {
      this.dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      this.dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.dropzone.classList.remove('dragover');
      });
    });

    this.dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files) {
        this.handleFiles(e.dataTransfer.files);
      }
    });

    // Action button execution
    if (this.actionBtn) {
      this.actionBtn.addEventListener('click', () => this.processTool());
    }

    // Add more files button inside workspace
    const addMoreBtn = document.getElementById('addMoreBtn');
    if (addMoreBtn) {
      addMoreBtn.addEventListener('click', () => this.fileInput.click());
    }
  }

  handleFiles(fileList) {
    if (!fileList || fileList.length === 0) return;

    if (this.config.multiple) {
      Array.from(fileList).forEach(f => this.files.push(f));
    } else {
      this.files = [fileList[0]];
    }

    this.renderWorkspace();

    // If this is organize-pdf, split-pdf or rotate-pdf, request preview thumbnails
    if (['organize-pdf', 'split-pdf', 'rotate-pdf'].includes(this.config.slug) && this.files.length > 0) {
      this.loadThumbnails(this.files[0]);
    }
  }

  async loadThumbnails(file) {
    const previewStage = document.getElementById('previewStage');
    if (!previewStage) return;

    previewStage.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:300px; color:var(--text-tertiary);">
        <div class="spinner" style="width:36px; height:36px; margin-bottom:1rem;"></div>
        <p>Loading page previews...</p>
      </div>
    `;

    const formData = new FormData();
    formData.append('file', file);

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    try {
      const response = await fetch('/api/preview/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData
      });

      const data = await response.json();
      if (data.success) {
        this.currentSessionId = data.session_id;
        this.pages = data.thumbnails;
        this.pageRotations = {};
        this.deletedPages.clear();
        this.renderPagesGrid();
      } else {
        showToast(data.error || 'Failed to render page thumbnails', 'error');
        this.renderFallbackPreview();
      }
    } catch (err) {
      showToast('Error generating page previews', 'error');
      this.renderFallbackPreview();
    }
  }

  renderFallbackPreview() {
    const previewStage = document.getElementById('previewStage');
    if (!previewStage) return;
    previewStage.innerHTML = `
      <div style="text-align:center; padding:3rem 1rem;">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom:1rem; color:var(--brand-primary);"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
        <h4 style="font-size:1.1rem; margin-bottom:0.25rem;">${this.files[0].name}</h4>
        <p style="color:var(--text-secondary); font-size:0.875rem;">${formatBytes(this.files[0].size)}</p>
      </div>
    `;
  }

  renderWorkspace() {
    this.dropzone.style.display = 'none';
    this.workspace.classList.add('active');

    // Update workspace header info
    const workspaceFileName = document.getElementById('workspaceFileName');
    if (workspaceFileName) {
      if (this.files.length === 1) {
        workspaceFileName.textContent = `${this.files[0].name} (${formatBytes(this.files[0].size)})`;
      } else {
        const totalSize = this.files.reduce((acc, f) => acc + f.size, 0);
        workspaceFileName.textContent = `${this.files.length} files selected (${formatBytes(totalSize)})`;
      }
    }

    // Render list for multi-file tools (Merge, JPG to PDF)
    if (this.config.multiple) {
      this.renderFileList();
    } else if (!['organize-pdf', 'split-pdf', 'rotate-pdf'].includes(this.config.slug)) {
      this.renderFallbackPreview();
    }
  }

  renderFileList() {
    const previewStage = document.getElementById('previewStage');
    if (!previewStage) return;

    let html = `<div class="file-list" id="sortableFileList">`;
    this.files.forEach((file, index) => {
      html += `
        <div class="file-row-item" data-index="${index}" draggable="true">
          <div class="file-row-left">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--brand-primary);"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            <div>
              <div class="file-row-name">${file.name}</div>
              <div class="file-row-size">${formatBytes(file.size)}</div>
            </div>
          </div>
          <div class="file-row-actions">
            <button type="button" class="btn-icon" style="width:30px; height:30px;" onclick="window.toolInstance.moveFile(${index}, -1)" ${index === 0 ? 'disabled' : ''} title="Move Up">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"></polyline></svg>
            </button>
            <button type="button" class="btn-icon" style="width:30px; height:30px;" onclick="window.toolInstance.moveFile(${index}, 1)" ${index === this.files.length - 1 ? 'disabled' : ''} title="Move Down">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </button>
            <button type="button" class="btn-icon" style="width:30px; height:30px; color:var(--danger);" onclick="window.toolInstance.removeFile(${index})" title="Remove">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>
      `;
    });
    html += `</div>`;
    previewStage.innerHTML = html;
  }

  moveFile(index, dir) {
    const target = index + dir;
    if (target < 0 || target >= this.files.length) return;
    const temp = this.files[index];
    this.files[index] = this.files[target];
    this.files[target] = temp;
    this.renderFileList();
  }

  removeFile(index) {
    this.files.splice(index, 1);
    if (this.files.length === 0) {
      this.resetTool();
    } else {
      this.renderWorkspace();
    }
  }

  renderPagesGrid() {
    const previewStage = document.getElementById('previewStage');
    if (!previewStage) return;

    let html = `<div class="pages-grid" id="pagesGrid">`;
    this.pages.forEach((page, orderIndex) => {
      const origIndex = page.index;
      const isDeleted = this.deletedPages.has(origIndex);
      const rot = this.pageRotations[origIndex] || 0;

      html += `
        <div class="page-item-card ${isDeleted ? 'deleted' : ''}" data-orig-index="${origIndex}" data-order="${orderIndex}" draggable="${!isDeleted}">
          <img src="${page.url}" alt="Page ${page.page_number}" class="page-item-thumb" style="transform: rotate(${rot}deg);" />
          <div class="page-item-footer">
            <span>Page ${page.page_number}</span>
            <div class="page-item-actions">
              <button type="button" class="page-action-btn" onclick="window.toolInstance.rotatePage(${origIndex})" title="Rotate 90°">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
              </button>
              <button type="button" class="page-action-btn" onclick="window.toolInstance.toggleDeletePage(${origIndex})" title="${isDeleted ? 'Restore Page' : 'Delete Page'}">
                ${isDeleted ? 
                  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>' : 
                  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>'
                }
              </button>
            </div>
          </div>
        </div>
      `;
    });
    html += `</div>`;
    previewStage.innerHTML = html;

    this.initDragSort();
  }

  rotatePage(origIndex) {
    const current = this.pageRotations[origIndex] || 0;
    this.pageRotations[origIndex] = (current + 90) % 360;
    this.renderPagesGrid();
  }

  toggleDeletePage(origIndex) {
    if (this.deletedPages.has(origIndex)) {
      this.deletedPages.delete(origIndex);
    } else {
      if (this.deletedPages.size >= this.pages.length - 1) {
        showToast("You cannot delete all pages. At least one page must remain.", "error");
        return;
      }
      this.deletedPages.add(origIndex);
    }
    this.renderPagesGrid();
  }

  initDragSort() {
    const grid = document.getElementById('pagesGrid');
    if (!grid) return;

    let draggedItem = null;

    grid.querySelectorAll('.page-item-card').forEach(item => {
      item.addEventListener('dragstart', (e) => {
        draggedItem = item;
        item.classList.add('is-dragging');
        e.dataTransfer.effectAllowed = 'move';
      });

      item.addEventListener('dragend', () => {
        if (draggedItem) draggedItem.classList.remove('is-dragging');
        draggedItem = null;
      });

      item.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (item !== draggedItem && !item.classList.contains('deleted')) {
          const bounding = item.getBoundingClientRect();
          const offset = e.clientX - bounding.left;
          if (offset > bounding.width / 2) {
            item.after(draggedItem);
          } else {
            item.before(draggedItem);
          }
        }
      });

      item.addEventListener('drop', (e) => {
        e.preventDefault();
        // Re-sync this.pages array from DOM order
        const newOrder = [];
        grid.querySelectorAll('.page-item-card').forEach(card => {
          const origIdx = parseInt(card.getAttribute('data-orig-index'), 10);
          const pageObj = this.pages.find(p => p.index === origIdx);
          if (pageObj) newOrder.push(pageObj);
        });
        this.pages = newOrder;
      });
    });
  }

  async processTool() {
    if (this.files.length === 0) {
      showToast('Please select file(s) to process', 'error');
      return;
    }

    const formData = new FormData();
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    // Append files
    if (this.config.multiple) {
      this.files.forEach(f => formData.append('files', f));
      // Append file order
      const fileNames = this.files.map(f => f.name);
      formData.append('file_order', JSON.stringify(fileNames));
    } else {
      formData.append('file', this.files[0]);
    }

    // Collect tool-specific form inputs
    const optionsForm = document.getElementById('optionsForm');
    if (optionsForm) {
      const inputs = optionsForm.querySelectorAll('input, select, textarea');
      inputs.forEach(input => {
        if (input.type === 'radio') {
          if (input.checked) formData.append(input.name, input.value);
        } else if (input.type === 'checkbox') {
          formData.append(input.name, input.checked);
        } else {
          formData.append(input.name, input.value);
        }
      });
    }

    // Organize PDF specific params
    if (this.config.slug === 'organize-pdf') {
      const finalOrder = [];
      this.pages.forEach(p => {
        if (!this.deletedPages.has(p.index)) {
          finalOrder.push(p.index);
        }
      });
      formData.append('page_order', JSON.stringify(finalOrder));
      formData.append('page_rotations', JSON.stringify(this.pageRotations));
    }

    // Show processing modal
    this.processingModal.classList.add('active');

    try {
      const response = await fetch(`/api/process/${this.config.slug}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData
      });

      const data = await response.json();
      this.processingModal.classList.remove('active');

      if (data.success) {
        this.renderSuccess(data);
      } else {
        showToast(data.error || 'An error occurred while processing', 'error');
      }
    } catch (err) {
      this.processingModal.classList.remove('active');
      showToast('Server communication failure. Please try again.', 'error');
    }
  }

  renderSuccess(data) {
    this.workspace.style.display = 'none';
    this.resultScreen.classList.add('active');

    const downloadBtn = document.getElementById('resultDownloadBtn');
    if (downloadBtn) {
      downloadBtn.href = data.download_url;
      downloadBtn.download = data.filename || 'processed_file.pdf';
    }

    const resultMessage = document.getElementById('resultMessage');
    if (resultMessage && data.message) {
      resultMessage.textContent = data.message;
    }

    const statNewSize = document.getElementById('statNewSize');
    if (statNewSize) {
      statNewSize.textContent = formatBytes(data.file_size);
    }

    // Compression stats
    const compressionStats = document.getElementById('compressionStats');
    if (compressionStats) {
      if (data.savings_pct !== undefined && data.savings_pct > 0) {
        compressionStats.style.display = 'flex';
        document.getElementById('statOriginalSize').textContent = formatBytes(data.original_size);
        document.getElementById('statSavingsPct').textContent = `${data.savings_pct}%`;
      } else {
        compressionStats.style.display = 'none';
      }
    }

    // Text preview snippet if pdf-to-text
    const textSnippetBox = document.getElementById('textSnippetBox');
    if (textSnippetBox && data.preview_snippet) {
      textSnippetBox.style.display = 'block';
      textSnippetBox.textContent = data.preview_snippet;
    }

    // Immediate cleanup button
    const deleteNowBtn = document.getElementById('deleteNowBtn');
    if (deleteNowBtn) {
      deleteNowBtn.onclick = async () => {
        if (!confirm('Are you sure you want to permanently delete this file now?')) return;
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        try {
          const res = await fetch(`/api/cleanup/${data.file_id}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken }
          });
          const resJson = await res.json();
          if (resJson.success) {
            showToast('File permanently deleted from server.', 'success');
            setTimeout(() => window.location.reload(), 1200);
          }
        } catch (e) {
          showToast('Could not delete file', 'error');
        }
      };
    }
  }

  resetTool() {
    this.files = [];
    this.pages = [];
    this.pageRotations = {};
    this.deletedPages.clear();
    this.fileInput.value = '';
    this.workspace.classList.remove('active');
    this.resultScreen.classList.remove('active');
    this.dropzone.style.display = 'block';
  }
}

// Homepage Search and Filtering
document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('toolSearchInput');
  const categoryPills = document.querySelectorAll('.category-pill');
  const toolCards = document.querySelectorAll('.tool-card');

  if (searchInput && toolCards.length > 0) {
    function filterCards() {
      const query = (searchInput.value || '').toLowerCase().trim();
      const activePill = document.querySelector('.category-pill.active');
      const activeCat = activePill ? activePill.getAttribute('data-category') : 'All';

      toolCards.forEach(card => {
        const title = (card.getAttribute('data-title') || '').toLowerCase();
        const desc = (card.getAttribute('data-desc') || '').toLowerCase();
        const cat = card.getAttribute('data-category') || '';

        const matchesQuery = !query || title.includes(query) || desc.includes(query);
        const matchesCategory = activeCat === 'All' || cat === activeCat;

        if (matchesQuery && matchesCategory) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
    }

    searchInput.addEventListener('input', filterCards);

    categoryPills.forEach(pill => {
      pill.addEventListener('click', () => {
        categoryPills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        filterCards();
      });
    });
  }
});
