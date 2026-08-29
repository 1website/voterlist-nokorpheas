import os
import io
import re
import uuid
import base64
import datetime
from PIL import Image, ImageOps, ImageEnhance

KHMER_DIGITS = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Normalize unicode and Khmer numbers
    return text.translate(KHMER_DIGITS).strip()

def parse_khmer_id_text(raw_text: str) -> dict:
    """
    Intelligently parses extracted OCR / Barcode text from a Cambodian National ID Card.
    Returns structured voter data dictionary.
    """
    if not raw_text:
        return {
            "national_id": "",
            "name_kh": "",
            "name_en": "",
            "gender": "ប្រុស",
            "dob": "1995-05-15",
            "address": "",
            "raw_text": ""
        }

    normalized = normalize_text(raw_text)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]

    # 1. National ID (9 digits or 7 digits)
    national_id = ""
    # Check for 9-digit pattern like 020491001 or 010 456 789 or ID: 020491001
    id_match_9 = re.search(r"\b(0\d{8}|\d{9})\b", normalized)
    if id_match_9:
        national_id = id_match_9.group(1).replace(" ", "")
    else:
        # Check spaced 9 digits
        id_spaced = re.search(r"\b(\d{3}\s+\d{3}\s+\d{3})\b", normalized)
        if id_spaced:
            national_id = re.sub(r"\s+", "", id_spaced.group(1))
        else:
            # Check 7-digit ID (Identity Certificate)
            id_match_7 = re.search(r"\b(\d{7})\b", normalized)
            if id_match_7:
                national_id = id_match_7.group(1)

    # 2. Date of Birth (DOB)
    dob = ""
    current_year = datetime.date.today().year
    
    # Patterns like DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY
    dob_match = re.search(r"\b([0-3]?\d)[./\-_]([0-1]?\d)[./\-_]((?:19|20)\d{2})\b", normalized)
    if dob_match:
        d, m, y = int(dob_match.group(1)), int(dob_match.group(2)), int(dob_match.group(3))
        if 1 <= d <= 31 and 1 <= m <= 12 and 1920 <= y <= current_year:
            dob = f"{y:04d}-{m:02d}-{d:02d}"
    
    if not dob:
        # YYYY-MM-DD
        dob_match_iso = re.search(r"\b((?:19|20)\d{2})[./\-_]([0-1]?\d)[./\-_]([0-3]?\d)\b", normalized)
        if dob_match_iso:
            y, m, d = int(dob_match_iso.group(1)), int(dob_match_iso.group(2)), int(dob_match_iso.group(3))
            if 1 <= d <= 31 and 1 <= m <= 12 and 1920 <= y <= current_year:
                dob = f"{y:04d}-{m:02d}-{d:02d}"

    if not dob:
        # Just Year if full date not found
        year_match = re.search(r"\b(19\d{2}|200\d|201\d)\b", normalized)
        if year_match:
            y = int(year_match.group(1))
            dob = f"{y:04d}-01-01"

    # 3. Gender (ភេទ)
    gender = "ប្រុស"
    if re.search(r"(ស្រី|FEMALE|\bF\b|FEM|ស្រី\s*/\s*F)", normalized, re.IGNORECASE):
        gender = "ស្រី"
    elif re.search(r"(ប្រុស|MALE|\bM\b|MAS|ប្រុស\s*/\s*M)", normalized, re.IGNORECASE):
        gender = "ប្រុស"

    # 4. Latin Name (ឈ្មោះជាអក្សរឡាតាំង ឧ. MEAS VANNA, KONG CHOY)
    name_en = ""
    stop_words = {"KINGDOM", "OF", "CAMBODIA", "NATIONAL", "IDENTITY", "CARD", "SEX", "DOB", "DATE", "BIRTH", "MALE", "FEMALE", "EXPIRE", "EXPIRY", "PLACE", "MINISTRY", "INTERIOR"}
    
    for line in lines:
        cleaned_line = re.sub(r"[^A-Z\s]", " ", line.upper()).strip()
        words = [w for w in cleaned_line.split() if len(w) >= 2 and w not in stop_words]
        if len(words) >= 2:
            candidate = " ".join(words)
            if not name_en or len(candidate) > len(name_en):
                name_en = candidate
                break

    # 5. Khmer Name (គោត្តនាម-នាម ឧ. មាស វណ្ណា)
    name_kh = ""
    khmer_stop_words = {"ព្រះរាជាណាចក្រកម្ពុជា", "ជាតិ", "សាសនា", "ព្រះមហាក្សត្រ", "អត្តសញ្ញាណប័ណ្ណ", "សញ្ជាតិខ្មែរ", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត", "ទីកន្លែងកំណើត", "អាសយដ្ឋាន", "សុពលភាព"}
    
    for line in lines:
        kh_text = re.sub(r"[^\u1780-\u17FF\s]", " ", line).strip()
        words = [w for w in kh_text.split() if len(w) >= 2 and w not in khmer_stop_words]
        if len(words) >= 2:
            candidate = " ".join(words)
            if not name_kh or len(candidate) > len(name_kh):
                name_kh = candidate
                break

    # 6. Address / Village
    address = ""
    addr_match = re.search(r"(?:ភូមិ|ឃុំ|ស្រុក|ខេត្ត)[^\n,]+", raw_text)
    if addr_match:
        address = addr_match.group(0).strip()

    return {
        "national_id": national_id,
        "name_kh": name_kh,
        "name_en": name_en,
        "gender": gender,
        "dob": dob or "1995-05-15",
        "address": address,
        "raw_text": raw_text
    }

def extract_id_card_face_portrait(image_bytes: bytes, subfolder: str = "voters") -> str:
    """
    Intelligently crops the portrait face region from a Cambodian National ID card image.
    In the standard Cambodian National ID Card:
    - Portrait is located on the left side (~4% to ~38% width, ~18% to ~85% height).
    Saves and returns an optimized Base64 Data URI.
    """
    if not image_bytes:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes))
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        # Convert to RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        w, h = image.size

        # Define portrait bounding box for standard ID card layout
        # (left: 4% to 38%, top: 18% to 85%)
        crop_box = (
            int(w * 0.04),
            int(h * 0.18),
            int(w * 0.38),
            int(h * 0.85)
        )

        # Safety check box bounds
        if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
            portrait = image.crop(crop_box)
        else:
            portrait = image

        # Enhance portrait contrast and sharpness slightly
        enhancer = ImageEnhance.Contrast(portrait)
        portrait = enhancer.enhance(1.1)

        # Resize to standard voter avatar size
        portrait.thumbnail((300, 360), Image.Resampling.LANCZOS)

        # Output to Base64 Data URI
        buf = io.BytesIO()
        portrait.save(buf, format="JPEG", quality=88, optimize=True)
        img_bytes = buf.getvalue()
        b64_str = base64.b64encode(img_bytes).decode("utf-8")

        # Save to static uploads directory
        static_uploads = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", subfolder)
        os.makedirs(static_uploads, exist_ok=True)
        filename = f"ocr_face_{uuid.uuid4().hex[:12]}.jpg"
        file_path = os.path.join(static_uploads, filename)
        with open(file_path, "wb") as f:
            f.write(img_bytes)

        return f"data:image/jpeg;base64,{b64_str}"

    except Exception as e:
        print(f"Face extraction notice: {e}")
        return None
