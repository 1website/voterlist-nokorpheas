/**
 * OFFICIAL PDF BULK VOTER IMPORTER
 * Handles uploading NEC 2025 official voter list PDF files,
 * extracting metadata & portrait face photos, previewing, and committing to DB.
 */

let currentPdfFile = null;
let currentPreviewData = null;

/**
 * Open the PDF Importer Modal
 */
function openPdfImportModal() {
    resetPdfImportModal();
    if (typeof openModal === 'function') {
        openModal('pdfImportModal');
    } else {
        const m = document.getElementById('pdfImportModal');
        if (m) m.classList.add('active');
    }
}

/**
 * Close the PDF Importer Modal
 */
function closePdfImportModal() {
    if (typeof closeModal === 'function') {
        closeModal('pdfImportModal');
    } else {
        const m = document.getElementById('pdfImportModal');
        if (m) m.classList.remove('active');
    }
}

/**
 * Reset modal to initial state
 */
function resetPdfImportModal() {
    currentPdfFile = null;
    currentPreviewData = null;

    const fileInput = document.getElementById('pdfFileInput');
    if (fileInput) fileInput.value = '';

    document.getElementById('pdfDropZone')?.classList.remove('hidden');
    document.getElementById('pdfLoadingOverlay')?.classList.add('hidden');
    document.getElementById('pdfErrorBox')?.classList.add('hidden');
    document.getElementById('pdfPreviewSection')?.classList.add('hidden');
    document.getElementById('pdfConfirmBtn')?.classList.add('hidden');
}

/**
 * Handle File Selection from Input or Drop
 */
function handlePdfFileSelect(input) {
    if (input.files && input.files[0]) {
        processPdfFile(input.files[0]);
    }
}

/**
 * Setup Drag & Drop Handlers
 */
document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('pdfDropZone');
    if (dropZone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('border-purple-500', 'bg-purple-50/50', 'dark:bg-purple-950/30');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('border-purple-500', 'bg-purple-50/50', 'dark:bg-purple-950/30');
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files[0]) {
                const file = dt.files[0];
                if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
                    processPdfFile(file);
                } else {
                    showToast('សូមជ្រើសរើសឯកសារជាទម្រង់ PDF (.pdf) តែប៉ុណ្ណោះ', 'warning');
                }
            }
        });
    }
});

/**
 * Upload and parse PDF for preview
 */
async function processPdfFile(file) {
    if (!file) return;
    currentPdfFile = file;

    const dropZone = document.getElementById('pdfDropZone');
    const loadingOverlay = document.getElementById('pdfLoadingOverlay');
    const errorBox = document.getElementById('pdfErrorBox');
    const previewSection = document.getElementById('pdfPreviewSection');
    const confirmBtn = document.getElementById('pdfConfirmBtn');

    dropZone?.classList.add('hidden');
    errorBox?.classList.add('hidden');
    previewSection?.classList.add('hidden');
    confirmBtn?.classList.add('hidden');
    loadingOverlay?.classList.remove('hidden');

    const statusText = document.getElementById('pdfLoadingStatus');
    if (statusText) {
        statusText.textContent = `កំពុងអានឯកសារ '${file.name}' និងស្រង់ទិន្នន័យ...`;
    }

    try {
        const formData = new FormData();
        formData.append('pdf_file', file);

        const response = await fetch('/api/voters/import-pdf/preview', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.detail || 'បរាជ័យក្នុងការអានឯកសារ PDF');
        }

        currentPreviewData = data;
        renderPdfPreview(data);

        loadingOverlay?.classList.add('hidden');
        previewSection?.classList.remove('hidden');
        confirmBtn?.classList.remove('hidden');

        showToast(`ស្រង់បានអ្នកបោះឆ្នោត ${data.total_voters} នាក់ (${data.total_pages} ទំព័រ) ជោគជ័យ!`, 'success');

    } catch (err) {
        console.error('PDF Preview error:', err);
        loadingOverlay?.classList.add('hidden');
        if (errorBox) {
            errorBox.classList.remove('hidden');
            const errorMsg = document.getElementById('pdfErrorMsg');
            if (errorMsg) errorMsg.textContent = err.message || 'មិនអាចអានឯកសារ PDF នេះបានឡើយ';
        }
        dropZone?.classList.remove('hidden');
    }
}

/**
 * Render the Preview Data in UI
 */
function renderPdfPreview(data) {
    const header = data.header || {};
    
    // Header tags
    const titleEl = document.getElementById('pdfMetaTitle');
    if (titleEl) {
        titleEl.textContent = `បញ្ជីបោះឆ្នោតផ្លូវការ ឆ្នាំ ${header.year || 2025} • ការិយាល័យលេខ ${header.station_code || ''}`;
    }

    const subtitleEl = document.getElementById('pdfMetaSubtitle');
    if (subtitleEl) {
        subtitleEl.textContent = `ទីតាំង៖ ${header.station_location || ''} • ភូមិ ${header.village_name || ''} • ឃុំ ${header.commune_name || ''} (${header.province_name || ''})`;
    }

    // Counts
    const totalCountEl = document.getElementById('pdfTotalVotersBadge');
    if (totalCountEl) totalCountEl.textContent = data.total_voters;

    const newCountEl = document.getElementById('pdfNewCountBadge');
    if (newCountEl) newCountEl.textContent = data.new_count;

    const femaleCountEl = document.getElementById('pdfFemaleCountBadge');
    if (femaleCountEl) femaleCountEl.textContent = data.female_count || 0;

    const maleCountEl = document.getElementById('pdfMaleCountBadge');
    if (maleCountEl) maleCountEl.textContent = data.male_count || 0;

    const dupCountEl = document.getElementById('pdfDupCountBadge');
    if (dupCountEl) dupCountEl.textContent = data.duplicate_count;

    const pagesEl = document.getElementById('pdfPagesBadge');
    if (pagesEl) pagesEl.textContent = data.total_pages;

    // Pre-populate Station and Village dropdowns
    const stationSel = document.getElementById('pdfStationSelect');
    if (stationSel && data.matched_station && data.matched_station.id) {
        stationSel.value = data.matched_station.id;
    }

    const villageSel = document.getElementById('pdfVillageSelect');
    if (villageSel && data.matched_village && data.matched_village.id) {
        villageSel.value = data.matched_village.id;
    }

    // Render Preview Table Rows
    const tbody = document.getElementById('pdfPreviewTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const records = data.preview_records || [];
    records.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-800/50 transition border-b border-slate-100 dark:border-slate-800 text-xs';
        
        const photoSrc = r.photo_url || (r.gender === 'ស្រី' ? '/static/images/avatars/female_1.jpg' : '/static/images/avatars/male_1.jpg');
        const statusBadge = r.is_duplicate 
            ? '<span class="badge badge-warning text-[10px] px-1.5 py-0.5">🔄 មានស្រាប់</span>'
            : '<span class="badge badge-success text-[10px] px-1.5 py-0.5">✨ ថ្មី</span>';
        
        const genderBadge = r.gender === 'ស្រី'
            ? '<span class="text-pink-600 dark:text-pink-400 font-bold">ស្រី</span>'
            : '<span class="text-blue-600 dark:text-sky-400 font-bold">ប្រុស</span>';

        tr.innerHTML = `
            <td class="p-2 text-center font-bold text-slate-500">${r.list_no}</td>
            <td class="p-2 text-center">
                <img src="${photoSrc}" alt="Face" class="w-8 h-9 object-cover rounded-lg border border-slate-200 shadow-xs mx-auto">
            </td>
            <td class="p-2 font-mono font-bold text-blue-700 dark:text-sky-300 whitespace-nowrap">${r.voter_code}</td>
            <td class="p-2 font-bold text-slate-900 dark:text-slate-100 whitespace-nowrap">
                <div>${r.name_kh}</div>
                <div class="text-[10px] text-slate-400 font-mono">${r.name_en || ''}</div>
            </td>
            <td class="p-2 text-center whitespace-nowrap">${genderBadge}</td>
            <td class="p-2 text-center font-mono whitespace-nowrap">${r.dob}</td>
            <td class="p-2 text-slate-600 dark:text-slate-300 truncate max-w-[140px]">${r.address}</td>
            <td class="p-2 text-center whitespace-nowrap">${statusBadge}</td>
        `;
        tbody.appendChild(tr);
    });

    // Show note about preview limit
    const noteEl = document.getElementById('pdfPreviewLimitNote');
    if (noteEl) {
        noteEl.textContent = `បង្ហាញគំរូ ${records.length} នាក់ដំបូង ក្នុងចំណោមអ្នកបោះឆ្នោតសរុប ${data.total_voters} នាក់។ ពេលចុចបញ្ជាក់ ប្រព័ន្ធនឹងរក្សាទុកទាំងអស់ ១០០%។`;
    }
}

/**
 * Confirm and execute the import
 */
async function confirmPdfImport() {
    if (!currentPdfFile) {
        showToast('សូមជ្រើសរើសឯកសារ PDF ជាមុនសិន', 'warning');
        return;
    }

    const stationSel = document.getElementById('pdfStationSelect');
    const villageSel = document.getElementById('pdfVillageSelect');
    const updateDupCheck = document.getElementById('pdfUpdateExistingCheck');

    const stationId = stationSel ? stationSel.value : '';
    const villageId = villageSel ? villageSel.value : '';
    const updateExisting = updateDupCheck ? updateDupCheck.checked : true;

    if (!stationId) {
        showToast('សូមជ្រើសរើសការិយាល័យបោះឆ្នោត', 'warning');
        return;
    }
    if (!villageId) {
        showToast('សូមជ្រើសរើសភូមិ', 'warning');
        return;
    }

    const confirmBtn = document.getElementById('pdfConfirmBtn');
    const originalBtnHtml = confirmBtn ? confirmBtn.innerHTML : '';
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span>⏳</span> <span>កំពុងរក្សាទុកក្នុង Database...</span>';
    }

    try {
        const formData = new FormData();
        formData.append('pdf_file', currentPdfFile);
        formData.append('station_id', stationId);
        formData.append('village_id', villageId);
        formData.append('update_existing', updateExisting ? 'true' : 'false');

        const response = await fetch('/api/voters/import-pdf/confirm', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.detail || 'បរាជ័យក្នុងការរក្សាទុកទិន្នន័យ');
        }

        showToast(
            `នាំចូលបានជោគជ័យ! បញ្ចូលថ្មី៖ ${data.inserted} នាក់ • អាប់ដេត៖ ${data.updated} នាក់ (សរុប៖ ${data.total_records} នាក់)`,
            'success',
            6000
        );

        closePdfImportModal();

        // Reload page after a brief delay to display newly imported voters
        setTimeout(() => {
            window.location.href = `/voters?reg_type_filter=legacy&reg_year_filter=2025`;
        }, 1200);

    } catch (err) {
        console.error('Confirm Import error:', err);
        showToast(err.message || 'មានបញ្ហាក្នុងការរក្សាទុកទិន្នន័យ', 'error');
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalBtnHtml;
        }
    }
}
