// Toast notification system with smooth slideInRight and slideOutRight
function showToast(message, type = 'success', duration = 4500) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = '✓';
    let title = 'ប្រតិបត្តិការជោគជ័យ';
    if (type === 'error' || type === 'danger') {
        icon = '🚫';
        title = '⚠️ ស្ទួនទិន្នន័យ / កំហុសប្រតិបត្តិការ';
        playAudioBeep(false);
    } else if (type === 'warning') {
        icon = '⚡';
        title = 'ការព្រមាន';
        playAudioBeep(false);
    } else if (type === 'info') {
        icon = 'ℹ️';
        title = 'ព័ត៌មានប្រព័ន្ធ';
    } else {
        playAudioBeep(true);
    }

    toast.innerHTML = `
        <div class="toast-icon-wrap">${icon}</div>
        <div class="toast-content-wrap">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button type="button" class="toast-close-btn" onclick="dismissToast(this.closest('.toast'))" title="បិទ">✕</button>
    `;

    container.appendChild(toast);

    let dismissTimeout = setTimeout(() => {
        dismissToast(toast);
    }, duration);

    toast._dismissTimeout = dismissTimeout;
}

function dismissToast(toastElement) {
    if (!toastElement || toastElement._isDismissing) return;
    toastElement._isDismissing = true;
    if (toastElement._dismissTimeout) clearTimeout(toastElement._dismissTimeout);
    toastElement.classList.add('toast-dismissing');
    setTimeout(() => {
        if (toastElement && toastElement.parentNode) {
            toastElement.remove();
        }
    }, 320);
}

// Play confirmation audio beep
function playAudioBeep(isSuccess = true) {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (isSuccess) {
            osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5
            osc.frequency.setValueAtTime(1174.66, audioCtx.currentTime + 0.08); // D6
            gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.25);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.25);
        } else {
            osc.frequency.setValueAtTime(300, audioCtx.currentTime);
            osc.frequency.setValueAtTime(200, audioCtx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.3);
        }
    } catch (e) {
        console.log("Audio not supported or blocked", e);
    }
}

// 1-Click Voter Check-in Toggle
async function toggleCheckin(voterId, btnElement = null) {
    try {
        const response = await fetch(`/api/voters/${voterId}/checkin`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (response.ok && data.success) {
            playAudioBeep(data.has_voted);
            showToast(data.message, 'success');

            // Update UI elements on current page if present
            const statusBadge = document.getElementById(`voter-status-${voterId}`);
            if (statusBadge) {
                if (data.has_voted) {
                    statusBadge.className = 'badge badge-success';
                    statusBadge.innerHTML = `✓ បោះឆ្នោតរួច (${data.voted_at || ''})`;
                } else {
                    statusBadge.className = 'badge badge-secondary';
                    statusBadge.innerHTML = `⏳ មិនទាន់បោះ`;
                }
            }

            if (btnElement) {
                if (data.has_voted) {
                    btnElement.className = 'btn btn-sm btn-success bg-emerald-600 hover:bg-emerald-700 text-white font-bold';
                    btnElement.title = 'បានបោះឆ្នោតរួច (ចុចដើម្បីប្តូរមកមិនទាន់បោះ)';
                    btnElement.innerHTML = '✓';
                } else {
                    btnElement.className = 'btn btn-sm btn-outline text-slate-400 hover:text-emerald-600 hover:border-emerald-500';
                    btnElement.title = 'មិនទាន់បោះឆ្នោត (ចុចដើម្បីកំណត់ថាបានបោះ)';
                    btnElement.innerHTML = '⏳';
                }
            }

            // Refresh mini-counter if on dashboard
            if (typeof refreshDashboardStats === 'function') {
                refreshDashboardStats();
            }
        } else {
            playAudioBeep(false);
            showToast(data.detail || data.message || 'មានបញ្ហាក្នុងការ Check-in', 'error');
        }
    } catch (err) {
        showToast('កំហុសប្រព័ន្ធក្នុងការតភ្ជាប់', 'error');
    }
}

// Modal Helpers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Live Duplicate ID Checker
// Sanitize National ID Card (Only Latin digits 0-9, Max 9 digits)
function sanitizeNationalId(inputElement) {
    if (!inputElement) return "";
    // Khmer numerals mapping ០-៩ to 0-9
    const khmerDigits = {'០':'0', '១':'1', '២':'2', '៣':'3', '៤':'4', '៥':'5', '៦':'6', '៧':'7', '៨':'8', '៩':'9'};
    let val = inputElement.value;
    // Replace any Khmer numerals with Latin digits
    let clean = val.replace(/[០-៩]/g, d => khmerDigits[d] || d);
    // Remove any non-digit characters
    clean = clean.replace(/[^0-9]/g, '');
    // Limit to maximum 9 digits
    if (clean.length > 9) {
        clean = clean.slice(0, 9);
    }
    if (inputElement.value !== clean) {
        inputElement.value = clean;
    }
    return clean;
}

let duplicateTimer = null;
function checkDuplicateID(inputElement, excludeId = 0, feedbackId = 'idCheckFeedback') {
    sanitizeNationalId(inputElement);
    clearTimeout(duplicateTimer);
    const feedback = document.getElementById(feedbackId);
    const val = inputElement.value.trim();

    if (!val) {
        if (feedback) feedback.innerHTML = '';
        inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30', 'border-emerald-500', 'ring-1', 'ring-emerald-200');
        return;
    }

    // Determine document type by length:
    // Length 7 = ឯកសារបញ្ជាក់អត្តសញ្ញាណ (Certificate of Identity)
    // Length 9 = អត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ (National ID Card)
    if (val.length < 7) {
        if (feedback) {
            feedback.innerHTML = `
                <div class="text-xs text-slate-600 dark:text-slate-300 font-medium mt-1.5 flex items-center gap-1.5">
                    <span>⏳</span>
                    <span>កំពុងបញ្ចូល៖ <strong class="text-blue-700 dark:text-sky-300 font-mono font-bold">${val.length} ខ្ទង់</strong> (ឯកសារបញ្ជាក់អត្តសញ្ញាណ ៧ ខ្ទង់ ឬ អត្តសញ្ញាណប័ណ្ណ ៩ ខ្ទង់)</span>
                </div>
            `;
        }
        inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30', 'border-emerald-500', 'ring-1', 'ring-emerald-200');
        return;
    }

    if (val.length === 8) {
        if (feedback) {
            feedback.innerHTML = `
                <div class="text-xs text-amber-700 dark:text-amber-300 font-medium mt-1.5 flex items-center gap-1.5 bg-amber-50 dark:bg-amber-950/60 p-2 rounded-xl border border-amber-200 dark:border-amber-800/60">
                    <span>⚠️</span>
                    <span>បានបញ្ចូល <strong class="font-mono font-bold">៨ ខ្ទង់</strong> (ប្រសិនបើជាអត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ សូមបញ្ចូលឱ្យគ្រប់ <strong>៩ ខ្ទង់</strong>)</span>
                </div>
            `;
        }
        inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30', 'border-emerald-500', 'ring-1', 'ring-emerald-200');
        return;
    }

    // When length is 7 or 9 digits -> Valid format, check duplicate in database!
    const docTypeLabel = val.length === 7 ? 'ឯកសារបញ្ជាក់អត្តសញ្ញាណ (៧ ខ្ទង់)' : 'អត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ (៩ ខ្ទង់)';
    const docTypeIcon = val.length === 7 ? '📄' : '🪪';

    duplicateTimer = setTimeout(async () => {
        try {
            const res = await fetch(`/api/voters/check-duplicate-id?national_id=${encodeURIComponent(val)}&exclude_id=${excludeId}`);
            const data = await res.json();
            if (feedback) {
                if (data.duplicate) {
                    inputElement.classList.remove('border-emerald-500', 'ring-1', 'ring-emerald-200');
                    inputElement.classList.add('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
                    
                    if (window._lastIdDupToastMsg !== data.message) {
                        window._lastIdDupToastMsg = data.message;
                        showToast(data.message, 'error', 5500);
                    }

                    feedback.innerHTML = `
                        <div class="p-3 bg-rose-50 dark:bg-rose-950/70 border-2 border-rose-300 dark:border-rose-800 rounded-xl text-xs text-rose-800 dark:text-rose-200 flex items-start gap-2.5 shadow-sm mt-1.5">
                            <span class="text-lg leading-none flex-shrink-0">🚫</span>
                            <div>
                                <strong class="font-bold text-rose-900 dark:text-rose-100 block text-xs">⚠️ ស្ទួនទិន្នន័យ៖ លេខ${docTypeLabel}នេះ បានចុះឈ្មោះរួចហើយ!</strong>
                                <span class="mt-0.5 block leading-relaxed text-rose-700 dark:text-rose-300">${data.message}</span>
                            </div>
                        </div>
                    `;
                } else {
                    window._lastIdDupToastMsg = null;
                    inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
                    inputElement.classList.add('border-emerald-500', 'ring-1', 'ring-emerald-200');
                    feedback.innerHTML = `
                        <div class="p-2.5 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800/80 rounded-xl text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2 mt-1.5 shadow-2xs">
                            <span class="text-base leading-none">✅</span>
                            <div>
                                <strong class="font-bold text-emerald-900 dark:text-emerald-200">${docTypeIcon} លេខ${docTypeLabel} ត្រឹមត្រូវ</strong>
                                <span class="text-emerald-700 dark:text-emerald-400 ml-1">មិនស្ទួនក្នុងប្រព័ន្ធឡើយ អាចចុះឈ្មោះបាន។</span>
                            </div>
                        </div>
                    `;
                }
            }
        } catch (e) {
            console.error("ID duplication check error:", e);
        }
    }, 280);
}

// Calculate age and validate >= 18 years old
function calculateAgeFromDob(dobString) {
    if (!dobString) return null;
    let birthDate;
    if (dobString.includes('-')) {
        const parts = dobString.split('-');
        if (parts[0].length === 4) {
            birthDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        } else {
            birthDate = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
        }
    } else if (dobString.includes('/')) {
        const parts = dobString.split('/');
        if (parts[0].length === 4) {
            birthDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        } else {
            birthDate = new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
        }
    } else {
        birthDate = new Date(dobString);
    }
    if (!birthDate || isNaN(birthDate.getTime())) return null;
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const m = today.getMonth() - birthDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
        age--;
    }
    return age;
}

function checkVoterAge(inputElement, feedbackId, submitBtnId) {
    const feedback = document.getElementById(feedbackId);
    const submitBtn = submitBtnId ? document.getElementById(submitBtnId) : null;
    if (!inputElement || !inputElement.value) {
        if (feedback) feedback.innerHTML = '';
        inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30', 'border-emerald-500', 'ring-1', 'ring-emerald-200');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        return true;
    }

    const age = calculateAgeFromDob(inputElement.value);
    if (age === null) {
        if (feedback) feedback.innerHTML = '';
        return true;
    }

    if (age < 18) {
        inputElement.classList.remove('border-emerald-500', 'ring-1', 'ring-emerald-200');
        inputElement.classList.add('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
        if (feedback) {
            feedback.innerHTML = `
                <div class="p-2.5 bg-rose-50 dark:bg-rose-950/70 border-2 border-rose-300 dark:border-rose-800 rounded-xl text-xs text-rose-800 dark:text-rose-200 flex items-start gap-2 shadow-sm mt-1.5 animate-pulse">
                    <span class="text-base flex-shrink-0 leading-none">🚫</span>
                    <div>
                        <strong class="font-bold text-rose-900 dark:text-rose-100 block text-xs">មិនទាន់គ្រប់អាយុបោះឆ្នោត (អាយុត្រឹម ${age} ឆ្នាំ)!</strong>
                        <span class="mt-0.5 block leading-relaxed text-rose-700 dark:text-rose-300">យោងតាមច្បាប់បោះឆ្នោតជាតិ ពលរដ្ឋត្រូវមានអាយុយ៉ាងតិច <strong>១៨ ឆ្នាំឡើងទៅ</strong> ទើបមានសិទ្ធិចុះឈ្មោះបាន។</span>
                    </div>
                </div>
            `;
        }
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
        return false;
    } else {
        inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
        inputElement.classList.add('border-emerald-500', 'ring-1', 'ring-emerald-200');
        if (feedback) {
            feedback.innerHTML = `
                <div class="text-xs font-semibold mt-1.5 flex items-center gap-1.5 text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 py-1.5 px-3 rounded-xl border border-emerald-200 dark:border-emerald-800/80 shadow-2xs w-fit">
                    <span>✅</span>
                    <span>គ្រប់អាយុបោះឆ្នោត (អាយុ <strong>${age} ឆ្នាំ</strong>) អាចចុះឈ្មោះបាន</span>
                </div>
            `;
        }
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        return true;
    }
}

// Live Duplicate Birth Certificate Checker
let birthDupTimer = null;
function checkDuplicateBirthCert(certInputId, bookInputId, excludeId = 0, feedbackId = 'birthDupFeedback', submitBtnId = 'birthSubmitBtn') {
    clearTimeout(birthDupTimer);
    const certInput = document.getElementById(certInputId);
    const bookInput = document.getElementById(bookInputId);
    const feedback = document.getElementById(feedbackId);
    const submitBtn = submitBtnId ? document.getElementById(submitBtnId) : null;

    if (!certInput) return;
    const certVal = certInput.value.trim();
    const bookVal = bookInput ? bookInput.value.trim() : "";

    if (!certVal) {
        if (feedback) feedback.innerHTML = '';
        certInput.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30', 'border-emerald-500', 'ring-1', 'ring-emerald-200');
        if (bookInput) bookInput.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30', 'border-emerald-500', 'ring-1', 'ring-emerald-200');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        return;
    }

    birthDupTimer = setTimeout(async () => {
        try {
            const url = `/api/birth-certificates/check-duplicate?certificate_no=${encodeURIComponent(certVal)}&book_no=${encodeURIComponent(bookVal)}&exclude_id=${excludeId}`;
            const res = await fetch(url);
            const data = await res.json();

            if (data.duplicate) {
                // Style inputs red
                certInput.classList.remove('border-emerald-500', 'ring-1', 'ring-emerald-200');
                certInput.classList.add('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
                if (bookInput && bookVal) {
                    bookInput.classList.remove('border-emerald-500', 'ring-1', 'ring-emerald-200');
                    bookInput.classList.add('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
                }

                if (window._lastBirthDupToastMsg !== data.message) {
                    window._lastBirthDupToastMsg = data.message;
                    showToast(data.message, 'error', 6000);
                }

                if (feedback) {
                    const ex = data.existing || {};
                    feedback.innerHTML = `
                        <div class="p-3 bg-rose-50 dark:bg-rose-950/70 border-2 border-rose-300 dark:border-rose-800 rounded-xl text-xs text-rose-800 dark:text-rose-200 flex items-start gap-2.5 shadow-sm mt-2 animate-pulse">
                            <span class="text-xl leading-none flex-shrink-0">🚫</span>
                            <div class="space-y-1 min-w-0 flex-1">
                                <strong class="font-bold text-rose-900 dark:text-rose-100 block text-xs font-kh-bold">
                                    ⚠️ ស្ទួនទិន្នន័យ៖ លេខសំបុត្រកំណើត ឬសៀវភៅនេះ បានបញ្ចូលរួចហើយ!
                                </strong>
                                <div class="text-[11px] text-rose-700 dark:text-rose-300 leading-relaxed">
                                    <span>${data.message}</span>
                                </div>
                                ${ex.name_kh ? `
                                <div class="pt-1.5 mt-1.5 border-t border-rose-200 dark:border-rose-800/80 flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-medium text-rose-900 dark:text-rose-100">
                                    <span>👤 ឈ្មោះ៖ <strong>${ex.name_kh}</strong> (${ex.name_en || ''})</span>
                                    <span>🎂 ថ្ងៃខែឆ្នាំកំណើត៖ <strong>${ex.dob || ''}</strong></span>
                                    ${ex.village_name ? `<span>🏡 ភូមិ៖ <strong>${ex.village_name}</strong></span>` : ''}
                                </div>` : ''}
                            </div>
                        </div>
                    `;
                }

                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
                }
            } else {
                window._lastBirthDupToastMsg = null;
                // Style inputs green
                certInput.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
                certInput.classList.add('border-emerald-500', 'ring-1', 'ring-emerald-200');
                if (bookInput) {
                    bookInput.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
                    if (bookVal) {
                        bookInput.classList.add('border-emerald-500', 'ring-1', 'ring-emerald-200');
                    }
                }

                if (feedback) {
                    feedback.innerHTML = `
                        <div class="p-2 bg-emerald-50 border border-emerald-300 rounded-xl text-xs text-emerald-800 flex items-center gap-2 mt-2 shadow-xs">
                            <span class="text-base leading-none">✅</span>
                            <div>
                                <strong class="font-bold text-emerald-900">លេខសំបុត្រកំណើតអាចប្រើប្រាស់បាន</strong>
                                <span class="text-emerald-700 ml-1">មិនស្ទួនក្នុងប្រព័ន្ធឡើយ។</span>
                            </div>
                        </div>
                    `;
                }

                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                }
            }
        } catch (e) {
            console.error("Error checking duplicate birth cert", e);
        }
    }, 250);
}

// Automatically trigger toasts if URL parameters 'msg' or 'error' exist
document.addEventListener('DOMContentLoaded', function() {
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const errorMsg = urlParams.get('error');
        const successMsg = urlParams.get('msg');
        if (errorMsg) {
            showToast(errorMsg, 'error');
        } else if (successMsg) {
            showToast(successMsg, 'success');
        }
    } catch (e) {
        console.error(e);
    }
});

