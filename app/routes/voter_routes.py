import os
import re
import io
import uuid
import base64
import datetime
import urllib.parse
from fastapi import APIRouter, Request, Depends, HTTPException, Query, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc, func
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.database import get_db
from app.models import User, Village, PollingStation, Voter
from app.auth import get_current_user_optional, get_current_user, require_admin, require_admin_or_officer
from app.schemas import VoterCreateSchema, VoterUpdateSchema
from app.audit import log_activity
from app.timezone_utils import get_cambodia_now, get_cambodia_today
from app.ocr_utils import parse_khmer_id_text, extract_id_card_face_portrait

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "voters")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitize_national_id_backend(raw_id: str) -> str:
    if not raw_id:
        raise HTTPException(status_code=400, detail="សូមបញ្ចូលលេខអត្តសញ្ញាណប័ណ្ណ ឬអត្តលេខ-ឯ.អ")
    # Convert Khmer numerals ០-៩ to 0-9
    khmer_map = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")
    converted = raw_id.strip().translate(khmer_map)
    # Remove any non-digits
    clean = re.sub(r"[^0-9]", "", converted)
    if not clean:
        raise HTTPException(
            status_code=400,
            detail="លេខអត្តសញ្ញាណត្រូវតែជាលេខ (0-9) តែប៉ុណ្ណោះ មិនអនុញ្ញាតអក្សរ ឬនិមិត្តសញ្ញាឡើយ"
        )
    if len(clean) not in [7, 8, 9]:
        raise HTTPException(
            status_code=400,
            detail=f"លេខឯកសារមិនត្រឹមត្រូវ ({len(clean)} ខ្ទង់)៖ ប្រព័ន្ធអនុញ្ញាតលេខ ៨ ខ្ទង់ (អត្តលេខ-ឯ.អ) ឬ ៩ ខ្ទង់ (លេខអត្តសញ្ញាណប័ណ្ណ)"
        )
    return clean

from app.image_utils import process_and_encode_image

def save_uploaded_photo(upload_file: UploadFile) -> str:
    return process_and_encode_image(upload_file, subfolder="voters", max_size=(300, 300), quality=85)

def calculate_age(dob_str: str) -> str:
    if not dob_str:
        return ""
    try:
        birth_year = int(str(dob_str).strip()[:4])
        current_year = get_cambodia_now().year
        age = current_year - birth_year
        return str(age) if age >= 0 else ""
    except Exception:
        return ""

def build_voter_query(
    db: Session,
    current_user: User = None,
    q: str = "",
    village_id: str = "",
    station_id: str = "",
    status_filter: str = "",
    gender_filter: str = "",
    age_group: str = "",
    voted_filter: str = "",
    clean_date: str = "",
    effective_reg_type: str = "",
    effective_reg_year: str = ""
):
    query = db.query(Voter)

    # Role-based restriction
    if current_user and current_user.role == "officer" and current_user.station_id:
        query = query.filter(Voter.station_id == current_user.station_id)
    elif current_user and current_user.role == "village_chief" and current_user.village_id:
        query = query.filter(Voter.village_id == current_user.village_id)

    # Keyword Search (Name Khmer, Name Latin, National ID, Voter Code)
    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Voter.name_kh.ilike(search),
                Voter.name_en.ilike(search),
                Voter.national_id.ilike(search),
                Voter.voter_code.ilike(search)
            )
        )

    # Village filter
    if village_id and str(village_id).isdigit():
        query = query.filter(Voter.village_id == int(village_id))

    # Polling station filter
    if station_id and str(station_id).isdigit():
        query = query.filter(Voter.station_id == int(station_id))

    # Status filter
    if status_filter:
        query = query.filter(Voter.status == status_filter)

    # Gender filter
    if gender_filter:
        query = query.filter(Voter.gender == gender_filter)

    # Voted filter
    if voted_filter == "voted":
        query = query.filter(Voter.has_voted == True)
    elif voted_filter == "not_voted":
        query = query.filter(Voter.has_voted == False)

    # Registration date filter (safe ISO date parsing)
    if clean_date:
        try:
            datetime.date.fromisoformat(clean_date)
            query = query.filter(func.date(Voter.created_at) == clean_date)
        except ValueError:
            pass

    # Registration Type filter (new, legacy, transferred)
    if effective_reg_type:
        query = query.filter(Voter.reg_type == effective_reg_type)

    # Registration Year filter
    if effective_reg_year and str(effective_reg_year).isdigit():
        query = query.filter(Voter.reg_year == int(effective_reg_year))

    # Age group filter (youth: 18-35, adult: 36-59, elderly: 60+)
    if age_group:
        current_year = get_cambodia_now().year
        if age_group == "youth":
            min_y = current_year - 35
            max_y = current_year - 18
            query = query.filter(Voter.dob.isnot(None), Voter.dob >= str(min_y), Voter.dob < str(max_y + 1))
        elif age_group == "adult":
            min_y = current_year - 59
            max_y = current_year - 36
            query = query.filter(Voter.dob.isnot(None), Voter.dob >= str(min_y), Voter.dob < str(max_y + 1))
        elif age_group == "elderly":
            max_y = current_year - 60
            query = query.filter(Voter.dob.isnot(None), Voter.dob >= "1900", Voter.dob < str(max_y + 1))

    return query

def generate_voters_excel(voters, filter_title: str = "ឃុំនគរភាសទាំងមូល") -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "បញ្ជីឈ្មោះបោះឆ្នោត"

    # Styles
    title_font = Font(name="Khmer OS Siemreap", size=14, bold=True, color="001F3F")
    subtitle_font = Font(name="Khmer OS Siemreap", size=11, bold=True, color="333333")
    header_font = Font(name="Khmer OS Siemreap", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Khmer OS Siemreap", size=10)

    header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
    sub_header_fill = PatternFill(start_color="F0F4F8", end_color="F0F4F8", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E0'),
        right=Side(style='thin', color='CBD5E0'),
        top=Side(style='thin', color='CBD5E0'),
        bottom=Side(style='thin', color='CBD5E0')
    )

    # Title Rows (15 columns A to O)
    ws.merge_cells("A1:O1")
    ws["A1"] = "ព្រះរាជាណាចក្រកម្ពុជា ជាតិ សាសនា ព្រះមហាក្សត្រ"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:O2")
    ws["A2"] = f"បញ្ជីឈ្មោះអ្នកចុះឈ្មោះបោះឆ្នោត - រដ្ឋបាលឃុំនគរភាស ({filter_title})"
    ws["A2"].font = subtitle_font
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:O3")
    now_str = get_cambodia_now().strftime("%d-%m-%Y %H:%M")
    ws["A3"] = f"កាលបរិច្ឆេទចេញរបាយការណ៍៖ {now_str} | ចំនួនសរុប៖ {len(voters)} នាក់"
    ws["A3"].font = Font(name="Khmer OS Siemreap", size=9, italic=True, color="666666")
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 22
    ws.row_dimensions[3].height = 18
    ws.row_dimensions[5].height = 28

    # Headers
    headers = [
        "ល.រ", "កូដអ្នកបោះឆ្នោត", "លេខរៀងបញ្ជី", "លេខអត្តសញ្ញាណប័ណ្ណ",
        "គោត្តនាម-នាម", "អក្សរឡាតាំង", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត",
        "អាយុ", "ភូមិ", "ការិយាល័យបោះឆ្នោត", "ប្រភេទបញ្ជី",
        "ស្ថានភាព", "ស្ថានភាពវត្តមាន", "ហត្ថលេខា / ស្នាមមេដៃ"
    ]

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Mapping helpers for clean Khmer display
    status_map = {
        "active": "សកម្ម",
        "deceased": "ទទួលមរណភាព",
        "moved": "ផ្ទេរចេញ",
        "suspended": "ផ្អាក"
    }
    reg_type_map = {
        "new": "ចុះថ្មី",
        "legacy": "បញ្ជីចាស់",
        "transferred": "ផ្ទេរចូល"
    }

    # Data Rows
    row_num = 6
    for idx, v in enumerate(voters, 1):
        voted_status = "បោះឆ្នោតរួច" if v.has_voted else "មិនទាន់បោះ"
        st_text = status_map.get(v.status, v.status or "")
        reg_text = reg_type_map.get(v.reg_type, v.reg_type or "")
        age_text = calculate_age(v.dob)

        ws.cell(row=row_num, column=1, value=idx).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=2, value=v.voter_code or "").alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=3, value=v.list_no or "").alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=4, value=v.national_id or "").alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=5, value=v.name_kh or "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=6, value=v.name_en or "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=7, value=v.gender or "").alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=8, value=v.dob or "").alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=9, value=age_text).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=10, value=v.village.name_kh if v.village else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=11, value=f"{v.station.code} - {v.station.name}" if v.station else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=12, value=reg_text).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=13, value=st_text).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=14, value=voted_status).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=15, value="").alignment = Alignment(horizontal="center")

        for c in range(1, 16):
            cell = ws.cell(row=row_num, column=c)
            cell.font = data_font
            cell.border = thin_border
            if row_num % 2 == 1:
                cell.fill = sub_header_fill

        ws.row_dimensions[row_num].height = 20
        row_num += 1

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row < 5:
                continue
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)

    ws.column_dimensions['O'].width = 18  # Signature column

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

@router.get("/voters", response_class=HTMLResponse)
def voter_list_page(
    request: Request,
    q: str = Query("", description="Search text"),
    village_id: str = Query("", description="Village filter"),
    station_id: str = Query("", description="Station filter"),
    status_filter: str = Query("", description="Status filter"),
    gender_filter: str = Query("", description="Gender filter"),
    age_group: str = Query("", description="Age group filter: youth, adult, elderly"),
    voted_filter: str = Query("", description="Voted filter (all, voted, not_voted)"),
    date_created: str = Query("", description="Registration date filter YYYY-MM-DD"),
    reg_type_filter: str = Query("", description="Registration type filter (new, legacy, transferred)"),
    reg_year_filter: str = Query("", description="Registration year filter"),
    _type_filter: str = Query("", description="Legacy alias for reg_type_filter"),
    _year_filter: str = Query("", description="Legacy alias for reg_year_filter"),
    page: int = Query(1),
    limit: int = Query(10),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role == "viewer":
        return RedirectResponse(url="/reports", status_code=302)

    # Safe pagination bounds
    if page < 1:
        page = 1
    if limit < 1:
        limit = 10
    elif limit > 200:
        limit = 200

    # Safe parameter normalization (handling HTML entity collision e.g. &reg -> ®)
    qp = request.query_params
    raw_date = (date_created or qp.get("date_created") or "").strip()
    clean_date = ""
    effective_reg_type = ""
    effective_reg_year = ""

    # Check if date_created was polluted by browser HTML entity parser (e.g. &reg consumed into ®_type_filter)
    if "®" in raw_date or "\u00ae" in raw_date or "_type_filter" in raw_date or "=" in raw_date or len(raw_date) > 10:
        # Extract any parameters trapped inside date_created
        if "type_filter=" in raw_date:
            m_t = re.search(r"type_filter=([^&]*)", raw_date)
            if m_t and m_t.group(1):
                effective_reg_type = m_t.group(1)
        if "year_filter=" in raw_date:
            m_y = re.search(r"year_filter=([^&]*)", raw_date)
            if m_y and m_y.group(1):
                effective_reg_year = m_y.group(1)
        # Attempt to get clean date before junk if any
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw_date)
        if date_match:
            clean_date = date_match.group(1)
    else:
        clean_date = raw_date

    # Fallback to legacy & entity aliases if primary not set
    if not effective_reg_type:
        effective_reg_type = (
            reg_type_filter or 
            qp.get("reg_type_filter") or 
            qp.get("type_filter") or 
            qp.get("_type_filter") or 
            qp.get("®_type_filter") or 
            qp.get("\u00ae_type_filter") or 
            ""
        ).strip()

    if not effective_reg_year:
        effective_reg_year = (
            reg_year_filter or 
            qp.get("reg_year_filter") or 
            qp.get("year_filter") or 
            qp.get("_year_filter") or 
            qp.get("®_year_filter") or 
            qp.get("\u00ae_year_filter") or 
            ""
        ).strip()

    # Build query using shared builder
    query = build_voter_query(
        db=db,
        current_user=current_user,
        q=q,
        village_id=village_id,
        station_id=station_id,
        status_filter=status_filter,
        gender_filter=gender_filter,
        age_group=age_group,
        voted_filter=voted_filter,
        clean_date=clean_date,
        effective_reg_type=effective_reg_type,
        effective_reg_year=effective_reg_year
    )

    total_count = query.count()
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    # Ensure page does not exceed total_pages when voters exist
    if total_count > 0 and page > total_pages:
        page = total_pages

    # Order by station, list_no
    voters = (
        query.order_by(Voter.station_id.asc(), Voter.list_no.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    # Distinct registration years for filter
    years_raw = db.query(Voter.reg_year).distinct().order_by(Voter.reg_year.desc()).all()
    available_years = [y[0] for y in years_raw if y[0]]
    if 2026 not in available_years:
        available_years.insert(0, 2026)

    # Build clean query string for pagination links & active filters
    active_params = {}
    if q.strip():
        active_params["q"] = q.strip()
    if village_id:
        active_params["village_id"] = village_id
    if station_id:
        active_params["station_id"] = station_id
    if status_filter:
        active_params["status_filter"] = status_filter
    if gender_filter:
        active_params["gender_filter"] = gender_filter
    if voted_filter:
        active_params["voted_filter"] = voted_filter
    if date_created and date_created.strip():
        active_params["date_created"] = date_created.strip()
    if effective_reg_type:
        active_params["reg_type_filter"] = effective_reg_type
    if effective_reg_year:
        active_params["reg_year_filter"] = effective_reg_year
    if age_group:
        active_params["age_group"] = age_group

    has_active_filter = bool(active_params)
    filter_querystring = ("&" + urllib.parse.urlencode(active_params)) if active_params else ""
    export_excel_url = f"/voters/export/excel?{urllib.parse.urlencode(active_params)}" if active_params else "/voters/export/excel"

    village_obj = next((v for v in villages if str(v.id) == str(village_id)), None) if village_id else None
    village_name = village_obj.name_kh if village_obj else ""

    station_obj = next((s for s in stations if str(s.id) == str(station_id)), None) if station_id else None
    station_name = f"{station_obj.code} - {station_obj.name}" if station_obj else ""

    return templates.TemplateResponse(request=request, name="voters/list.html", context={
        "current_user": current_user,
        "voters": voters,
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "q": q,
        "village_id": village_id,
        "village_name": village_name,
        "station_id": station_id,
        "station_name": station_name,
        "status_filter": status_filter,
        "gender_filter": gender_filter,
        "age_group": age_group,
        "voted_filter": voted_filter,
        "date_created": date_created,
        "reg_type_filter": effective_reg_type,
        "reg_year_filter": effective_reg_year,
        "filter_querystring": filter_querystring,
        "available_years": available_years,
        "villages": villages,
        "stations": stations,
        "has_active_filter": has_active_filter,
        "export_excel_url": export_excel_url
    })

@router.get("/voters/export/excel")
def export_filtered_voters_excel(
    request: Request,
    q: str = Query("", description="Search text"),
    village_id: str = Query("", description="Village filter"),
    station_id: str = Query("", description="Station filter"),
    status_filter: str = Query("", description="Status filter"),
    gender_filter: str = Query("", description="Gender filter"),
    age_group: str = Query("", description="Age group filter: youth, adult, elderly"),
    voted_filter: str = Query("", description="Voted filter (all, voted, not_voted)"),
    date_created: str = Query("", description="Registration date filter YYYY-MM-DD"),
    reg_type_filter: str = Query("", description="Registration type filter (new, legacy, transferred)"),
    reg_year_filter: str = Query("", description="Registration year filter"),
    _type_filter: str = Query("", description="Legacy alias"),
    _year_filter: str = Query("", description="Legacy alias"),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)

    qp = request.query_params
    raw_date = (date_created or qp.get("date_created") or "").strip()
    clean_date = ""
    effective_reg_type = ""
    effective_reg_year = ""

    if "®" in raw_date or "\u00ae" in raw_date or "_type_filter" in raw_date or "=" in raw_date or len(raw_date) > 10:
        if "type_filter=" in raw_date:
            m_t = re.search(r"type_filter=([^&]*)", raw_date)
            if m_t and m_t.group(1):
                effective_reg_type = m_t.group(1)
        if "year_filter=" in raw_date:
            m_y = re.search(r"year_filter=([^&]*)", raw_date)
            if m_y and m_y.group(1):
                effective_reg_year = m_y.group(1)
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw_date)
        if date_match:
            clean_date = date_match.group(1)
    else:
        clean_date = raw_date

    if not effective_reg_type:
        effective_reg_type = (
            reg_type_filter or 
            qp.get("reg_type_filter") or 
            qp.get("type_filter") or 
            qp.get("_type_filter") or 
            qp.get("®_type_filter") or 
            qp.get("\u00ae_type_filter") or 
            ""
        ).strip()

    if not effective_reg_year:
        effective_reg_year = (
            reg_year_filter or 
            qp.get("reg_year_filter") or 
            qp.get("year_filter") or 
            qp.get("_year_filter") or 
            qp.get("®_year_filter") or 
            qp.get("\u00ae_year_filter") or 
            ""
        ).strip()

    # Build filtered query
    query = build_voter_query(
        db=db,
        current_user=current_user,
        q=q,
        village_id=village_id,
        station_id=station_id,
        status_filter=status_filter,
        gender_filter=gender_filter,
        age_group=age_group,
        voted_filter=voted_filter,
        clean_date=clean_date,
        effective_reg_type=effective_reg_type,
        effective_reg_year=effective_reg_year
    )

    voters = query.order_by(Voter.station_id.asc(), Voter.list_no.asc()).all()

    # Build human-readable filter title for Excel header
    title_parts = []
    if q and q.strip():
        title_parts.append(f"ស្វែងរក៖ \"{q.strip()}\"")
    if village_id and str(village_id).isdigit():
        v_obj = db.query(Village).filter(Village.id == int(village_id)).first()
        if v_obj:
            title_parts.append(f"ភូមិ {v_obj.name_kh}")
    if station_id and str(station_id).isdigit():
        s_obj = db.query(PollingStation).filter(PollingStation.id == int(station_id)).first()
        if s_obj:
            title_parts.append(f"ការិយាល័យ {s_obj.code}")
    if age_group:
        age_map = {"youth": "យុវជន (១៨-៣៥)", "adult": "វ័យកណ្តាល (៣៦-៥៩)", "elderly": "មនុស្សចាស់ (៦០+)"}
        title_parts.append(f"ក្រុមអាយុ៖ {age_map.get(age_group, age_group)}")
    if effective_reg_type:
        reg_map = {"new": "ចុះថ្មី", "legacy": "បញ្ជីចាស់", "transferred": "ផ្ទេរចូល"}
        title_parts.append(f"ប្រភេទ៖ {reg_map.get(effective_reg_type, effective_reg_type)}")
    if gender_filter:
        title_parts.append(f"ភេទ៖ {gender_filter}")
    if status_filter:
        status_map = {"active": "សកម្ម", "deceased": "ទទួលមរណភាព", "moved": "ផ្ទេរចេញ", "suspended": "ផ្អាក"}
        title_parts.append(f"ស្ថានភាព៖ {status_map.get(status_filter, status_filter)}")
    if voted_filter:
        title_parts.append("បានបោះឆ្នោត" if voted_filter == "voted" else "មិនទាន់បោះ")
    if clean_date:
        title_parts.append(f"ថ្ងៃចុះឈ្មោះ៖ {clean_date}")

    filter_title = " • ".join(title_parts) if title_parts else "ឃុំនគរភាសទាំងមូល"

    excel_output = generate_voters_excel(voters, filter_title=filter_title)

    filename = f"Voter_List_Filtered_{get_cambodia_now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        excel_output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/api/voters/check-duplicate-id")
def check_duplicate_national_id(
    national_id: str = Query(...),
    exclude_id: int = Query(0),
    db: Session = Depends(get_db)
):
    try:
        clean_id = sanitize_national_id_backend(national_id)
    except HTTPException:
        clean_id = national_id.strip()

    doc_type_name = "អត្តលេខ-ឯ.អ" if len(clean_id) == 8 else ("លេខអត្តសញ្ញាណប័ណ្ណ" if len(clean_id) == 9 else "ឯកសារបញ្ជាក់អត្តសញ្ញាណ")
    query = db.query(Voter).filter(Voter.national_id == clean_id)
    if exclude_id > 0:
        query = query.filter(Voter.id != exclude_id)
    existing = query.first()
    if existing:
        v_name = f"ភូមិ{existing.village.name_kh}" if existing.village else ""
        s_name = f"ការិយាល័យ {existing.station.code}" if existing.station else ""
        details = " • ".join(filter(None, [existing.voter_code, v_name, s_name]))
        return {
            "duplicate": True,
            "doc_type": "cert_election" if len(clean_id) == 8 else "national_id",
            "doc_label": doc_type_name,
            "message": f"{doc_type_name} '{clean_id}' ត្រូវបានចុះឈ្មោះដោយឈ្មោះ '{existing.name_kh}' ({details}) រួចហើយ!",
            "voter": {
                "id": existing.id,
                "name_kh": existing.name_kh,
                "voter_code": existing.voter_code,
                "station_code": existing.station.code if existing.station else "",
                "station_name": existing.station.name if existing.station else ""
            }
        }
    return {
        "duplicate": False,
        "doc_type": "cert_election" if len(clean_id) == 8 else "national_id",
        "doc_label": doc_type_name,
        "message": f"{doc_type_name} ត្រឹមត្រូវ (អាចប្រើប្រាស់បាន)"
    }

@router.get("/api/avatars")
def get_avatar_presets():
    return {
        "males": [
            {"id": "m1", "url": "/static/images/avatars/male_1.jpg", "label": "រូបបុរស ១"},
            {"id": "m2", "url": "/static/images/avatars/male_2.jpg", "label": "រូបបុរស ២"},
            {"id": "m3", "url": "/static/images/avatars/male_3.jpg", "label": "រូបបុរស ៣"},
            {"id": "m4", "url": "/static/images/avatars/male_4.jpg", "label": "រូបបុរស ៤"},
        ],
        "females": [
            {"id": "f1", "url": "/static/images/avatars/female_1.jpg", "label": "រូបស្រ្តី ១"},
            {"id": "f2", "url": "/static/images/avatars/female_2.jpg", "label": "រូបស្រ្តី ២"},
            {"id": "f3", "url": "/static/images/avatars/female_3.jpg", "label": "រូបស្រ្តី ៣"},
        ]
    }

def validate_voter_age_backend(dob_str: str) -> None:
    if not dob_str or not dob_str.strip():
        return
    clean_dob = dob_str.strip()
    try:
        if '-' in clean_dob:
            parts = [int(p) for p in clean_dob.split('-')]
            if parts[0] > 1900:
                birth = datetime.date(parts[0], parts[1], parts[2])
            else:
                birth = datetime.date(parts[2], parts[1], parts[0])
        elif '/' in clean_dob:
            parts = [int(p) for p in clean_dob.split('/')]
            if parts[0] > 1900:
                birth = datetime.date(parts[0], parts[1], parts[2])
            else:
                birth = datetime.date(parts[2], parts[1], parts[0])
        else:
            birth = datetime.date.fromisoformat(clean_dob)

        today = get_cambodia_today()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if age < 18:
            raise HTTPException(
                status_code=400,
                detail=f"មិនអាចចុះឈ្មោះបានឡើយ៖ ពលរដ្ឋមានអាយុត្រឹម {age} ឆ្នាំ (មិនទាន់គ្រប់ ១៨ ឆ្នាំតាមច្បាប់បោះឆ្នោត)"
            )
    except (ValueError, IndexError):
        pass

@router.post("/api/voters")
def create_voter(
    name_kh: str = Form(...),
    name_en: str = Form(...),
    gender: str = Form(...),
    dob: str = Form(...),
    national_id: str = Form(...),
    village_id: int = Form(...),
    station_id: int = Form(...),
    reg_type: str = Form("new"),
    reg_year: int = Form(2026),
    reg_reason: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    force_save: str = Form("0"),
    photo_preset: str = Form(None),
    photo: UploadFile = File(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role not in ["admin", "officer"]:
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិបញ្ចូលទិន្នន័យ (Permission denied)")

    validate_voter_age_backend(dob)
    clean_id = sanitize_national_id_backend(national_id)
    # Check duplicate national ID
    existing = db.query(Voter).filter(Voter.national_id == clean_id).first()
    if existing and force_save != "1":
        doc_name = "អត្តលេខ-ឯ.អ" if len(clean_id) == 8 else ("លេខអត្តសញ្ញាណប័ណ្ណ" if len(clean_id) == 9 else "ឯកសារបញ្ជាក់អត្តសញ្ញាណ")
        raise HTTPException(
            status_code=400,
            detail=f"{doc_name} '{clean_id}' ត្រូវបានចុះឈ្មោះរួចហើយសម្រាប់ឈ្មោះ {existing.name_kh}"
        )

    # Get station to determine station code & next list_no
    station = db.query(PollingStation).filter(PollingStation.id == station_id).first()
    if not station:
        raise HTTPException(status_code=400, detail="ការិយាល័យបោះឆ្នោតមិនត្រឹមត្រូវ")

    # Determine next list_no in this station
    max_list_no = db.query(Voter).filter(Voter.station_id == station_id).count()
    next_list_no = max_list_no + 1
    voter_code = f"NP-{station.code}-{next_list_no:04d}"

    # Handle Photo
    photo_url = None
    if photo and photo.filename:
        photo_url = save_uploaded_photo(photo)
    elif photo_preset and photo_preset.strip():
        photo_url = photo_preset.strip()
    else:
        # Default avatar based on gender
        photo_url = "/static/images/avatars/female_1.jpg" if gender.strip() == "ស្រី" else "/static/images/avatars/male_1.jpg"

    now_ict = get_cambodia_now()
    new_voter = Voter(
        voter_code=voter_code,
        list_no=next_list_no,
        national_id=clean_id,
        name_kh=name_kh.strip(),
        name_en=name_en.strip().upper(),
        gender=gender.strip(),
        dob=dob.strip(),
        address=address.strip(),
        village_id=village_id,
        station_id=station_id,
        status="active",
        reg_type=reg_type.strip() if reg_type else "new",
        reg_year=reg_year if reg_year else 2026,
        reg_reason=reg_reason.strip() if reg_reason else None,
        photo_url=photo_url,
        has_voted=False,
        notes=notes.strip(),
        created_at=now_ict,
        updated_at=now_ict
    )
    db.add(new_voter)
    db.commit()
    db.refresh(new_voter)

    log_activity(
        db, current_user, "CREATE_VOTER",
        f"បានចុះឈ្មោះអ្នកបោះឆ្នោត ({new_voter.reg_type_badge['text']})៖ '{new_voter.name_kh}' (កូដ: {new_voter.voter_code} | អត្តសញ្ញាណប័ណ្ណ: {new_voter.national_id})",
        "voter", str(new_voter.id), "success", request=request
    )

    return JSONResponse({
        "success": True,
        "message": f"បានចុះឈ្មោះអ្នកបោះឆ្នោត '{new_voter.name_kh}' ដោយជោគជ័យ (កូដ: {new_voter.voter_code})",
        "voter_id": new_voter.id,
        "photo_url": new_voter.photo_display
    })

@router.get("/verify/{voter_code}", response_class=HTMLResponse)
def verify_voter_public_page(voter_code: str, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    clean_code = voter_code.strip()
    
    # Try finding by voter_code, national_id, or numeric id
    voter = db.query(Voter).filter(
        or_(
            Voter.voter_code == clean_code,
            Voter.national_id == clean_code
        )
    ).first()
    
    if not voter and clean_code.isdigit():
        voter = db.query(Voter).filter(Voter.id == int(clean_code)).first()

    return templates.TemplateResponse(request=request, name="voters/verify.html", context={
        "current_user": current_user,
        "voter": voter,
        "search_code": clean_code
    })

@router.get("/api/voters/lookup-qr")
def lookup_qr_code(code: str = Query(...), db: Session = Depends(get_db)):
    clean_code = code.strip()
    if "/" in clean_code:
        clean_code = clean_code.rstrip("/").split("/")[-1]

    voter = (
        db.query(Voter)
        .filter(
            or_(
                Voter.voter_code == clean_code,
                Voter.national_id == clean_code
            )
        )
        .first()
    )
    if not voter and clean_code.isdigit():
        voter = db.query(Voter).filter(Voter.id == int(clean_code)).first()

    if not voter:
        return JSONResponse({"found": False, "message": "រកមិនឃើញទិន្នន័យអ្នកបោះឆ្នោតតាមកូដនេះឡើយ"}, status_code=404)

    return JSONResponse({
        "found": True,
        "voter": {
            "id": voter.id,
            "voter_code": voter.voter_code,
            "list_no": voter.list_no,
            "national_id": voter.national_id,
            "name_kh": voter.name_kh,
            "name_en": voter.name_en,
            "gender": voter.gender,
            "dob": voter.dob,
            "photo_url": voter.photo_display,
            "village_name": voter.village.name_kh if voter.village else "",
            "station_code": voter.station.code if voter.station else "",
            "station_name": voter.station.name if voter.station else "",
            "station_location": voter.station.location if voter.station else "",
            "status": voter.status,
            "has_voted": voter.has_voted,
            "voted_at": voter.voted_at.strftime("%Y-%m-%d %H:%M:%S") if voter.voted_at else None
        }
    })

@router.get("/api/voters/{voter_id}")
def get_voter_detail(voter_id: int, db: Session = Depends(get_db)):
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="រកមិនឃើញអ្នកបោះឆ្នោតនេះឡើយ")
    return {
        "id": voter.id,
        "voter_code": voter.voter_code,
        "list_no": voter.list_no,
        "national_id": voter.national_id,
        "name_kh": voter.name_kh,
        "name_en": voter.name_en,
        "gender": voter.gender,
        "dob": voter.dob,
        "photo_url": voter.photo_display,
        "address": voter.address or "",
        "village_id": voter.village_id,
        "village_name": voter.village.name_kh if voter.village else "",
        "station_id": voter.station_id,
        "station_code": voter.station.code if voter.station else "",
        "station_name": voter.station.name if voter.station else "",
        "station_location": voter.station.location if voter.station else "",
        "status": voter.status,
        "reg_type": voter.reg_type or "new",
        "reg_year": voter.reg_year or 2026,
        "reg_reason": voter.reg_reason or "",
        "reg_type_badge": voter.reg_type_badge,
        "has_voted": voter.has_voted,
        "voted_at": voter.voted_at.strftime("%Y-%m-%d %H:%M:%S") if voter.voted_at else None,
        "notes": voter.notes or ""
    }

@router.post("/api/voters/{voter_id}/photo")
def upload_voter_photo(
    voter_id: int,
    photo_preset: str = Form(None),
    photo: UploadFile = File(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role not in ["admin", "officer"]:
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិបញ្ចូលរូបថត")

    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="រកមិនឃើញអ្នកបោះឆ្នោត")

    if photo and photo.filename:
        voter.photo_url = save_uploaded_photo(photo)
    elif photo_preset and photo_preset.strip():
        voter.photo_url = photo_preset.strip()
    else:
        raise HTTPException(status_code=400, detail="សូមជ្រើសរើសរូបថត")

    db.commit()
    log_activity(
        db, current_user, "UPDATE_PHOTO",
        f"បានផ្លាស់ប្តូររូបថតសម្រាប់ '{voter.name_kh}' (កូដ: {voter.voter_code})",
        "voter", str(voter.id), "info", request=request
    )

    return JSONResponse({
        "success": True,
        "message": f"បានផ្លាស់ប្តូររូបថតសម្រាប់ '{voter.name_kh}' រួចរាល់",
        "photo_url": voter.photo_display
    })

@router.post("/api/voters/{voter_id}/edit")
def update_voter(
    voter_id: int,
    name_kh: str = Form(...),
    name_en: str = Form(...),
    gender: str = Form(...),
    dob: str = Form(...),
    national_id: str = Form(...),
    village_id: int = Form(...),
    station_id: int = Form(...),
    status: str = Form("active"),
    reg_type: str = Form("new"),
    reg_year: int = Form(2026),
    reg_reason: str = Form(""),
    address: str = Form(""),
    notes: str = Form(""),
    force_save: str = Form("0"),
    photo_preset: str = Form(None),
    photo: UploadFile = File(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role not in ["admin", "officer"]:
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិកែប្រែទិន្នន័យ (Permission denied)")

    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="រកមិនឃើញអ្នកបោះឆ្នោតនេះឡើយ")

    validate_voter_age_backend(dob)
    clean_id = sanitize_national_id_backend(national_id)
    # Check duplicate ID
    duplicate = db.query(Voter).filter(Voter.national_id == clean_id, Voter.id != voter_id).first()
    if duplicate and force_save != "1":
        doc_name = "អត្តលេខ-ឯ.អ" if len(clean_id) == 8 else ("លេខអត្តសញ្ញាណប័ណ្ណ" if len(clean_id) == 9 else "ឯកសារបញ្ជាក់អត្តសញ្ញាណ")
        raise HTTPException(
            status_code=400,
            detail=f"{doc_name} '{clean_id}' ត្រូវបានប្រើប្រាស់ដោយឈ្មោះ {duplicate.name_kh} រួចហើយ"
        )

    # If new photo uploaded or preset selected
    if photo and photo.filename:
        voter.photo_url = save_uploaded_photo(photo)
    elif photo_preset and photo_preset.strip():
        voter.photo_url = photo_preset.strip()

    voter.name_kh = name_kh.strip()
    voter.name_en = name_en.strip().upper()
    voter.gender = gender.strip()
    voter.dob = dob.strip()
    voter.national_id = clean_id
    voter.village_id = village_id
    voter.station_id = station_id
    voter.status = status.strip()
    voter.reg_type = reg_type.strip() if reg_type else "new"
    voter.reg_year = reg_year if reg_year else 2026
    voter.reg_reason = reg_reason.strip() if reg_reason else None
    voter.address = address.strip()
    voter.notes = notes.strip()
    voter.updated_at = get_cambodia_now()

    db.commit()
    log_activity(
        db, current_user, "UPDATE_VOTER",
        f"បានកែប្រែទិន្នន័យអ្នកបោះឆ្នោត៖ '{voter.name_kh}' (កូដ: {voter.voter_code})",
        "voter", str(voter.id), "info", request=request
    )

    return JSONResponse({
        "success": True,
        "message": f"បានកែប្រែទិន្នន័យអ្នកបោះឆ្នោត '{voter.name_kh}' ដោយជោគជ័យ",
        "photo_url": voter.photo_display
    })

@router.post("/api/voters/{voter_id}/delete")
def delete_voter(voter_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="មានតែ Admin ប៉ុណ្ណោះដែលអាចលុបទិន្នន័យបាន")

    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="រកមិនឃើញអ្នកបោះឆ្នោត")

    v_name = voter.name_kh
    v_code = voter.voter_code
    db.delete(voter)
    db.commit()

    log_activity(
        db, current_user, "DELETE_VOTER",
        f"បានលុបអ្នកបោះឆ្នោត៖ '{v_name}' (កូដ: {v_code})",
        "voter", str(voter_id), "danger", request=request
    )

    return JSONResponse({"success": True, "message": f"បានលុបអ្នកបោះឆ្នោត '{v_name}' រួចរាល់"})

@router.post("/api/voters/{voter_id}/checkin")
def toggle_checkin(voter_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role not in ["admin", "officer"]:
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិកត់ត្រាវត្តមាន")

    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="រកមិនឃើញអ្នកបោះឆ្នោត")

    if voter.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"មិនអាច Check-in បានទេ ព្រោះស្ថានភាពអ្នកបោះឆ្នោតគឺ: '{voter.status}'"
        )

    # If officer, check if station matches
    if current_user.role == "officer" and current_user.station_id and voter.station_id != current_user.station_id:
        raise HTTPException(
            status_code=403,
            detail=f"អ្នកបោះឆ្នោតនេះស្ថិតនៅការិយាល័យ {voter.station.code} មិនមែនការិយាល័យរបស់លោកអ្នកឡើយ"
        )

    # Toggle status
    voter.has_voted = not voter.has_voted
    if voter.has_voted:
        voter.voted_at = get_cambodia_now()
        voter.voted_by_user_id = current_user.id
        msg = f"បាន Check-in វត្តមានបោះឆ្នោតសម្រាប់ '{voter.name_kh}' រួចរាល់"
        action_name = "CHECKIN"
        action_type = "success"
    else:
        voter.voted_at = None
        voter.voted_by_user_id = None
        msg = f"បានលុបចោល Check-in សម្រាប់ '{voter.name_kh}'"
        action_name = "UNCHECKIN"
        action_type = "warning"

    db.commit()

    log_activity(
        db, current_user, action_name,
        f"{msg} (កូដ: {voter.voter_code})",
        "voter", str(voter.id), action_type, request=request
    )

    return JSONResponse({
        "success": True,
        "has_voted": voter.has_voted,
        "voted_at": voter.voted_at.strftime("%H:%M:%S") if voter.voted_at else None,
        "message": msg
    })

@router.get("/voters/{voter_id}/card", response_class=HTMLResponse)
def voter_card_view(voter_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="រកមិនឃើញអ្នកបោះឆ្នោត")

    return templates.TemplateResponse(request=request, name="voters/card.html", context={
        "current_user": current_user,
        "voter": voter
    })

@router.post("/api/voters/ocr-id-card")
async def ocr_khmer_id_card(
    request: Request,
    image: UploadFile = File(None),
    image_base64: str = Form(None),
    client_text: str = Form(None),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="សូមចូលប្រើប្រព័ន្ធជាមុនសិន")

    img_bytes = None
    if image and image.filename:
        try:
            img_bytes = await image.read()
        except Exception:
            pass
    elif image_base64 and image_base64.strip():
        try:
            raw_b64 = image_base64.strip()
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            print(f"Base64 decode note: {e}")

    # Extract portrait face photo
    portrait_url = None
    if img_bytes:
        portrait_url = extract_id_card_face_portrait(img_bytes, subfolder="voters")

    # Parse text
    parsed = parse_khmer_id_text(client_text or "")
    national_id = parsed.get("national_id", "")
    name_kh = parsed.get("name_kh", "")
    name_en = parsed.get("name_en", "")
    gender = parsed.get("gender", "ប្រុស")
    dob = parsed.get("dob", "1995-05-15")
    address = parsed.get("address", "")

    # Duplicate ID check
    is_duplicate = False
    duplicate_name = ""
    if national_id:
        existing = db.query(Voter).filter(Voter.national_id == national_id).first()
        if existing:
            is_duplicate = True
            duplicate_name = existing.name_kh

    # Age calculation
    age = 0
    is_eligible_18 = True
    if dob:
        try:
            birth_year = int(dob[:4])
            current_year = datetime.date.today().year
            age = current_year - birth_year
            is_eligible_18 = (age >= 18)
        except Exception:
            pass

    return JSONResponse({
        "success": True,
        "data": {
            "national_id": national_id,
            "name_kh": name_kh,
            "name_en": name_en,
            "gender": gender,
            "dob": dob,
            "photo_url": portrait_url,
            "address": address,
            "is_duplicate": is_duplicate,
            "duplicate_name": duplicate_name,
            "age": age,
            "is_eligible_18": is_eligible_18
        }
    })

from app.pdf_importer import preview_pdf_import, execute_pdf_import

@router.post("/api/voters/import-pdf/preview")
async def api_preview_voter_pdf(
    pdf_file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Parses an uploaded NEC official voter list PDF and returns a structured preview.
    """
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role not in ["admin", "officer"]:
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិនាំចូលទិន្នន័យឡើយ (Permission denied)")

    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="សូមជ្រើសរើសឯកសារជាទម្រង់ PDF តែប៉ុណ្ណោះ")

    content = await pdf_file.read()
    if not content:
        raise HTTPException(status_code=400, detail="ឯកសារ PDF ទទេ")

    try:
        preview_data = preview_pdf_import(content, pdf_file.filename, db)
        return JSONResponse(preview_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"បរាជ័យក្នុងការអានឯកសារ PDF៖ {str(e)}")

@router.post("/api/voters/import-pdf/confirm")
async def api_confirm_voter_pdf_import(
    pdf_file: UploadFile = File(...),
    station_id: int = Form(...),
    village_id: int = Form(...),
    update_existing: bool = Form(True),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Executes the batch insertion/update of all voters from the confirmed PDF file.
    """
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role not in ["admin", "officer"]:
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិនាំចូលទិន្នន័យឡើយ (Permission denied)")

    content = await pdf_file.read()
    if not content:
        raise HTTPException(status_code=400, detail="ឯកសារ PDF ទទេ")

    try:
        result = execute_pdf_import(
            file_bytes=content,
            filename=pdf_file.filename,
            station_id=station_id,
            village_id=village_id,
            update_existing=update_existing,
            user_id=current_user.id,
            db=db
        )
        
        # Log to audit trail
        log_activity(
            db=db,
            user=current_user,
            action="IMPORT_PDF_VOTERS",
            description=f"បាននាំចូលបញ្ជីបោះឆ្នោតផ្លូវការ ២០២៥ ចំនួន {result['inserted']} នាក់ថ្មី (អាប់ដេត {result['updated']} នាក់) ពីឯកសារ '{pdf_file.filename}' សម្រាប់ការិយាល័យ {result['station_name']}",
            target_type="voter_batch",
            target_id=str(station_id),
            action_type="info",
            request=request
        )

        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"បរាជ័យក្នុងការរក្សាទុកទិន្នន័យ៖ {str(e)}")

