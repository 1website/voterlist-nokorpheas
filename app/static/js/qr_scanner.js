// QR Code and Barcode Scanner for Voter Management System
let html5QrCode = null;

async function startCameraScanner(elementId, resultCallback) {
    const scannerContainer = document.getElementById(elementId);
    if (!scannerContainer) return;

    if (typeof Html5Qrcode === 'undefined') {
        showToast("សូមរង់ចាំដំណើរការកម្មវិធីស្កេនកាមេរ៉ា...", "warning");
        return;
    }

    try {
        if (!html5QrCode) {
            html5QrCode = new Html5Qrcode(elementId);
        }

        const config = { fps: 10, qrbox: { width: 250, height: 250 } };
        await html5QrCode.start(
            { facingMode: "environment" },
            config,
            (decodedText, decodedResult) => {
                if (resultCallback) {
                    resultCallback(decodedText);
                }
            },
            (errorMessage) => {
                // Ignore per-frame decode errors
            }
        );
    } catch (err) {
        console.error("Camera access error:", err);
        showToast("មិនអាចបើកកាមេរ៉ាបានទេ សូមពិនិត្យការអនុញ្ញាត (Camera permission)", "error");
    }
}

async function stopCameraScanner() {
    if (html5QrCode) {
        try {
            await html5QrCode.stop();
            html5QrCode = null;
        } catch (e) {
            console.log("Stop scanner error", e);
        }
    }
}

// Quick Lookup and Instant Check-in
async function lookupVoterCode(code, autoCheckin = false) {
    if (!code || !code.trim()) return;

    try {
        const res = await fetch(`/api/voters/lookup-qr?code=${encodeURIComponent(code.trim())}`);
        const data = await res.json();

        if (res.ok && data.found) {
            playAudioBeep(true);
            displayVoterResult(data.voter, autoCheckin);
        } else {
            playAudioBeep(false);
            showToast(data.message || "រកមិនឃើញទិន្នន័យអ្នកបោះឆ្នោតឡើយ", "error");
        }
    } catch (e) {
        showToast("មានបញ្ហាក្នុងការស្វែងរក", "error");
    }
}

function displayVoterResult(voter, autoCheckin = false) {
    const resultCard = document.getElementById('qrSearchResult');
    if (!resultCard) return;

    resultCard.classList.remove('hidden');
    resultCard.style.display = 'block';

    const statusBadge = voter.has_voted
        ? `<span class="badge badge-success text-xs font-bold">✓ បានបោះឆ្នោតរួច (${voter.voted_at || ''})</span>`
        : `<span class="badge badge-warning text-xs font-bold">⏳ មិនទាន់បោះឆ្នោត (មានសិទ្ធិបោះឆ្នោត)</span>`;

    const docTypeLabel = (voter.national_id && voter.national_id.length === 7)
        ? `<span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-900 font-bold">📄 ឯ.អ (៧ ខ្ទង់)</span>`
        : `<span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-900 font-bold">🪪 អត្តសញ្ញាណប័ណ្ណ (៩ ខ្ទង់)</span>`;

    resultCard.innerHTML = `
        <div class="p-6 bg-white rounded-3xl border-2 border-blue-600 shadow-2xl animate-fade-in relative overflow-hidden">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b pb-4 mb-4 gap-3">
                <div class="flex items-center gap-3.5">
                    <img src="${voter.photo_url || '/static/images/avatars/male_1.jpg'}" alt="${voter.name_kh}" class="w-16 h-16 sm:w-18 sm:h-18 rounded-2xl object-cover border-2 border-blue-500 shadow-md bg-white flex-shrink-0">
                    <div class="min-w-0">
                        <div class="flex items-center gap-1.5 flex-wrap">
                            <span class="text-xs uppercase font-mono font-bold text-blue-700 bg-blue-100 px-2.5 py-0.5 rounded-full border border-blue-200">
                                ${voter.voter_code}
                            </span>
                            ${docTypeLabel}
                        </div>
                        <h3 class="text-xl sm:text-2xl font-bold text-slate-800 mt-1 font-kh-heading">${voter.name_kh}</h3>
                        <p class="text-xs uppercase font-semibold text-slate-500 tracking-wider font-mono">${voter.name_en}</p>
                    </div>
                </div>
                <div class="text-left sm:text-right">
                    <span class="text-[11px] text-slate-400 font-bold uppercase">លេខរៀងក្នុងបញ្ជី</span>
                    <div class="text-2xl sm:text-3xl font-black text-amber-600 font-mono">#${voter.list_no}</div>
                </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs mb-4">
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                    <span class="text-slate-500 font-medium block">លេខអត្តសញ្ញាណប័ណ្ណ / ឯកសារបញ្ជាក់៖</span>
                    <strong class="font-mono text-sm text-slate-900 font-bold">${voter.national_id}</strong>
                </div>
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                    <span class="text-slate-500 font-medium block">ភេទ / ថ្ងៃខែឆ្នាំកំណើត៖</span>
                    <strong class="text-sm text-slate-900 font-bold">${voter.gender} (${voter.dob})</strong>
                </div>
                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                    <span class="text-slate-500 font-medium block">ភូមិ (ទីលំនៅ)៖</span>
                    <strong class="text-sm text-slate-900 font-bold">${voter.village_name}</strong>
                </div>
                <div class="p-2.5 rounded-xl bg-blue-50/70 border border-blue-200">
                    <span class="text-slate-500 font-medium block">ការិយាល័យបោះឆ្នោត៖</span>
                    <strong class="text-sm text-blue-900 font-bold">${voter.station_code} - ${voter.station_name}</strong>
                    <div class="text-[11px] text-slate-500 mt-0.5">📍 ${voter.station_location}</div>
                </div>
            </div>

            <!-- Verification Link Banner -->
            <div class="p-3 bg-slate-900 text-white rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-2 mb-4 text-xs shadow-inner">
                <div class="flex items-center gap-2 min-w-0 flex-1">
                    <span class="text-base">🔗</span>
                    <div class="min-w-0 flex-1 truncate">
                        <span class="text-amber-300 font-bold text-[10px] uppercase block">Link ផ្ទៀងផ្ទាត់ផ្លូវការ៖</span>
                        <span class="font-mono text-slate-200 text-[11px] truncate block">${window.location.origin}/verify/${voter.voter_code}</span>
                    </div>
                </div>
                <a href="/verify/${voter.voter_code}" target="_blank" class="btn btn-sm btn-accent text-xs font-bold whitespace-nowrap flex-shrink-0">
                    ↗ បើក Link ផ្ទៀងផ្ទាត់
                </a>
            </div>

            <div class="flex flex-col sm:flex-row items-center justify-between pt-3 border-t border-slate-100 gap-3">
                <div id="voter-status-${voter.id}">${statusBadge}</div>
                <div class="flex items-center gap-2 w-full sm:w-auto justify-end">
                    <button onclick="toggleCheckin(${voter.id}, this)" class="btn ${voter.has_voted ? 'btn-outline text-red-600' : 'btn-success px-5 py-2 font-bold text-sm'}">
                        ${voter.has_voted ? '✕ លុប Check-in' : '✓ បញ្ជាក់ការបោះឆ្នោត (Check-in)'}
                    </button>
                    <a href="/voters/${voter.id}/card" target="_blank" class="btn btn-outline btn-sm">
                        🖨️ បោះពុម្ពប័ណ្ណ
                    </a>
                </div>
            </div>
        </div>
    `;

    // Auto-checkin if requested and not yet voted
    if (autoCheckin && !voter.has_voted) {
        toggleCheckin(voter.id);
    }
}
