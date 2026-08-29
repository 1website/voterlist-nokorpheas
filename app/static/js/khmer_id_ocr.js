// =========================================================================
// KHMER NATIONAL ID CARD CAMERA OCR SCANNER & AUTO-FILL SYSTEM
// =========================================================================

let ocrMediaStream = null;
let ocrFacingMode = "environment"; // default to rear camera on mobile
let ocrCurrentCapturedImage = null;
let ocrExtractedData = null;

/**
 * Open the ID Card OCR Scanner Modal
 */
function openIdCardOcrModal() {
    openModal('ocrScannerModal');
    switchOcrTab('camera');
    startOcrCamera();
}

/**
 * Close the ID Card OCR Scanner Modal
 */
function closeIdCardOcrModal() {
    stopOcrCamera();
    closeModal('ocrScannerModal');
    resetOcrResults();
}

/**
 * Switch tabs between Live Camera and File Upload
 */
function switchOcrTab(tab) {
    const camTabBtn = document.getElementById('ocrTabCamBtn');
    const uploadTabBtn = document.getElementById('ocrTabUploadBtn');
    const camSection = document.getElementById('ocrCameraSection');
    const uploadSection = document.getElementById('ocrUploadSection');

    if (tab === 'camera') {
        if (camTabBtn) camTabBtn.className = "px-4 py-2 text-xs sm:text-sm font-bold rounded-xl bg-blue-600 text-white shadow-sm transition";
        if (uploadTabBtn) uploadTabBtn.className = "px-4 py-2 text-xs sm:text-sm font-semibold rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition";
        if (camSection) camSection.classList.remove('hidden');
        if (uploadSection) uploadSection.classList.add('hidden');
        startOcrCamera();
    } else {
        if (uploadTabBtn) uploadTabBtn.className = "px-4 py-2 text-xs sm:text-sm font-bold rounded-xl bg-blue-600 text-white shadow-sm transition";
        if (camTabBtn) camTabBtn.className = "px-4 py-2 text-xs sm:text-sm font-semibold rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition";
        if (uploadSection) uploadSection.classList.remove('hidden');
        if (camSection) camSection.classList.add('hidden');
        stopOcrCamera();
    }
}

/**
 * Start camera feed with card guide overlay
 */
async function startOcrCamera() {
    const video = document.getElementById('ocrCameraVideo');
    if (!video) return;

    stopOcrCamera();

    try {
        const constraints = {
            video: {
                facingMode: ocrFacingMode,
                width: { ideal: 1920, min: 1280 },
                height: { ideal: 1080, min: 720 }
            },
            audio: false
        };

        ocrMediaStream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = ocrMediaStream;
        await video.play();

        const statusEl = document.getElementById('ocrCameraStatus');
        if (statusEl) {
            statusEl.textContent = "កាមេរ៉ារួចរាល់៖ សូមដាក់អត្តសញ្ញាណប័ណ្ណក្នុងស៊ុម";
            statusEl.className = "text-[11px] text-emerald-600 dark:text-emerald-400 font-medium";
        }
    } catch (err) {
        console.warn("Camera start warning:", err);
        const statusEl = document.getElementById('ocrCameraStatus');
        if (statusEl) {
            statusEl.textContent = "មិនអាចបើកកាមេរ៉ាបានទេ។ សូមប្រើប្រាស់ការ Upload រូបថតជំនួសវិញ";
            statusEl.className = "text-[11px] text-rose-500 font-medium";
        }
    }
}

/**
 * Stop live camera feed
 */
function stopOcrCamera() {
    if (ocrMediaStream) {
        ocrMediaStream.getTracks().forEach(track => track.stop());
        ocrMediaStream = null;
    }
    const video = document.getElementById('ocrCameraVideo');
    if (video) {
        video.srcObject = null;
    }
}

/**
 * Switch between Front & Rear Camera
 */
function switchOcrCameraFacing() {
    ocrFacingMode = (ocrFacingMode === "environment") ? "user" : "environment";
    startOcrCamera();
}

/**
 * Capture photo from camera and process OCR
 */
async function captureAndScanIdCard() {
    const video = document.getElementById('ocrCameraVideo');
    if (!video || !ocrMediaStream) {
        showToast("សូមបើកកាមេរ៉ាជាមុនសិន", "warning");
        return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const base64Data = canvas.toDataURL('image/jpeg', 0.92);
    ocrCurrentCapturedImage = base64Data;

    await executeOcrRecognition(base64Data, null);
}

/**
 * Handle direct file upload from computer or phone gallery
 */
async function handleOcrFileUpload(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];

    const reader = new FileReader();
    reader.onload = async (e) => {
        const base64Data = e.target.result;
        ocrCurrentCapturedImage = base64Data;
        await executeOcrRecognition(base64Data, file);
    };
    reader.readAsDataURL(file);
}

/**
 * Core OCR Recognition Engine: Runs Client-side Tesseract.js (if available) + Server-side AI Parser
 */
async function executeOcrRecognition(base64Image, fileObject) {
    const processingEl = document.getElementById('ocrProcessingOverlay');
    const resultBox = document.getElementById('ocrResultBox');
    const errorBox = document.getElementById('ocrErrorBox');

    if (processingEl) processingEl.classList.remove('hidden');
    if (resultBox) resultBox.classList.add('hidden');
    if (errorBox) errorBox.classList.add('hidden');

    let clientRecognizedText = "";

    // 1. Client-Side OCR with Tesseract.js if library loaded
    if (typeof Tesseract !== 'undefined') {
        try {
            const statusTextEl = document.getElementById('ocrProgressStatus');
            if (statusTextEl) statusTextEl.textContent = "កំពុងអានអក្សរលើអត្តសញ្ញាណប័ណ្ណ (OCR Reading)...";

            const ocrResult = await Tesseract.recognize(base64Image, 'eng+khm', {
                logger: m => {
                    if (m.status === 'recognizing text' && statusTextEl) {
                        statusTextEl.textContent = `កំពុងវិភាគអក្សរ... ${Math.round(m.progress * 100)}%`;
                    }
                }
            });
            clientRecognizedText = ocrResult.data.text || "";
        } catch (tessErr) {
            console.warn("Client OCR notice:", tessErr);
        }
    }

    // 2. Send to Backend API for structured parsing, validation, and facial portrait crop
    try {
        const statusTextEl = document.getElementById('ocrProgressStatus');
        if (statusTextEl) statusTextEl.textContent = "កំពុងកាត់យករូបថតមុខ & ទាញយកទិន្នន័យ...";

        const formData = new FormData();
        if (fileObject) {
            formData.append('image', fileObject);
        }
        formData.append('image_base64', base64Image);
        formData.append('client_text', clientRecognizedText);

        const response = await fetch('/api/voters/ocr-id-card', {
            method: 'POST',
            body: formData
        });

        const resData = await response.json();

        if (response.ok && resData.success) {
            ocrExtractedData = resData.data;
            displayOcrResults(ocrExtractedData, base64Image);
            playAudioBeep(true);
        } else {
            throw new Error(resData.detail || "មិនអាចអានទិន្នន័យបានពេញលេញឡើយ");
        }
    } catch (err) {
        console.error("OCR execution error:", err);
        if (errorBox) {
            errorBox.classList.remove('hidden');
            const errMsg = document.getElementById('ocrErrorMsg');
            if (errMsg) errMsg.textContent = err.message || "មានបញ្ហាក្នុងការអានរូបភាព សូមសាកល្បងថតសារជាថ្មី";
        }
        playAudioBeep(false);
    } finally {
        if (processingEl) processingEl.classList.add('hidden');
    }
}

/**
 * Display the Extracted Results with verification form & portrait preview
 */
function displayOcrResults(data, cardImage) {
    const resultBox = document.getElementById('ocrResultBox');
    if (!resultBox) return;

    resultBox.classList.remove('hidden');

    // Populate images
    const portraitImg = document.getElementById('ocrExtractedPhoto');
    if (portraitImg) {
        portraitImg.src = data.photo_url || cardImage || '/static/images/avatars/male_1.jpg';
    }
    const cardImg = document.getElementById('ocrSnapshotPreview');
    if (cardImg) {
        cardImg.src = cardImage;
    }

    // Populate input fields for user review / adjustment
    const idInput = document.getElementById('ocrFieldNationalId');
    if (idInput) idInput.value = data.national_id || "";

    const nameKhInput = document.getElementById('ocrFieldNameKh');
    if (nameKhInput) nameKhInput.value = data.name_kh || "";

    const nameEnInput = document.getElementById('ocrFieldNameEn');
    if (nameEnInput) nameEnInput.value = data.name_en || "";

    const genderSelect = document.getElementById('ocrFieldGender');
    if (genderSelect) genderSelect.value = data.gender || "ប្រុស";

    const dobInput = document.getElementById('ocrFieldDob');
    if (dobInput) dobInput.value = data.dob || "1995-05-15";

    // Duplicate ID Warning Badge
    const dupBadge = document.getElementById('ocrDuplicateAlert');
    if (dupBadge) {
        if (data.is_duplicate) {
            dupBadge.classList.remove('hidden');
            const dupText = document.getElementById('ocrDuplicateText');
            if (dupText) dupText.textContent = `លេខអត្តសញ្ញាណប័ណ្ណនេះធ្លាប់បានចុះឈ្មោះរួចហើយ៖ ${data.duplicate_name}`;
        } else {
            dupBadge.classList.add('hidden');
        }
    }

    // Age eligibility badge
    const ageBadge = document.getElementById('ocrAgeBadge');
    if (ageBadge) {
        if (data.age && data.age >= 18) {
            ageBadge.className = "badge badge-success text-xs px-2.5 py-1";
            ageBadge.textContent = `អាយុ ${data.age} ឆ្នាំ (គ្រប់អាយុ ១៨+)`;
        } else if (data.age) {
            ageBadge.className = "badge badge-danger text-xs px-2.5 py-1";
            ageBadge.textContent = `អាយុ ${data.age} ឆ្នាំ (មិនទាន់គ្រប់ ១៨ ឆ្នាំ)`;
        } else {
            ageBadge.textContent = "";
        }
    }

    // Scroll result box into view smoothly
    resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/**
 * Apply the verified OCR data directly into Add Voter Modal
 */
function applyOcrDataToVoterForm() {
    const nationalId = document.getElementById('ocrFieldNationalId')?.value || "";
    const nameKh = document.getElementById('ocrFieldNameKh')?.value || "";
    const nameEn = document.getElementById('ocrFieldNameEn')?.value || "";
    const gender = document.getElementById('ocrFieldGender')?.value || "ប្រុស";
    const dob = document.getElementById('ocrFieldDob')?.value || "1995-05-15";
    const photoUrl = document.getElementById('ocrExtractedPhoto')?.src || "";

    // Close OCR Scanner Modal
    closeIdCardOcrModal();

    // Open Add Voter Modal if not already open
    openAddVoterModal();

    // Fill inputs in Add Voter Modal
    const targetNameKh = document.querySelector('#addVoterForm input[name="name_kh"]');
    if (targetNameKh) targetNameKh.value = nameKh;

    const targetNameEn = document.querySelector('#addVoterForm input[name="name_en"]');
    if (targetNameEn) targetNameEn.value = nameEn;

    const targetGender = document.getElementById('addGenderSelect');
    if (targetGender) {
        targetGender.value = gender;
    }

    const targetDob = document.getElementById('addDobInput');
    if (targetDob) {
        targetDob.value = dob;
        if (typeof checkVoterAge === 'function') {
            checkVoterAge(targetDob, 'addDobFeedback', 'addVoterSubmitBtn');
        }
    }

    const targetNationalId = document.getElementById('addNationalId');
    if (targetNationalId) {
        targetNationalId.value = nationalId;
        if (typeof checkDuplicateID === 'function') {
            checkDuplicateID(targetNationalId);
        }
    }

    // Set Photo Preview and Hidden Preset Input
    if (photoUrl && !photoUrl.includes('/static/images/avatars/')) {
        const photoPreview = document.getElementById('addPhotoPreview');
        if (photoPreview) photoPreview.src = photoUrl;
        const presetInput = document.getElementById('addPresetInput');
        if (presetInput) presetInput.value = photoUrl;
    }

    showToast("បានបំពេញទិន្នន័យពីអត្តសញ្ញាណប័ណ្ណដោយជោគជ័យ! ✨", "success");
}

/**
 * Reset OCR state and inputs
 */
function resetOcrResults() {
    ocrCurrentCapturedImage = null;
    ocrExtractedData = null;
    const resultBox = document.getElementById('ocrResultBox');
    if (resultBox) resultBox.classList.add('hidden');
    const errorBox = document.getElementById('ocrErrorBox');
    if (errorBox) errorBox.classList.add('hidden');
    const fileInput = document.getElementById('ocrFileInput');
    if (fileInput) fileInput.value = '';
}
