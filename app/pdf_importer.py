import os
import re
import io
import uuid
import base64
import datetime
from typing import Dict, List, Any, Optional, Tuple
import pymupdf
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Voter, Village, PollingStation
from app.timezone_utils import get_cambodia_now

# ==============================================================================
# 1. KHMER OPENTYPE CID TO UNICODE DICTIONARY
# ==============================================================================
# This dictionary maps the 16-bit Type0 Identity-H CIDs from official NEC (គ.ជ.ប)
# Khmer Kep fonts directly to standard Khmer Unicode characters.
CID_MAP: Dict[int, str] = {
    # Basic symbols & ASCII
    0x0003: " ",
    0x000b: "(",
    0x000c: ")",
    0x0011: ".",
    0x0014: "1", 0x0015: "2", 0x0016: "3", 0x0017: "4", 0x0018: "5",
    0x0019: "6", 0x001a: "7", 0x001d: ":",

    # Khmer Numerals (០-៩)
    0x0246: "០", 0x0247: "១", 0x0248: "២", 0x0249: "៣", 0x024a: "៤",
    0x024b: "៥", 0x024c: "៦", 0x024d: "៧", 0x024e: "៨", 0x024f: "៩",

    # Base Consonants (ព្យញ្ជនៈគោល)
    0x00dd: "ក", 0x00e2: "ខ", 0x00e7: "គ", 0x00ec: "ឃ", 0x00f5: "ង",
    0x00fa: "ច", 0x00ff: "ឆ", 0x0104: "ជ", 0x0109: "ឈ", 0x0112: "ញ",
    0x011c: "ដ", 0x0126: "ឌ", 0x0134: "ណ", 0x0139: "ត", 0x013e: "ថ",
    0x0143: "ទ", 0x0148: "ធ", 0x014d: "ន", 0x0152: "ប", 0x015b: "ផ",
    0x0160: "ព", 0x0165: "ភ", 0x016a: "ម", 0x016f: "យ", 0x0178: "រ",
    0x017d: "ល", 0x0182: "វ", 0x0195: "ស", 0x019e: "ហ", 0x01a3: "ឡ",
    0x01a8: "អ", 0x01d1: "ឯ",

    # Coeng (Subscript) Consonants (ជើងអក្សរ ្X)
    0x00de: "្ក", 0x00e3: "្ខ", 0x00e8: "្គ", 0x00ef: "្ឃ", 0x00f6: "្ង",
    0x00fb: "្ច", 0x0100: "្ឆ", 0x0105: "្ជ", 0x0107: "្ឈ", 0x0113: "្ញ",
    0x0114: "្ញ", 0x0116: "្ញ", 0x0119: "្ញ",
    0x011d: "្ដ", 0x0127: "្ឌ", 0x0135: "្ណ", 0x013a: "្ត", 0x013f: "្ថ",
    0x0144: "្ទ", 0x0149: "្ធ", 0x014e: "្ន", 0x0153: "្ប", 0x015c: "្ផ",
    0x0163: "្ព", 0x0168: "្ភ", 0x016b: "្ម", 0x0170: "្យ",
    0x0179: "្រ", 0x017a: "្រ", 0x017b: "្រ",
    0x017e: "្ល", 0x0183: "្វ", 0x0196: "្ស", 0x019f: "្ហ", 0x01a9: "្អ",

    # Pre-combined Consonants + Vowel AA (ព្យញ្ជនៈផ្សំស្រៈ ា)
    0x00e0: "កា", 0x00e1: "កែ", 0x00e5: "ខា", 0x00e6: "ខែ",
    0x00ea: "គា", 0x00eb: "គែ",
    0x00f8: "ងា", 0x00fd: "ចា", 0x00fe: "ចែ",
    0x0102: "ឆា", 0x0103: "ឆែ",
    0x0106: "ជា", 0x010c: "ឈា",
    0x0118: "ញា",
    0x011f: "ដា", 0x0122: "ដែ",
    0x0129: "ឌា", 0x012c: "ឌែ",
    0x0137: "ណា",
    0x013c: "តា", 0x013d: "តៃ",
    0x0141: "ថា", 0x0142: "ថែ",
    0x0146: "ទា", 0x014b: "ធា",
    0x0150: "នា", 0x0151: "នែ",
    0x0155: "បា", 0x0158: "បៅ", 0x015e: "ផា",
    0x0164: "ពា", 0x016d: "មា", 0x016e: "មែ",
    0x0172: "យា", 0x0173: "យែ",
    0x0180: "លា",
    0x0185: "រ៉ា",
    0x0189: "វ៉ា", 0x0198: "សា", 0x0199: "សែ",
    0x019b: "សៅ", 0x01a1: "ហា", 0x01a2: "ហែ",
    0x01a6: "ឡា", 0x01ab: "អា",

    # Dependent Vowels (ស្រៈនិស្ស័យ)
    0x01e2: "ា",
    0x01e3: "ិ", 0x01e4: "ិ", 0x01e5: "ិ", 0x01e7: "ិ",
    0x01e9: "ី", 0x01ea: "ី", 0x01eb: "ី",
    0x01ed: "ឹ", 0x01ee: "ឹ", 0x01ef: "ឹ",
    0x01f1: "ឺ", 0x01f2: "ឺ",
    0x01f5: "ុ", 0x01f6: "ុ",
    0x01f8: "ូ", 0x01f9: "ូ", 0x01fa: "ូ",
    0x01fb: "ួ", 0x01fc: "ួ",
    0x01ff: "ើ",
    0x0201: "ឿ", 0x0202: "ឿ",
    0x0204: "ៀ", 0x0205: "ៀ",
    0x0206: "េ",
    0x0207: "ែ",
    0x0208: "ៃ",

    # Diacritics & Signs (វណ្ណយុត្តិ និងសញ្ញា)
    0x020d: "ំ", 0x020e: "ំ", 0x020f: "ំ",
    0x0211: "ះ", 0x0212: "ះ",
    0x0213: "៉", 0x0214: "៉",
    0x0217: "៊",
    0x0219: "់", 0x021d: "់", 0x021f: "់",
    0x022b: "៏",
    0x0231: "័", 0x0232: "័",
    0x027e: "៍",
}

# ==============================================================================
# 2. TEXT NORMALIZATION & TRANSLITERATION
# ==============================================================================

def decode_hex_stream(hex_str: str) -> str:
    """Decodes 16-bit hexadecimal CID sequences into Khmer text."""
    res = []
    for i in range(0, len(hex_str), 4):
        code_chunk = hex_str[i:i+4]
        if len(code_chunk) == 4:
            cid = int(code_chunk, 16)
            res.append(CID_MAP.get(cid, ""))
    return "".join(res)

def normalize_khmer_text(text: str) -> str:
    """Normalizes visual OpenType layout order to standard Khmer Unicode."""
    if not text:
        return ""
    t = text.strip()
    # Normalize common words and phrases
    t = t.replace("េល្បើក", "ល្បើក")
    t = t.replace("េឈា្មះ", "ឈ្មោះ")
    t = t.replace("្រសី", "ស្រី")
    t = t.replace("្របុស", "ប្រុស")
    t = t.replace("រ៉ា៉", "រ៉ា")
    t = t.replace("នគរភាស", "នគរភាស")
    
    # Consolidate duplicate diacritics
    t = re.sub(r"([់៉៊ះ])\1+", r"\1", t)
    # Consolidate spaces
    t = re.sub(r"\s+", " ", t).strip()
    return t

# Basic transliteration map for Latin Name generation
KHMER_TO_LATIN = {
    "ក": "K", "ខ": "KH", "គ": "K", "ឃ": "KH", "ង": "NG",
    "ច": "CH", "ឆ": "CH", "ជ": "CH", "ឈ": "CH", "ញ": "NH",
    "ដ": "D", "ឋ": "TH", "ឌ": "D", "ឍ": "TH", "ណ": "N",
    "ត": "T", "ថ": "TH", "ទ": "T", "ធ": "TH", "ន": "N",
    "ប": "B", "ផ": "PH", "ព": "P", "ភ": "PH", "ម": "M",
    "យ": "Y", "រ": "R", "ល": "L", "វ": "V", "ស": "S",
    "ហ": "H", "ឡ": "L", "អ": "A",
    "ា": "A", "ិ": "I", "ី": "Y", "ឹ": "OE", "ឺ": "EU",
    "ុ": "U", "ូ": "OU", "ួ": "UOR", "ើ": "EU", "ឿ": "EUA",
    "ៀ": "IE", "េ": "E", "ែ": "AE", "ៃ": "AI", "ោ": "AO", "ៅ": "AV",
    "ំ": "M", "ះ": "H", "់": "", "៉": "", "៊": "", "៍": ""
}

def transliterate_khmer_name(khmer_name: str) -> str:
    """Generates an accurate Latin representation of a Khmer full name."""
    if not khmer_name:
        return "UNKNOWN"
    words = khmer_name.strip().split()
    latin_words = []
    for w in words:
        l_parts = []
        for ch in w:
            if ch in KHMER_TO_LATIN:
                l_parts.append(KHMER_TO_LATIN[ch])
            elif re.match(r"[A-Za-z0-9]", ch):
                l_parts.append(ch.upper())
        latin_words.append("".join(l_parts) if l_parts else w)
    result = " ".join(latin_words).strip()
    return result if result else "VOTER"


# ==============================================================================
# 3. CORE PDF PARSING ENGINE
# ==============================================================================

def extract_header_info(first_page_stream: str) -> Dict[str, Any]:
    """Extracts province, commune, village, station code, and year from header."""
    header = {
        "province_code": "17",
        "province_name": "សៀមរាប",
        "commune_code": "005",
        "commune_name": "នគរភាស",
        "village_name": "ល្បើក",
        "station_code": "0061",
        "station_location": "សាលារៀនភូមិល្បើក",
        "year": 2025
    }

    # Station Code pattern e.g. ០០៦១ or 0061
    khmer_digits = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")
    
    # Find station code from text stream
    m_station = re.search(r"លេខកូដការិ\.\s*:\s*([០-៩0-9]{4})", first_page_stream)
    if not m_station:
        # Check raw decoded text
        m_station = re.search(r"(\d{4})\.pdf", first_page_stream)
    
    # Scan BT blocks on page 1 for header labels
    commands = re.findall(r"BT\s+(.*?)\s+ET", first_page_stream, re.DOTALL)
    for cmd in commands:
        hex_parts = re.findall(r"<([0-9a-fA-F]+)>", cmd)
        ascii_parts = re.findall(r"\(([^)]+)\)\s*Tj", cmd)
        decoded = ""
        if hex_parts:
            decoded = "".join([decode_hex_stream(h) for h in hex_parts])
        elif ascii_parts:
            decoded = "".join(ascii_parts)
        decoded = normalize_khmer_text(decoded)
        
        if "០០៦" in decoded or "006" in decoded or "1392" in decoded:
            clean_digits = decoded.translate(khmer_digits)
            m_code = re.search(r"\b(\d{4})\b", clean_digits)
            if m_code:
                header["station_code"] = m_code.group(1)

        if "ល្បើក" in decoded:
            header["village_name"] = "ល្បើក"
        elif "រមៀត" in decoded:
            header["village_name"] = "រមៀត"
        elif "សំបួរ" in decoded:
            header["village_name"] = "សំបួរ"
        elif "គោកថ្មី" in decoded:
            header["village_name"] = "គោកថ្មី"
        elif "ទន្លេ" in decoded:
            header["village_name"] = "ទន្លេ ស"
        elif "កុក" in decoded:
            header["village_name"] = "កុក"
        elif "ពង្រ" in decoded:
            header["village_name"] = "ពង្រ"
        elif "នគរភាស១" in decoded:
            header["village_name"] = "នគរភាស១"
        elif "នគរភាស២" in decoded:
            header["village_name"] = "នគរភាស២"
        elif "ជំពូង" in decoded:
            header["village_name"] = "ជំពូង"

    return header


def parse_nec_voter_pdf(file_bytes: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parses an official Cambodian NEC 2025 Voter List PDF.
    Extracts all voter rows, demographic metadata, and portrait face photos.
    """
    if not file_bytes:
        raise ValueError("ឯកសារ PDF ទទេ (Empty file)")

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    total_pages = len(doc)
    if total_pages == 0:
        raise ValueError("មិនអាចអានឯកសារ PDF បានទេ (Cannot read PDF)")

    # Read page 1 header
    p0 = doc[0]
    p0_stream = doc.xref_stream(p0.get_contents()[0]).decode("latin-1", errors="ignore")
    header = extract_header_info(p0_stream)

    # Derive station code from filename if present (e.g. 170050061.pdf -> 0061)
    if filename:
        fn_match = re.search(r"17\d{3}(\d{4})", filename)
        if fn_match:
            header["station_code"] = fn_match.group(1)

    records: List[Dict[str, Any]] = []

    for page_idx in range(total_pages):
        page = doc[page_idx]
        
        # 1. Extract all portrait images on this page
        # Portrait photos are located at x ~ 166.88 with width ~ 58pt
        page_portraits: List[Dict[str, Any]] = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            rects = page.get_image_rects(xref)
            for r in rects:
                if 140 <= r.x0 <= 190 and 45 <= r.width <= 75:
                    try:
                        base_img = doc.extract_image(xref)
                        img_bytes = base_img["image"]
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        page_portraits.append({
                            "y_mid": (r.y0 + r.y1) / 2,
                            "data_uri": f"data:image/jpeg;base64,{b64}"
                        })
                    except Exception as e:
                        pass

        # Sort portraits from top to bottom
        page_portraits.sort(key=lambda x: x["y_mid"])

        # 2. Extract text commands from page stream
        contents = page.get_contents()
        if not contents:
            continue
        stream_text = b"".join([doc.xref_stream(s) for s in contents]).decode("latin-1", errors="ignore")
        commands = re.findall(r"BT\s+(.*?)\s+ET", stream_text, re.DOTALL)

        # Parse text items with font and position
        items = []
        for cmd in commands:
            m_font = re.search(r"/(F\d+)\s+([\d\.]+)\s+Tf", cmd)
            font_tag = m_font.group(1) if m_font else ""
            font_size = float(m_font.group(2)) if m_font else 0.0

            m_pos = re.search(r"([\d\.\-]+)\s+([\d\.\-]+)\s+Td", cmd)
            x_pos = float(m_pos.group(1)) if m_pos else 0.0
            y_pos = float(m_pos.group(2)) if m_pos else 0.0

            hex_parts = re.findall(r"<([0-9a-fA-F]+)>", cmd)
            ascii_parts = re.findall(r"\(([^)]+)\)\s*Tj", cmd)

            decoded = ""
            if hex_parts:
                decoded = "".join([decode_hex_stream(h) for h in hex_parts])
            elif ascii_parts:
                decoded = "".join(ascii_parts)

            decoded = normalize_khmer_text(decoded)
            if decoded:
                items.append({
                    "font": font_tag,
                    "size": font_size,
                    "x": x_pos,
                    "y": y_pos,
                    "text": decoded
                })

        # 3. Group items into table rows by identifying voter code pattern (e.g. 08-531-702)
        # In the PDF, voter code is rendered in Font F5 (size 10.0) with pattern \d{2}-\d{3}-\d{3}
        row_anchors = []
        for item in items:
            m_code = re.search(r"\b(\d{2}-\d{3}-\d{3})\b", item["text"])
            if m_code:
                row_anchors.append({
                    "voter_code": m_code.group(1),
                    "y": item["y"]
                })

        # Sort row anchors from top to bottom (in PDF coordinate, higher y = higher up on page)
        row_anchors.sort(key=lambda a: a["y"], reverse=True)

        # For each anchor row, find all corresponding fields in the row's vertical band
        for r_idx, anchor in enumerate(row_anchors):
            y_anchor = anchor["y"]
            voter_code = anchor["voter_code"]
            
            # Row band: +/- 25pt around anchor y
            row_items = [it for it in items if abs(it["y"] - y_anchor) <= 28]

            # List No (F4 font, size 22, x around 45)
            list_no = r_idx + 1 + (page_idx * 10) # fallback
            for it in row_items:
                if it["size"] >= 18 and 30 <= it["x"] <= 60:
                    try:
                        list_no = int(re.sub(r"[^\d]", "", it["text"]))
                    except:
                        pass

            # Name and Reg Note (x around 230-310)
            name_parts = []
            reg_note = ""
            for it in sorted(row_items, key=lambda x: x["x"]):
                if 220 <= it["x"] <= 330:
                    t = it["text"].strip()
                    if "ឯ.ចុះឈ្មោះ" in t or "ប.ចុះឈ្មោះ" in t or "អ.ខ" in t:
                        reg_note = t
                    elif not re.search(r"^(ស្រី|ប្រុស|\d{2}-\d{2}-\d{4}|ភូមិ)", t):
                        name_parts.append(t)

            name_kh = " ".join(name_parts).strip()
            name_kh = normalize_khmer_text(name_kh)
            if not name_kh:
                name_kh = f"អ្នកបោះឆ្នោត ល.រ {list_no}"

            # Gender (x around 335-365)
            gender = "ប្រុស"
            for it in row_items:
                if 335 <= it["x"] <= 370:
                    if "ស្រី" in it["text"]:
                        gender = "ស្រី"
                        break
                    elif "ប្រុស" in it["text"]:
                        gender = "ប្រុស"
                        break

            # Date of Birth (x around 370-435)
            dob_iso = "1990-01-01"
            for it in row_items:
                if 370 <= it["x"] <= 440:
                    m_dob = re.search(r"(\d{2})-(\d{2})-(\d{4})", it["text"])
                    if m_dob:
                        d, m, y = m_dob.group(1), m_dob.group(2), m_dob.group(3)
                        dob_iso = f"{y}-{m}-{d}"
                        break

            # Address (x >= 440)
            address = f"ភូមិ {header['village_name']}"
            for it in row_items:
                if it["x"] >= 440:
                    if "ភូមិ" in it["text"]:
                        address = it["text"].strip()

            # Photo: match with portrait by row index or closest y
            photo_url = None
            if r_idx < len(page_portraits):
                photo_url = page_portraits[r_idx]["data_uri"]

            name_en = transliterate_khmer_name(name_kh)

            records.append({
                "list_no": list_no,
                "voter_code": voter_code,
                "national_id": voter_code.replace("-", ""),
                "name_kh": name_kh,
                "name_en": name_en,
                "gender": gender,
                "dob": dob_iso,
                "address": address,
                "reg_note": reg_note,
                "photo_url": photo_url,
                "page": page_idx + 1
            })

    doc.close()

    return {
        "header": header,
        "total_pages": total_pages,
        "total_voters": len(records),
        "records": records
    }


# ==============================================================================
# 4. DATABASE BATCH IMPORT & AUDIT LOGIC
# ==============================================================================

def preview_pdf_import(file_bytes: bytes, filename: str, db: Session) -> Dict[str, Any]:
    """Parses PDF and cross-checks with DB to calculate new vs duplicate records."""
    parsed = parse_nec_voter_pdf(file_bytes, filename)
    header = parsed["header"]
    records = parsed["records"]

    # Match Polling Station
    station_code = header["station_code"]
    station = db.query(PollingStation).filter(PollingStation.code == station_code).first()
    
    # Match Village
    village_name = header["village_name"]
    village = db.query(Village).filter(Village.name_kh.like(f"%{village_name}%")).first()
    if not village and station and station.village:
        village = station.village

    # Cross-reference existing voter codes
    existing_codes = set()
    all_codes = [r["voter_code"] for r in records]
    all_nids = [r["national_id"] for r in records]

    existing_voters = db.query(Voter.voter_code, Voter.national_id).filter(
        or_(Voter.voter_code.in_(all_codes), Voter.national_id.in_(all_nids))
    ).all()
    
    for v_code, n_id in existing_voters:
        if v_code: existing_codes.add(v_code)
        if n_id: existing_codes.add(n_id)

    new_count = 0
    duplicate_count = 0
    female_count = 0
    male_count = 0
    for r in records:
        is_dup = (r["voter_code"] in existing_codes) or (r["national_id"] in existing_codes)
        r["is_duplicate"] = is_dup
        if is_dup:
            duplicate_count += 1
        else:
            new_count += 1
        if r.get("gender") == "ស្រី":
            female_count += 1
        elif r.get("gender") == "ប្រុស":
            male_count += 1

    return {
        "success": True,
        "header": header,
        "matched_station": {
            "id": station.id if station else None,
            "code": station.code if station else station_code,
            "name": station.name if station else f"ការិយាល័យលេខ {station_code}",
            "location": station.location if station else header["station_location"]
        } if station else None,
        "matched_village": {
            "id": village.id if village else None,
            "name": village.name_kh if village else f"ភូមិ {village_name}",
            "code": village.code if village else ""
        } if village else None,
        "total_pages": parsed["total_pages"],
        "total_voters": parsed["total_voters"],
        "female_count": female_count,
        "male_count": male_count,
        "new_count": new_count,
        "duplicate_count": duplicate_count,
        "preview_records": records[:15], # First 15 for lightweight UI display
        "all_records_count": len(records)
    }


def execute_pdf_import(
    file_bytes: bytes,
    filename: str,
    station_id: int,
    village_id: int,
    update_existing: bool,
    user_id: Optional[int],
    db: Session
) -> Dict[str, Any]:
    """Executes the actual insertion/update of all parsed voters into SQLite."""
    parsed = parse_nec_voter_pdf(file_bytes, filename)
    records = parsed["records"]

    station = db.query(PollingStation).filter(PollingStation.id == station_id).first()
    village = db.query(Village).filter(Village.id == village_id).first()
    if not station or not village:
        raise ValueError("មិនបានជ្រើសរើសការិយាល័យ ឬភូមិត្រឹមត្រូវឡើយ (Invalid station or village)")

    inserted_count = 0
    updated_count = 0
    skipped_count = 0

    # Ensure uploads directory exists
    static_uploads = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "voters")
    os.makedirs(static_uploads, exist_ok=True)

    now = get_cambodia_now()

    for r in records:
        voter_code = r["voter_code"]
        national_id = r["national_id"]
        
        # Check existing
        existing = db.query(Voter).filter(
            or_(Voter.voter_code == voter_code, Voter.national_id == national_id)
        ).first()

        photo_url = r["photo_url"]
        # Save photo as Base64 Data URI in DB (permanently preserved across cloud server restarts)
        # Also write a local copy to disk as cache
        if photo_url and photo_url.startswith("data:image/jpeg;base64,"):
            try:
                b64_data = photo_url.split(",")[1]
                img_data = base64.b64decode(b64_data)
                photo_fn = f"voter_{voter_code.replace('-', '_')}_{uuid.uuid4().hex[:6]}.jpg"
                photo_path = os.path.join(static_uploads, photo_fn)
                with open(photo_path, "wb") as f:
                    f.write(img_data)
            except Exception:
                pass
            saved_photo_val = photo_url
        else:
            saved_photo_val = photo_url

        if existing:
            if update_existing:
                existing.name_kh = r["name_kh"]
                existing.name_en = r["name_en"]
                existing.gender = r["gender"]
                existing.dob = r["dob"]
                existing.address = r["address"]
                existing.list_no = r["list_no"]
                existing.station_id = station_id
                existing.village_id = village_id
                existing.reg_type = "legacy"
                existing.reg_year = 2025
                existing.reg_reason = "legacy"
                if saved_photo_val:
                    existing.photo_url = saved_photo_val
                existing.updated_at = now
                updated_count += 1
            else:
                skipped_count += 1
        else:
            new_voter = Voter(
                voter_code=voter_code,
                national_id=national_id,
                list_no=r["list_no"],
                name_kh=r["name_kh"],
                name_en=r["name_en"],
                gender=r["gender"],
                dob=r["dob"],
                address=r["address"],
                village_id=village_id,
                station_id=station_id,
                status="active",
                reg_type="legacy",
                reg_year=2025,
                reg_reason="legacy",
                photo_url=saved_photo_val,
                notes=r.get("reg_note", ""),
                created_at=now,
                updated_at=now
            )
            db.add(new_voter)
            inserted_count += 1

    db.commit()

    return {
        "success": True,
        "station_name": station.name,
        "village_name": village.name_kh,
        "total_records": len(records),
        "female_count": sum(1 for r in records if r.get("gender") == "ស្រី"),
        "male_count": sum(1 for r in records if r.get("gender") == "ប្រុស"),
        "inserted": inserted_count,
        "updated": updated_count,
        "skipped": skipped_count
    }
