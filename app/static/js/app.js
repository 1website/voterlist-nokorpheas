// Toast notification system
function showToast(message, type = 'success') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✓' : '⚠️';
    toast.innerHTML = `<span>${icon}</span> <div>${message}</div>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
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
                    btnElement.className = 'btn btn-sm btn-outline text-danger';
                    btnElement.innerHTML = '✕ លុប Check-in';
                } else {
                    btnElement.className = 'btn btn-sm btn-success';
                    btnElement.innerHTML = '✓ Check-in';
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
                <div class="text-[11px] text-slate-500 font-medium mt-1 flex items-center gap-1.5">
                    <span>⏳</span>
                    <span>កំពុងបញ្ចូល៖ <strong class="text-blue-700 font-mono">${val.length} ខ្ទង់</strong> (ឯកសារបញ្ជាក់អត្តសញ្ញាណ ៧ ខ្ទង់ ឬ អត្តសញ្ញាណប័ណ្ណ ៩ ខ្ទង់)</span>
                </div>
            `;
        }
        inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30', 'border-emerald-500', 'ring-1', 'ring-emerald-200');
        return;
    }

    if (val.length === 8) {
        if (feedback) {
            feedback.innerHTML = `
                <div class="text-[11px] text-amber-700 font-medium mt-1 flex items-center gap-1.5">
                    <span>⚠️</span>
                    <span>បានបញ្ចូល <strong class="font-mono">៨ ខ្ទង់</strong> (ប្រសិនបើជាអត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ សូមបញ្ចូលឱ្យគ្រប់ <strong>៩ ខ្ទង់</strong>)</span>
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
                    feedback.innerHTML = `
                        <div class="p-3 bg-red-50 border-2 border-red-300 rounded-xl text-xs text-red-700 flex items-start gap-2.5 shadow-sm mt-1.5">
                            <span class="text-lg leading-none flex-shrink-0">🚫</span>
                            <div>
                                <strong class="font-bold text-red-900 block text-xs">⚠️ ស្ទួនទិន្នន័យ៖ លេខ${docTypeLabel}នេះ បានចុះឈ្មោះរួចហើយ!</strong>
                                <span class="mt-0.5 block leading-relaxed">${data.message}</span>
                            </div>
                        </div>
                    `;
                } else {
                    inputElement.classList.remove('border-red-500', 'ring-2', 'ring-red-200', 'bg-red-50/30');
                    inputElement.classList.add('border-emerald-500', 'ring-1', 'ring-emerald-200');
                    feedback.innerHTML = `
                        <div class="p-2.5 bg-emerald-50 border border-emerald-300 rounded-xl text-xs text-emerald-800 flex items-center gap-2 mt-1.5 shadow-sm">
                            <span class="text-base leading-none">✅</span>
                            <div>
                                <strong class="font-bold text-emerald-900">${docTypeIcon} លេខ${docTypeLabel} ត្រឹមត្រូវ</strong>
                                <span class="text-emerald-700 ml-1">មិនស្ទួនក្នុងប្រព័ន្ធឡើយ អាចចុះឈ្មោះបាន។</span>
                            </div>
                        </div>
                    `;
                }
            }
        } catch (e) {
            console.error(e);
        }
    }, 250);
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

    if (isNaN(birthDate.getTime())) return null;

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
                <div class="p-2.5 bg-red-50 border-2 border-red-300 rounded-xl text-xs text-red-700 flex items-start gap-2 shadow-sm mt-1.5 animate-pulse">
                    <span class="text-base flex-shrink-0 leading-none">🚫</span>
                    <div>
                        <strong class="font-bold text-red-900 block text-xs">មិនទាន់គ្រប់អាយុបោះឆ្នោត (អាយុត្រឹម ${age} ឆ្នាំ)!</strong>
                        <span class="mt-0.5 block leading-relaxed">យោងតាមច្បាប់បោះឆ្នោតជាតិ ពលរដ្ឋត្រូវមានអាយុយ៉ាងតិច <strong>១៨ ឆ្នាំឡើងទៅ</strong> ទើបមានសិទ្ធិចុះឈ្មោះបាន។</span>
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
                <div class="text-[11px] text-emerald-700 font-semibold mt-1 flex items-center gap-1.5">
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
