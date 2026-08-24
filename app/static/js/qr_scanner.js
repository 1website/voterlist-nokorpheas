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
        ? `<span class="badge badge-success">✓ បានបោះឆ្នោតរួច (${voter.voted_at || ''})</span>`
        : `<span class="badge badge-warning">⏳ មិនទាន់បោះឆ្នោត</span>`;

    resultCard.innerHTML = `
        <div class="p-6 bg-white rounded-2xl border-2 border-blue-600 shadow-xl animate-fade-in">
            <div class="flex items-center justify-between border-b pb-4 mb-4">
                <div class="flex items-center gap-4">
                    <img src="${voter.photo_url || '/static/images/avatars/male_1.jpg'}" alt="${voter.name_kh}" class="w-16 h-16 rounded-2xl object-cover border-2 border-blue-500 shadow-md bg-white">
                    <div>
                        <span class="text-xs uppercase font-bold text-blue-700 bg-blue-100 px-2.5 py-1 rounded-full">
                            លេខកូដ: ${voter.voter_code}
                        </span>
                        <h3 class="text-2xl font-bold text-slate-800 mt-1 font-kh-bold">${voter.name_kh}</h3>
                        <p class="text-sm font-semibold text-slate-500 tracking-wider">${voter.name_en}</p>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-3xl font-black text-blue-900">#${voter.list_no}</div>
                    <div class="text-xs text-slate-500 font-semibold">លេខរៀងក្នុងបញ្ជី</div>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-4 text-sm mb-5">
                <div>
                    <span class="text-slate-500">អត្តសញ្ញាណប័ណ្ណ៖</span>
                    <p class="font-bold text-slate-800 text-base">${voter.national_id}</p>
                </div>
                <div>
                    <span class="text-slate-500">ភេទ / ថ្ងៃខែឆ្នាំកំណើត៖</span>
                    <p class="font-bold text-slate-800">${voter.gender} (${voter.dob})</p>
                </div>
                <div>
                    <span class="text-slate-500">ភូមិ៖</span>
                    <p class="font-bold text-slate-800">${voter.village_name}</p>
                </div>
                <div>
                    <span class="text-slate-500">ការិយាល័យបោះឆ្នោត៖</span>
                    <p class="font-bold text-blue-700">${voter.station_code} - ${voter.station_name}</p>
                    <p class="text-xs text-slate-500">${voter.station_location}</p>
                </div>
            </div>

            <div class="flex items-center justify-between pt-4 border-t">
                <div id="voter-status-${voter.id}">${statusBadge}</div>
                <div class="flex gap-2">
                    <button onclick="toggleCheckin(${voter.id}, this)" class="btn ${voter.has_voted ? 'btn-outline text-red-600' : 'btn-success px-6 py-2 text-base'}">
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
