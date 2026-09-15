import io
import re
import datetime
from typing import Dict, List, Any, Optional
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import BirthCertificate, Village, Voter, User, AuditLog
from app.audit import log_activity
from app.timezone_utils import get_cambodia_now, get_cambodia_today, get_cambodia_today_str

# Khmer Numerals Mapping
KHMER_NUMERALS = {
    '០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4',
    '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9'
}

def convert_khmer_numerals(text: str) -> str:
    """Converts Khmer digits ០-៩ to standard digits 0-9."""
    if not text:
        return ""
    result = str(text)
    for kh, ar in KHMER_NUMERALS.items():
        result = result.replace(kh, ar)
    return result

def clean_date_value(val: Any) -> Optional[str]:
    """Parse various Excel date types into YYYY-MM-DD string."""
    if val is None:
        return None
    
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime("%Y-%m-%d")
    
    s = convert_khmer_numerals(str(val)).strip()
    if not s:
        return None
    
    # 1. Matches YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD (supports trailing time)
    m1 = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        try:
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            return None

    # 2. Matches DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY (supports trailing time)
    m2 = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
    if m2:
        d, m, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            return None

    # 3. Matches 4-digit year only (e.g. 2008)
    m3 = re.match(r"^(\d{4})$", s)
    if m3:
        y = int(m3.group(1))
        if 1900 <= y <= 2100:
            return f"{y:04d}-01-01"
            
    return None

def normalize_gender(val: Any) -> Optional[str]:
    """Normalize gender to 'ប្រុស' or 'ស្រី'."""
    if not val:
        return None
    s = str(val).strip().lower()
    if any(k in s for k in ["ប្រុស", "male", "m", "ប", "boy", "man"]):
        return "ប្រុស"
    if any(k in s for k in ["ស្រី", "female", "f", "ស", "girl", "woman"]):
        return "ស្រី"
    return None

LATIN_MAP = {
    "ស៊ឹម": "SIM", "កែវ": "KEO", "ចាន់": "CHAN", "ហេង": "HENG", "ឡុង": "LONG",
    "ប៊ុន": "BUN", "សុខ": "SOK", "អ៊ុំ": "OUM", "អ៊ុក": "OUK", "ទូច": "TOUCH",
    "សួន": "SUON", "មាស": "MEAS", "គង់": "KONG", "ពេជ្រ": "PICH", "ឈុន": "CHHUN",
    "គឹម": "KIM", "វណ្ណា": "VANNA", "រតនា": "ROTHANA", "វិចិត្រ": "VICHET",
    "ធឿន": "THOEUN", "សុខា": "SOKHA", "ពិសិដ្ឋ": "PISETH", "សំណាង": "SAMNANG",
    "តារា": "DARA", "សម្បត្តិ": "SAMBATH", "វិបុល": "VIBOL", "បញ្ញា": "PANHA",
    "ចាន់ថន": "CHANTHORN", "វុទ្ធី": "VUTHY", "សិលា": "SEILA", "សុផល": "SOPHAL",
    "សុជាតិ": "SOCHEAT", "សុភា": "SOPHEA", "កល្យាណ": "KALYAN", "ចិន្តា": "CHINDA",
    "ស្រីពៅ": "SREYPOV", "ធីតា": "THIDA", "បុប្ផា": "BOPHA", "ចរិយា": "CHORIYA",
    "មុន្នី": "MONY", "ទេវី": "DEVI", "រស្មី": "REAKSMEY", "លក្ខិណា": "LEAKHENA", "វណ្ណី": "VANNY"
}

def transliterate_khmer_name(kh_name: str) -> str:
    """Best-effort conversion of Khmer name to Latin."""
    if not kh_name:
        return ""
    parts = kh_name.strip().split()
    latin_parts = [LATIN_MAP.get(p, p) for p in parts]
    return " ".join(latin_parts).upper()

def match_village_record(val: Any, villages: List[Village]) -> Optional[Village]:
    """Matches a cell value to one of the 10 villages in Nokor Pheas."""
    if not val:
        return None
    s = str(val).strip().lower()
    
    # 1. Match by numeric ID
    if s.isdigit():
        vid = int(s)
        for v in villages:
            if v.id == vid:
                return v

    # 2. Match by village code (e.g. V01, V02)
    clean_code = s.upper()
    for v in villages:
        if v.code.upper() == clean_code:
            return v
            
    # 3. Match by exact Khmer name or contained substring
    for v in villages:
        v_name = v.name_kh.lower()
        if s == v_name or s.replace("ភូមិ", "") == v_name.replace("ភូមិ", ""):
            return v
        if v_name.replace("ភូមិ", "") in s:
            return v
            
    # 4. Match by English name
    for v in villages:
        if v.name_en and v.name_en.lower() in s:
            return v
            
    return None

def calculate_age_from_dob(dob_str: str) -> int:
    """Calculate age based on current date in Cambodia."""
    try:
        b_date = datetime.datetime.strptime(dob_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
        return max(0, age)
    except Exception:
        return 0


# ==============================================================================
# 1. GENERATE OFFICIAL EXCEL SAMPLE TEMPLATE
# ==============================================================================
def generate_birth_excel_template(villages: List[Village]) -> io.BytesIO:
    """Creates a beautiful, pre-formatted Excel template for birth certificates."""
    wb = openpyxl.Workbook()
    
    # Sheet 1: Main Data Entry Sheet
    ws = wb.active
    ws.title = "ទម្រង់បញ្ចូលសំបុត្រកំណើត"
    ws.views.sheetView[0].showGridLines = True

    # Styling definitions
    title_font = Font(name="Khmer OS Muol Light", size=13, bold=True, color="0f2b5c")
    subtitle_font = Font(name="Khmer OS Siemreap", size=10, italic=True, color="334155")
    inst_font = Font(name="Khmer OS Siemreap", size=9, bold=True, color="B45309")
    header_font = Font(name="Khmer OS Siemreap", size=10, bold=True, color="FFFFFF")
    sample_font = Font(name="Khmer OS Siemreap", size=9)
    sample_bold_font = Font(name="Khmer OS Siemreap", size=9, bold=True)
    
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    req_header_fill = PatternFill(start_color="1D4ED8", end_color="1D4ED8", fill_type="solid")
    even_row_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    inst_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    # Titles
    ws.merge_cells("A1:M1")
    ws["A1"] = "ព្រះរាជាណាចក្រកម្ពុជា • ជាតិ សាសនា ព្រះមហាក្សត្រ"
    ws["A1"].font = Font(name="Khmer OS Muol Light", size=11, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:M2")
    ws["A2"] = "រដ្ឋបាលឃុំនគរភាស • ទម្រង់គំរូនាំចូលទិន្នន័យសំបុត្រកំណើត (Bulk Import Excel)"
    ws["A2"].font = title_font
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:M3")
    ws["A3"] = "👉 ណែនាំ៖ ជួរឈរដែលមានសញ្ញា (*) គឺជាទិន្នន័យចាំបាច់។ កាលបរិច្ឆេទអាចបញ្ចូលជា YYYY-MM-DD (ឧ. 2008-06-16) ឬ DD/MM/YYYY។ ភេទ៖ ប្រុស ឬ ស្រី។ ឈ្មោះភូមិអាចមើលសន្លឹកទី២។"
    ws["A3"].font = inst_font
    ws["A3"].fill = inst_fill
    ws["A3"].alignment = Alignment(horizontal="left", vertical="center")

    headers = [
        "លេខសំបុត្រកំណើត (*)",
        "សៀវភៅលេខ",
        "កាលបរិច្ឆេទចុះបញ្ជី",
        "ឈ្មោះជាភាសាខ្មែរ (*)",
        "ឈ្មោះជាអក្សរឡាតាំង",
        "ភេទ (*)",
        "ថ្ងៃខែឆ្នាំកំណើត (*)",
        "ទីកន្លែងកំណើត",
        "ឈ្មោះឪពុក",
        "ឈ្មោះម្តាយ",
        "ភូមិ (*)",
        "អាសយដ្ឋានបច្ចុប្បន្ន",
        "កំណត់សម្គាល់"
    ]

    ws.append([]) # Row 4 empty
    ws.append(headers) # Row 5
    header_row_idx = 5
    ws.row_dimensions[header_row_idx].height = 30

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.font = header_font
        cell.fill = req_header_fill if "(*)" in h else header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Sample rows
    sample_rows = [
        [
            "ស.ក-2008-0101", "05/2008", "2026-09-02", "ស៊ឹម វិចិត្រ", "SIM VICHET", "ប្រុស", "2008-06-16",
            "ភូមិរមៀត ឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប", "ស៊ឹម វណ្ណា", "មាស សុផល", "ភូមិរមៀត",
            "ក្រុមទី ០២ ភូមិរមៀត", "គំរូយុវជនគ្រប់អាយុ ១៨ ឆ្នាំ"
        ],
        [
            "ស.ក-2008-0102", "05/2008", "2026-09-05", "ឡុង កល្យាណ", "LONG KALYAN", "ស្រី", "2008-11-20",
            "ភូមិល្បើក ឃុំនគរភាស ស្រុកអង្គរជុំ", "ឡុង វិចិត្រ", "គឹម សុជាតិ", "ភូមិល្បើក",
            "ក្រុមទី ០១", ""
        ],
        [
            "ស.ក-2009-0103", "06/2009", "2026-09-10", "កែវ សំណាង", "KEO SAMNANG", "ប្រុស", "2009-04-08",
            "ភូមិសំបួរ ឃុំនគរភាស", "កែវ ចាន់ថន", "អ៊ុក ចរិយា", "ភូមិសំបួរ",
            "ក្រុមទី ០៥", "យុវជនគ្រប់អាយុឆ្នាំក្រោយ (២០២៧)"
        ]
    ]

    for i, row in enumerate(sample_rows, start=1):
        r_idx = header_row_idx + i
        ws.append(row)
        ws.row_dimensions[r_idx].height = 24
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.font = sample_bold_font if col_idx in [1, 4, 6, 7, 11] else sample_font
            cell.border = thin_border
            if col_idx in [1, 2, 3, 6, 7]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            if i % 2 == 0:
                cell.fill = even_row_fill

    # Adjust column widths
    col_widths = {
        1: 22, # លេខសំបុត្រ
        2: 15, # សៀវភៅលេខ
        3: 18, # កាលបរិច្ឆេទចុះបញ្ជី
        4: 20, # ឈ្មោះខ្មែរ
        5: 20, # ឈ្មោះឡាតាំង
        6: 12, # ភេទ
        7: 18, # ថ្ងៃខែឆ្នាំកំណើត
        8: 30, # ទីកន្លែងកំណើត
        9: 20, # ឪពុក
        10: 20, # ម្តាយ
        11: 18, # ភូមិ
        12: 24, # អាសយដ្ឋាន
        13: 25  # កំណត់សម្គាល់
    }
    for c_idx, w in col_widths.items():
        ws.column_dimensions[get_column_letter(c_idx)].width = w

    # Sheet 2: Reference Villages
    ws2 = wb.create_sheet(title="បញ្ជីឈ្មោះភូមិទាំង១០")
    ws2.views.sheetView[0].showGridLines = True
    
    ws2.merge_cells("A1:E1")
    ws2["A1"] = "បញ្ជីឈ្មោះភូមិផ្លូវការទាំង ១០ ក្នុងឃុំនគរភាស (សម្រាប់ប្រើក្នុងទម្រង់ Excel)"
    ws2["A1"].font = title_font
    ws2["A1"].alignment = Alignment(horizontal="center", vertical="center")
    
    v_headers = ["ល.រ", "កូដភូមិ", "ឈ្មោះភូមិជាភាសាខ្មែរ", "ឈ្មោះជាភាសាឡាតាំង", "ប្រធានភូមិ"]
    ws2.append([]) # Row 2 empty
    ws2.append(v_headers) # Row 3
    ws2.row_dimensions[3].height = 26
    
    for c_idx, v_h in enumerate(v_headers, start=1):
        c = ws2.cell(row=3, column=c_idx)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    sorted_villages = sorted(villages, key=lambda v: v.code)
    for idx, v in enumerate(sorted_villages, start=1):
        row_num = 3 + idx
        ws2.append([idx, v.code, v.name_kh, v.name_en or "", v.chief_name or ""])
        ws2.row_dimensions[row_num].height = 22
        for col_idx in range(1, 6):
            c = ws2.cell(row=row_num, column=col_idx)
            c.font = sample_bold_font if col_idx in [2, 3] else sample_font
            c.border = thin_border
            if col_idx in [1, 2]:
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")

    for c_idx, w in {1: 8, 2: 14, 3: 24, 4: 20, 5: 25}.items():
        ws2.column_dimensions[get_column_letter(c_idx)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ==============================================================================
# 2. PARSE UPLOADED EXCEL FILE WITH PREVIEW & VALIDATION
# ==============================================================================
def parse_birth_certificates_excel(file_bytes: bytes, filename: str, db: Session) -> Dict[str, Any]:
    """Parses uploaded Excel workbook, maps columns, and validates every row."""
    villages = db.query(Village).all()
    existing_db_certs = {
        row[0].strip().lower(): row[1] 
        for row in db.query(BirthCertificate.certificate_no, BirthCertificate.name_kh).all()
        if row[0]
    }
    
    # Pre-cache active voters for auto-matching
    voters_cache = {}
    for voter in db.query(Voter).filter(Voter.status == "active").all():
        key = (voter.name_kh.strip(), voter.dob.strip(), voter.village_id)
        voters_cache[key] = {
            "id": voter.id,
            "voter_code": voter.voter_code,
            "name_kh": voter.name_kh
        }

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        return {
            "success": False,
            "error": f"មិនអាចអានឯកសារ Excel បានទេ៖ {str(e)}"
        }

    # Select the first sheet or the sheet named 'ទម្រង់បញ្ចូលសំបុត្រកំណើត'
    sheet = None
    if "ទម្រង់បញ្ចូលសំបុត្រកំណើត" in wb.sheetnames:
        sheet = wb["ទម្រង់បញ្ចូលសំបុត្រកំណើត"]
    else:
        sheet = wb.active

    if not sheet:
        return {"success": False, "error": "រកមិនឃើញសន្លឹកកិច្ចការ (Worksheet) ក្នុងឯកសារ Excel ឡើយ"}

    # Detect header row by scanning rows for highest column match count
    header_row_idx = None
    header_col_map = {}
    best_score = 0
    best_col_map = {}

    max_search_rows = min(sheet.max_row + 1, 20)
    for r in range(1, max_search_rows):
        candidate_map = {}
        for c in range(1, sheet.max_column + 1):
            val = str(sheet.cell(row=r, column=c).value or "").strip()
            if not val:
                continue
            v_lower = val.lower()
            if any(k in v_lower for k in ["លេខសំបុត្រ", "cert_no", "certificate"]):
                candidate_map["certificate_no"] = c
            elif any(k in v_lower for k in ["សៀវភៅ", "book_no", "book"]):
                candidate_map["book_no"] = c
            elif any(k in v_lower for k in ["កាលបរិច្ឆេទចុះ", "កាលបរិច្ឆេទ", "registered_date", "reg_date"]):
                candidate_map["registered_date"] = c
            elif any(k in v_lower for k in ["ឈ្មោះជាភាសាខ្មែរ", "ឈ្មោះខ្មែរ", "name_kh"]):
                candidate_map["name_kh"] = c
            elif any(k in v_lower for k in ["ឈ្មោះជាអក្សរឡាតាំង", "ឡាតាំង", "name_en", "latin"]):
                candidate_map["name_en"] = c
            elif any(k in v_lower for k in ["ភេទ", "gender", "sex"]):
                candidate_map["gender"] = c
            elif any(k in v_lower for k in ["ថ្ងៃខែឆ្នាំកំណើត", "ថ្ងៃកំណើត", "dob", "birth_date"]):
                candidate_map["dob"] = c
            elif any(k in v_lower for k in ["ទីកន្លែងកំណើត", "pob", "place_of_birth"]):
                candidate_map["pob"] = c
            elif any(k in v_lower for k in ["ឪពុក", "father", "father_name"]):
                candidate_map["father_name"] = c
            elif any(k in v_lower for k in ["ម្តាយ", "mother", "mother_name"]):
                candidate_map["mother_name"] = c
            elif any(k in v_lower for k in ["ភូមិ", "village", "village_name"]):
                candidate_map["village"] = c
            elif any(k in v_lower for k in ["អាសយដ្ឋាន", "address"]):
                candidate_map["address"] = c
            elif any(k in v_lower for k in ["កំណត់សម្គាល់", "notes", "note"]):
                candidate_map["notes"] = c

        if len(candidate_map) > best_score:
            best_score = len(candidate_map)
            header_row_idx = r
            best_col_map = candidate_map

    # If header found with at least 2 matching columns, use it; otherwise fallback to positional
    if best_score >= 2 and header_row_idx:
        header_col_map = best_col_map
    else:
        header_row_idx = 4
        header_col_map = {
            "certificate_no": 1,
            "book_no": 2,
            "registered_date": 3,
            "name_kh": 4,
            "name_en": 5,
            "gender": 6,
            "dob": 7,
            "pob": 8,
            "father_name": 9,
            "mother_name": 10,
            "village": 11,
            "address": 12,
            "notes": 13
        }

    parsed_records: List[Dict[str, Any]] = []
    seen_in_file_certs = set()
    total_rows = 0
    valid_count = 0
    warning_count = 0
    error_count = 0

    start_row = header_row_idx + 1
    for r in range(start_row, sheet.max_row + 1):
        # Extract cell values
        def get_val(key):
            col_idx = header_col_map.get(key)
            if col_idx:
                v = sheet.cell(row=r, column=col_idx).value
                return v
            return None

        raw_cert_no = get_val("certificate_no")
        raw_name_kh = get_val("name_kh")
        
        # Skip completely empty rows
        if raw_cert_no is None and raw_name_kh is None:
            continue

        raw_cert_str = str(raw_cert_no or "").strip().lower()
        raw_name_str = str(raw_name_kh or "").strip().lower()

        # Skip header or instructions if repeated
        if any(k in raw_cert_str for k in ["លេខសំបុត្រ", "certificate", "cert_no"]) or \
           any(k in raw_name_str for k in ["ឈ្មោះជាភាសាខ្មែរ", "ឈ្មោះខ្មែរ"]):
            continue

        total_rows += 1
        issues = []
        status = "valid"

        # 1. Certificate Number
        cert_no = convert_khmer_numerals(str(raw_cert_no or "")).strip()
        if not cert_no:
            issues.append("ខ្វះលេខសំបុត្រកំណើត")
            status = "error"

        # 2. Name Khmer
        name_kh = str(raw_name_kh or "").strip()
        if not name_kh:
            issues.append("ខ្វះឈ្មោះជាភាសាខ្មែរ")
            status = "error"

        # 3. Name English
        raw_name_en = str(get_val("name_en") or "").strip()
        name_en = raw_name_en.upper() if raw_name_en else transliterate_khmer_name(name_kh)

        # 4. Gender
        gender = normalize_gender(get_val("gender"))
        if not gender:
            issues.append("ភេទមិនត្រឹមត្រូវ (ត្រូវជា 'ប្រុស' ឬ 'ស្រី')")
            status = "error"

        # 5. Date of Birth
        dob_str = clean_date_value(get_val("dob"))
        age = 0
        is_eligible_18 = False
        if not dob_str:
            issues.append("ថ្ងៃខែឆ្នាំកំណើតមិនត្រឹមត្រូវ (ឧ. 2008-06-16)")
            status = "error"
        else:
            age = calculate_age_from_dob(dob_str)
            is_eligible_18 = (age >= 18)

        # 6. Village Matching
        village_match = match_village_record(get_val("village"), villages)
        if not village_match:
            issues.append("រកមិនឃើញភូមិដែលត្រូវគ្នាឡើយ")
            status = "error"

        # 7. Registration Date
        reg_date_str = clean_date_value(get_val("registered_date"))
        if not reg_date_str:
            reg_date_str = get_cambodia_today_str()

        # 8. Check Duplicates
        is_dup_db = False
        is_dup_file = False
        if cert_no:
            cert_key = cert_no.lower()
            if cert_key in existing_db_certs:
                is_dup_db = True
                dup_owner = existing_db_certs[cert_key]
                issues.append(f"ស្ទួនលេខក្នុងប្រព័ន្ធរួចហើយ ({dup_owner})")
                if status != "error":
                    status = "warning"
            if cert_key in seen_in_file_certs:
                is_dup_file = True
                issues.append("ស្ទួនលេខជាមួយជួរដេកផ្សេងក្នុងឯកសារនេះ")
                status = "error"
            seen_in_file_certs.add(cert_key)

        # 9. Auto-check matching with registered voter
        matched_voter = None
        if name_kh and dob_str and village_match:
            v_key = (name_kh, dob_str, village_match.id)
            if v_key in voters_cache:
                matched_voter = voters_cache[v_key]

        if status == "valid":
            valid_count += 1
        elif status == "warning":
            warning_count += 1
        else:
            error_count += 1

        rec = {
            "row_idx": r,
            "certificate_no": cert_no,
            "book_no": str(get_val("book_no") or "").strip(),
            "registered_date": reg_date_str,
            "name_kh": name_kh,
            "name_en": name_en,
            "gender": gender or "ប្រុស",
            "dob": dob_str or "",
            "age": age,
            "is_eligible_18": is_eligible_18,
            "village_id": village_match.id if village_match else None,
            "village_name": village_match.name_kh if village_match else str(get_val("village") or ""),
            "pob": str(get_val("pob") or "").strip(),
            "father_name": str(get_val("father_name") or "").strip(),
            "mother_name": str(get_val("mother_name") or "").strip(),
            "address": str(get_val("address") or "").strip(),
            "notes": str(get_val("notes") or "").strip(),
            "status": status,
            "issues": issues,
            "is_dup_db": is_dup_db,
            "is_dup_file": is_dup_file,
            "matched_voter": matched_voter
        }
        parsed_records.append(rec)

    return {
        "success": True,
        "filename": filename,
        "total_rows": total_rows,
        "valid_count": valid_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "records": parsed_records
    }


# ==============================================================================
# 3. EXECUTE IMPORT INTO DATABASE
# ==============================================================================
def execute_birth_import(
    records: List[Dict[str, Any]], 
    current_user: User, 
    db: Session, 
    on_duplicate: str = "skip"
) -> Dict[str, Any]:
    """
    Inserts or updates birth certificates in the database.
    on_duplicate options: 'skip', 'overwrite'
    """
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    for item in records:
        cert_no = (item.get("certificate_no") or "").strip()
        name_kh = (item.get("name_kh") or "").strip()
        dob = (item.get("dob") or "").strip()
        village_id = item.get("village_id")
        gender = item.get("gender") or "ប្រុស"

        # Basic validity check
        if not cert_no or not name_kh or not dob or not village_id:
            failed_count += 1
            continue

        existing = db.query(BirthCertificate).filter(
            func.lower(func.trim(BirthCertificate.certificate_no)) == cert_no.lower()
        ).first()

        # Check existing voter to auto-link
        matched_voter = db.query(Voter).filter(
            Voter.name_kh == name_kh,
            Voter.dob == dob,
            Voter.village_id == village_id
        ).first()

        is_reg = True if matched_voter else False
        voter_id = matched_voter.id if matched_voter else None

        if existing:
            if on_duplicate == "skip":
                skipped_count += 1
                continue
            elif on_duplicate == "overwrite":
                existing.book_no = item.get("book_no") or existing.book_no
                existing.name_kh = name_kh
                existing.name_en = (item.get("name_en") or existing.name_en).upper()
                existing.gender = gender
                existing.dob = dob
                existing.registered_date = item.get("registered_date") or existing.registered_date
                existing.village_id = village_id
                existing.pob = item.get("pob") or existing.pob
                existing.father_name = item.get("father_name") or existing.father_name
                existing.mother_name = item.get("mother_name") or existing.mother_name
                existing.address = item.get("address") or existing.address
                if item.get("notes"):
                    existing.notes = item.get("notes")
                if matched_voter:
                    existing.is_registered_voter = True
                    existing.voter_id = matched_voter.id
                updated_count += 1
        else:
            bc = BirthCertificate(
                certificate_no=cert_no,
                book_no=item.get("book_no") or None,
                name_kh=name_kh,
                name_en=(item.get("name_en") or transliterate_khmer_name(name_kh)).upper(),
                gender=gender,
                dob=dob,
                registered_date=item.get("registered_date") or get_cambodia_today_str(),
                village_id=village_id,
                pob=item.get("pob") or None,
                father_name=item.get("father_name") or None,
                mother_name=item.get("mother_name") or None,
                address=item.get("address") or None,
                notes=item.get("notes") or "នាំចូលពី Excel",
                is_registered_voter=is_reg,
                voter_id=voter_id
            )
            db.add(bc)
            imported_count += 1

    db.commit()

    log_activity(
        db=db,
        user=current_user,
        action="IMPORT_EXCEL_BIRTH_CERTS",
        action_type="success",
        target_type="birth_certificate",
        target_id=str(imported_count + updated_count),
        description=f"បាននាំចូលទិន្នន័យសំបុត្រកំណើតពី Excel៖ បញ្ចូលថ្មី {imported_count} នាក់, កែប្រែ {updated_count} នាក់, រំលងស្ទួន {skipped_count} នាក់"
    )

    return {
        "success": True,
        "imported_count": imported_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "total_processed": len(records)
    }
