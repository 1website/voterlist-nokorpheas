import os
import io
import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.database import get_db
from app.models import Village, PollingStation, Voter, User
from app.auth import get_current_user_optional
from app.timezone_utils import get_cambodia_now, get_cambodia_today, get_cambodia_today_str

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

@router.get("/reports", response_class=HTMLResponse)
def reports_hub(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    # Demographic stats
    voters = db.query(Voter).filter(Voter.status == "active").all()
    total_active = len(voters)
    total_voted = len([v for v in voters if v.has_voted])
    male_count = len([v for v in voters if v.gender == "ប្រុស"])
    female_count = len([v for v in voters if v.gender == "ស្រី"])
    male_voted = len([v for v in voters if v.gender == "ប្រុស" and v.has_voted])
    female_voted = len([v for v in voters if v.gender == "ស្រី" and v.has_voted])

    # Age group calculation
    current_year = get_cambodia_now().year
    age_groups = {"18-30": 0, "31-45": 0, "46-60": 0, "60+": 0}
    for v in voters:
        try:
            birth_year = int(v.dob[:4])
            age = current_year - birth_year
            if age <= 30:
                age_groups["18-30"] += 1
            elif age <= 45:
                age_groups["31-45"] += 1
            elif age <= 60:
                age_groups["46-60"] += 1
            else:
                age_groups["60+"] += 1
        except Exception:
            pass

    # Daily Registration Trend (Last 10 Days)
    daily_trends_raw = (
        db.query(
            func.date(Voter.created_at).label("reg_date"),
            func.count(Voter.id).label("total"),
            func.sum(case((Voter.gender == "ប្រុស", 1), else_=0)).label("male"),
            func.sum(case((Voter.gender == "ស្រី", 1), else_=0)).label("female")
        )
        .group_by(func.date(Voter.created_at))
        .order_by(func.date(Voter.created_at).desc())
        .limit(10)
        .all()
    )

    daily_trends = [
        {
            "date": str(row.reg_date),
            "total": row.total,
            "male": row.male or 0,
            "female": row.female or 0
        }
        for row in daily_trends_raw if row.reg_date
    ]

    today_str = get_cambodia_today_str()

    return templates.TemplateResponse(request=request, name="reports/index.html", context={
        "current_user": current_user,
        "villages": villages,
        "stations": stations,
        "total_active": total_active,
        "total_voted": total_voted,
        "male_count": male_count,
        "female_count": female_count,
        "male_voted": male_voted,
        "female_voted": female_voted,
        "age_groups": age_groups,
        "daily_trends": daily_trends,
        "today_str": today_str
    })

@router.get("/reports/daily", response_class=HTMLResponse)
def daily_registration_report(
    request: Request,
    date: str = Query("", description="Selected date YYYY-MM-DD"),
    village_id: str = Query("", description="Village ID filter"),
    station_id: str = Query("", description="Station ID filter"),
    gender: str = Query("", description="Gender filter"),
    q: str = Query("", description="Search query"),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    today_str = get_cambodia_today_str()

    # If date is not provided, pick today if it has records, else latest registration date from DB or today
    if not date or not date.strip():
        today_count = db.query(Voter).filter(func.date(Voter.created_at) == today_str).count()
        if today_count > 0:
            date = today_str
        else:
            latest_row = db.query(func.date(Voter.created_at)).order_by(Voter.created_at.desc()).first()
            date = str(latest_row[0]) if latest_row and latest_row[0] else today_str
    else:
        date = date.strip()

    query = db.query(Voter).filter(func.date(Voter.created_at) == date)

    # Role restriction
    if current_user.role == "officer" and current_user.station_id:
        query = query.filter(Voter.station_id == current_user.station_id)
        station_id = str(current_user.station_id)
    elif current_user.role == "village_chief" and current_user.village_id:
        query = query.filter(Voter.village_id == current_user.village_id)
        village_id = str(current_user.village_id)

    if village_id and village_id.isdigit():
        query = query.filter(Voter.village_id == int(village_id))
    if station_id and station_id.isdigit():
        query = query.filter(Voter.station_id == int(station_id))
    if gender:
        query = query.filter(Voter.gender == gender)
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

    voters = query.order_by(Voter.created_at.desc(), Voter.list_no.asc()).all()

    total_day = len(voters)
    male_day = len([v for v in voters if v.gender == "ប្រុស"])
    female_day = len([v for v in voters if v.gender == "ស្រី"])

    # Recent 10 dates for quick switching
    recent_dates_raw = (
        db.query(
            func.date(Voter.created_at).label("reg_date"),
            func.count(Voter.id).label("total")
        )
        .group_by(func.date(Voter.created_at))
        .order_by(func.date(Voter.created_at).desc())
        .limit(10)
        .all()
    )

    recent_dates = []
    found_today = False
    for r in recent_dates_raw:
        if r.reg_date:
            r_str = str(r.reg_date)
            is_today = (r_str == today_str)
            if is_today:
                found_today = True
            recent_dates.append({
                "reg_date": r_str,
                "total": r.total,
                "is_today": is_today
            })

    if not found_today:
        recent_dates.insert(0, {
            "reg_date": today_str,
            "total": 0,
            "is_today": True
        })

    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    return templates.TemplateResponse(request=request, name="reports/daily.html", context={
        "current_user": current_user,
        "selected_date": date,
        "today_str": today_str,
        "voters": voters,
        "total_day": total_day,
        "male_day": male_day,
        "female_day": female_day,
        "recent_dates": recent_dates,
        "villages": villages,
        "stations": stations,
        "village_id": village_id,
        "station_id": station_id,
        "gender": gender,
        "q": q
    })

@router.get("/reports/daily/export/excel")
def export_daily_registrations_excel(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    village_id: str = Query("", description="Village ID"),
    station_id: str = Query("", description="Station ID"),
    db: Session = Depends(get_db)
):
    query = db.query(Voter).filter(func.date(Voter.created_at) == date)
    filter_desc = f"ប្រចាំថ្ងៃទី {date}"

    if village_id and village_id.isdigit():
        v_obj = db.query(Village).filter(Village.id == int(village_id)).first()
        if v_obj:
            query = query.filter(Voter.village_id == int(village_id))
            filter_desc += f" - ភូមិ {v_obj.name_kh}"
    if station_id and station_id.isdigit():
        s_obj = db.query(PollingStation).filter(PollingStation.id == int(station_id)).first()
        if s_obj:
            query = query.filter(Voter.station_id == int(station_id))
            filter_desc += f" - ការិយាល័យ {s_obj.code}"

    voters = query.order_by(Voter.created_at.desc(), Voter.list_no.asc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"ចុះឈ្មោះ_{date}"

    # Styles
    title_font = Font(name="Khmer OS Siemreap", size=14, bold=True, color="001F3F")
    subtitle_font = Font(name="Khmer OS Siemreap", size=11, bold=True, color="333333")
    header_font = Font(name="Khmer OS Siemreap", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Khmer OS Siemreap", size=10)
    
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    sub_header_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E0'),
        right=Side(style='thin', color='CBD5E0'),
        top=Side(style='thin', color='CBD5E0'),
        bottom=Side(style='thin', color='CBD5E0')
    )

    ws.merge_cells("A1:K1")
    ws["A1"] = "ព្រះរាជាណាចក្រកម្ពុជា ជាតិ សាសនា ព្រះមហាក្សត្រ"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:K2")
    ws["A2"] = f"របាយការណ៍អ្នកចុះឈ្មោះបោះឆ្នោតប្រចាំថ្ងៃ ({filter_desc}) - រដ្ឋបាលឃុំនគរភាស"
    ws["A2"].font = subtitle_font
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:K3")
    now_str = get_cambodia_now().strftime("%d-%m-%Y %H:%M")
    ws["A3"] = f"កាលបរិច្ឆេទចេញរបាយការណ៍៖ {now_str} | សរុបចុះឈ្មោះក្នុងថ្ងៃនេះ៖ {len(voters)} នាក់"
    ws["A3"].font = Font(name="Khmer OS Siemreap", size=9, italic=True, color="666666")
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    headers = [
        "ល.រ", "ម៉ោងចុះឈ្មោះ", "កូដអ្នកបោះឆ្នោត", "លេខអត្តសញ្ញាណប័ណ្ណ",
        "គោត្តនាម-នាម", "អក្សរឡាតាំង", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត",
        "ភូមិ", "ការិយាល័យបោះឆ្នោត", "កំណត់សម្គាល់"
    ]

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    row_num = 6
    for idx, v in enumerate(voters, 1):
        time_str = v.created_at.strftime("%H:%M:%S") if v.created_at else ""
        ws.cell(row=row_num, column=1, value=idx).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=2, value=time_str).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=3, value=v.voter_code).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=4, value=v.national_id).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=5, value=v.name_kh).alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=6, value=v.name_en).alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=7, value=v.gender).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=8, value=v.dob).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=9, value=v.village.name_kh if v.village else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=10, value=f"{v.station.code} - {v.station.name}" if v.station else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=11, value=v.notes or "បានចុះឈ្មោះ").alignment = Alignment(horizontal="left")

        for c in range(1, 12):
            cell = ws.cell(row=row_num, column=c)
            cell.font = data_font
            cell.border = thin_border
            if row_num % 2 == 1:
                cell.fill = sub_header_fill
        row_num += 1

    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row < 5:
                continue
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Daily_Registrations_{date}_{get_cambodia_now().strftime('%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/reports/daily/print", response_class=HTMLResponse)
def print_daily_registrations(
    request: Request,
    date: str = Query(..., description="Date YYYY-MM-DD"),
    village_id: str = Query("", description="Village ID"),
    station_id: str = Query("", description="Station ID"),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    query = db.query(Voter).filter(func.date(Voter.created_at) == date)
    village = None
    station = None

    if village_id and village_id.isdigit():
        village = db.query(Village).filter(Village.id == int(village_id)).first()
        if village:
            query = query.filter(Voter.village_id == int(village_id))

    if station_id and station_id.isdigit():
        station = db.query(PollingStation).filter(PollingStation.id == int(station_id)).first()
        if station:
            query = query.filter(Voter.station_id == int(station_id))

    voters = query.order_by(Voter.created_at.desc(), Voter.list_no.asc()).all()

    return templates.TemplateResponse(request=request, name="reports/daily_print.html", context={
        "current_user": current_user,
        "selected_date": date,
        "voters": voters,
        "village": village,
        "station": station,
        "now": get_cambodia_now()
    })

@router.get("/reports/export/excel")
def export_voter_list_excel(
    station_id: str = Query("", description="Station ID"),
    village_id: str = Query("", description="Village ID"),
    status_filter: str = Query("active", description="Status filter"),
    db: Session = Depends(get_db)
):
    query = db.query(Voter)

    filter_title = "ឃុំនគរភាសទាំងមូល"
    if station_id and station_id.isdigit():
        station = db.query(PollingStation).filter(PollingStation.id == int(station_id)).first()
        if station:
            query = query.filter(Voter.station_id == int(station_id))
            filter_title = f"{station.name} ({station.location})"

    if village_id and village_id.isdigit():
        village = db.query(Village).filter(Village.id == int(village_id)).first()
        if village:
            query = query.filter(Voter.village_id == int(village_id))
            filter_title = f"ភូមិ {village.name_kh} ({village.name_en})"

    if status_filter:
        query = query.filter(Voter.status == status_filter)

    voters = query.order_by(Voter.station_id.asc(), Voter.list_no.asc()).all()

    # Create OpenPyXL workbook
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

    # Title Rows
    ws.merge_cells("A1:J1")
    ws["A1"] = "ព្រះរាជាណាចក្រកម្ពុជា ជាតិ សាសនា ព្រះមហាក្សត្រ"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:J2")
    ws["A2"] = f"បញ្ជីឈ្មោះអ្នកចុះឈ្មោះបោះឆ្នោតផ្លូវការ - រដ្ឋបាលឃុំនគរភាស ({filter_title})"
    ws["A2"].font = subtitle_font
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:J3")
    now_str = get_cambodia_now().strftime("%d-%m-%Y %H:%M")
    ws["A3"] = f"កាលបរិច្ឆេទចេញរបាយការណ៍៖ {now_str} | ចំនួនសរុប៖ {len(voters)} នាក់"
    ws["A3"].font = Font(name="Khmer OS Siemreap", size=9, italic=True, color="666666")
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 22
    ws.row_dimensions[3].height = 18
    ws.row_dimensions[5].height = 26

    # Headers
    headers = [
        "ល.រ", "កូដអ្នកបោះឆ្នោត", "លេខរៀងបញ្ជី", "លេខអត្តសញ្ញាណប័ណ្ណ",
        "គោត្តនាម-នាម", "អក្សរឡាតាំង", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត",
        "ភូមិ", "ការិយាល័យបោះឆ្នោត", "ស្ថានភាពវត្តមាន", "ហត្ថលេខា / ស្នាមមេដៃ"
    ]

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Data Rows
    row_num = 6
    for idx, v in enumerate(voters, 1):
        voted_status = "បោះឆ្នោតរួច" if v.has_voted else "មិនទាន់បោះ"
        ws.cell(row=row_num, column=1, value=idx).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=2, value=v.voter_code).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=3, value=v.list_no).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=4, value=v.national_id).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=5, value=v.name_kh).alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=6, value=v.name_en).alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=7, value=v.gender).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=8, value=v.dob).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=9, value=v.village.name_kh if v.village else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=10, value=f"{v.station.code} - {v.station.name}" if v.station else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=11, value=voted_status).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=12, value="").alignment = Alignment(horizontal="center") # signature space

        for c in range(1, 13):
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
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
    ws.column_dimensions['L'].width = 20 # signature column

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Voter_List_Nokor_Pheas_{get_cambodia_now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/reports/official-list", response_class=HTMLResponse)
def official_printable_list(
    request: Request,
    station_id: str = Query("", description="Station ID"),
    village_id: str = Query("", description="Village ID"),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    query = db.query(Voter).filter(Voter.status == "active")
    station = None
    village = None

    if station_id and station_id.isdigit():
        station = db.query(PollingStation).filter(PollingStation.id == int(station_id)).first()
        if station:
            query = query.filter(Voter.station_id == int(station_id))

    if village_id and village_id.isdigit():
        village = db.query(Village).filter(Village.id == int(village_id)).first()
        if village:
            query = query.filter(Voter.village_id == int(village_id))

    voters = query.order_by(Voter.station_id.asc(), Voter.list_no.asc()).all()
    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    return templates.TemplateResponse(request=request, name="reports/official_list.html", context={
        "current_user": current_user,
        "voters": voters,
        "station": station,
        "village": village,
        "stations": stations,
        "villages": villages,
        "now": get_cambodia_now()
    })

@router.get("/reports/batch-cards", response_class=HTMLResponse)
def batch_printable_cards(
    request: Request,
    station_id: str = Query("", description="Station ID"),
    village_id: str = Query("", description="Village ID"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    query = db.query(Voter).filter(Voter.status == "active")
    if station_id and station_id.isdigit():
        query = query.filter(Voter.station_id == int(station_id))
    if village_id and village_id.isdigit():
        query = query.filter(Voter.village_id == int(village_id))

    voters = query.order_by(Voter.station_id.asc(), Voter.list_no.asc()).limit(limit).all()

    return templates.TemplateResponse(request=request, name="reports/batch_cards.html", context={
        "current_user": current_user,
        "voters": voters
    })

@router.get("/reports/annual-summary", response_class=HTMLResponse)
def annual_summary_report(
    request: Request,
    year: int = Query(2026, description="Registration year"),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    all_voters = db.query(Voter).all()
    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    # KPI stats
    legacy_count = len([v for v in all_voters if v.status == "active" and (v.reg_type == "legacy" or (v.reg_year and v.reg_year < year))])
    new_count = len([v for v in all_voters if v.status == "active" and v.reg_type == "new" and (v.reg_year == year or not v.reg_year)])
    transferred_count = len([v for v in all_voters if v.status == "active" and v.reg_type == "transferred" and v.reg_year == year])
    removed_count = len([v for v in all_voters if v.status in ["moved", "deceased", "suspended"]])
    total_active = legacy_count + new_count + transferred_count
    net_growth = (new_count + transferred_count) - removed_count

    # Village Breakdown
    village_stats = []
    for v in villages:
        v_voters = [vt for vt in all_voters if vt.village_id == v.id]
        v_legacy = len([vt for vt in v_voters if vt.status == "active" and (vt.reg_type == "legacy" or (vt.reg_year and vt.reg_year < year))])
        v_new = len([vt for vt in v_voters if vt.status == "active" and vt.reg_type == "new" and (vt.reg_year == year or not vt.reg_year)])
        v_transferred = len([vt for vt in v_voters if vt.status == "active" and vt.reg_type == "transferred" and vt.reg_year == year])
        v_removed = len([vt for vt in v_voters if vt.status in ["moved", "deceased", "suspended"]])
        v_active = v_legacy + v_new + v_transferred
        v_voted = len([vt for vt in v_voters if vt.status == "active" and vt.has_voted])
        v_rate = round((v_voted / v_active * 100), 1) if v_active > 0 else 0.0

        village_stats.append({
            "id": v.id,
            "code": v.code,
            "name_kh": v.name_kh,
            "legacy": v_legacy,
            "new": v_new,
            "transferred": v_transferred,
            "removed": v_removed,
            "active": v_active,
            "voted": v_voted,
            "turnout_rate": v_rate
        })

    # Polling Station Breakdown
    station_stats = []
    for s in stations:
        s_voters = [vt for vt in all_voters if vt.station_id == s.id]
        s_legacy = len([vt for vt in s_voters if vt.status == "active" and (vt.reg_type == "legacy" or (vt.reg_year and vt.reg_year < year))])
        s_new = len([vt for vt in s_voters if vt.status == "active" and vt.reg_type == "new" and (vt.reg_year == year or not vt.reg_year)])
        s_transferred = len([vt for vt in s_voters if vt.status == "active" and vt.reg_type == "transferred" and vt.reg_year == year])
        s_removed = len([vt for vt in s_voters if vt.status in ["moved", "deceased", "suspended"]])
        s_active = s_legacy + s_new + s_transferred
        s_voted = len([vt for vt in s_voters if vt.status == "active" and vt.has_voted])
        s_rate = round((s_voted / s_active * 100), 1) if s_active > 0 else 0.0

        station_stats.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "location": s.location,
            "village_name": s.village.name_kh if s.village else "",
            "legacy": s_legacy,
            "new": s_new,
            "transferred": s_transferred,
            "removed": s_removed,
            "active": s_active,
            "voted": s_voted,
            "turnout_rate": s_rate
        })

    return templates.TemplateResponse(request=request, name="reports/annual_summary.html", context={
        "current_user": current_user,
        "year": year,
        "legacy_count": legacy_count,
        "new_count": new_count,
        "transferred_count": transferred_count,
        "removed_count": removed_count,
        "total_active": total_active,
        "net_growth": net_growth,
        "village_stats": village_stats,
        "station_stats": station_stats
    })

@router.get("/reports/print/annual-summary", response_class=HTMLResponse)
def print_annual_summary(
    request: Request,
    year: int = Query(2026, description="Registration year"),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    all_voters = db.query(Voter).all()
    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    legacy_count = len([v for v in all_voters if v.status == "active" and (v.reg_type == "legacy" or (v.reg_year and v.reg_year < year))])
    new_count = len([v for v in all_voters if v.status == "active" and v.reg_type == "new" and (v.reg_year == year or not v.reg_year)])
    transferred_count = len([v for v in all_voters if v.status == "active" and v.reg_type == "transferred" and v.reg_year == year])
    removed_count = len([v for v in all_voters if v.status in ["moved", "deceased", "suspended"]])
    total_active = legacy_count + new_count + transferred_count
    net_growth = (new_count + transferred_count) - removed_count

    village_stats = []
    for v in villages:
        v_voters = [vt for vt in all_voters if vt.village_id == v.id]
        v_legacy = len([vt for vt in v_voters if vt.status == "active" and (vt.reg_type == "legacy" or (vt.reg_year and vt.reg_year < year))])
        v_new = len([vt for vt in v_voters if vt.status == "active" and vt.reg_type == "new" and (vt.reg_year == year or not vt.reg_year)])
        v_transferred = len([vt for vt in v_voters if vt.status == "active" and vt.reg_type == "transferred" and vt.reg_year == year])
        v_removed = len([vt for vt in v_voters if vt.status in ["moved", "deceased", "suspended"]])
        v_active = v_legacy + v_new + v_transferred
        village_stats.append({
            "code": v.code,
            "name_kh": v.name_kh,
            "legacy": v_legacy,
            "new": v_new,
            "transferred": v_transferred,
            "removed": v_removed,
            "active": v_active
        })

    station_stats = []
    for s in stations:
        s_voters = [vt for vt in all_voters if vt.station_id == s.id]
        s_legacy = len([vt for vt in s_voters if vt.status == "active" and (vt.reg_type == "legacy" or (vt.reg_year and vt.reg_year < year))])
        s_new = len([vt for vt in s_voters if vt.status == "active" and vt.reg_type == "new" and (vt.reg_year == year or not vt.reg_year)])
        s_transferred = len([vt for vt in s_voters if vt.status == "active" and vt.reg_type == "transferred" and vt.reg_year == year])
        s_removed = len([vt for vt in s_voters if vt.status in ["moved", "deceased", "suspended"]])
        s_active = s_legacy + s_new + s_transferred
        station_stats.append({
            "code": s.code,
            "name": s.name,
            "location": s.location,
            "village_name": s.village.name_kh if s.village else "",
            "legacy": s_legacy,
            "new": s_new,
            "transferred": s_transferred,
            "removed": s_removed,
            "active": s_active
        })

    return templates.TemplateResponse(request=request, name="reports/print_annual_summary.html", context={
        "current_user": current_user,
        "year": year,
        "legacy_count": legacy_count,
        "new_count": new_count,
        "transferred_count": transferred_count,
        "removed_count": removed_count,
        "total_active": total_active,
        "net_growth": net_growth,
        "village_stats": village_stats,
        "station_stats": station_stats,
        "now": get_cambodia_now()
    })

@router.get("/reports/export/annual-summary-excel")
def export_annual_summary_excel(
    year: int = Query(2026, description="Registration year"),
    db: Session = Depends(get_db)
):
    all_voters = db.query(Voter).all()
    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"របាយការណ៍បូកសរុប {year}"

    # Styles
    font_title = Font(name="Khmer OS Muol Light", size=14, bold=True, color="001A4E")
    font_subtitle = Font(name="Khmer OS Siemreap", size=11, bold=True, color="333333")
    font_header = Font(name="Khmer OS Siemreap", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Khmer OS Siemreap", size=10)
    font_bold = Font(name="Khmer OS Siemreap", size=10, bold=True)
    font_mono = Font(name="Consolas", size=10, bold=True)

    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_sub = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")
    fill_total = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Title
    ws.merge_cells("A1:G1")
    ws["A1"] = "ព្រះរាជាណាចក្រកម្ពុជា • ជាតិ សាសនា ព្រះមហាក្សត្រ"
    ws["A1"].font = font_subtitle
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:G2")
    ws["A2"] = f"របាយការណ៍បូកសរុបលទ្ធផលនៃការពិនិត្យបញ្ជីឈ្មោះ និងការចុះឈ្មោះបោះឆ្នោតប្រចាំឆ្នាំ {year}"
    ws["A2"].font = font_title
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:G3")
    ws["A3"] = "រដ្ឋបាលឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប"
    ws["A3"].font = font_subtitle
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    # Table 1: Summary KPI Block
    legacy_count = len([v for v in all_voters if v.status == "active" and (v.reg_type == "legacy" or (v.reg_year and v.reg_year < year))])
    new_count = len([v for v in all_voters if v.status == "active" and v.reg_type == "new" and (v.reg_year == year or not v.reg_year)])
    transferred_count = len([v for v in all_voters if v.status == "active" and v.reg_type == "transferred" and v.reg_year == year])
    removed_count = len([v for v in all_voters if v.status in ["moved", "deceased", "suspended"]])
    total_active = legacy_count + new_count + transferred_count

    ws.append([])
    ws.append(["១. តារាងសង្ខេបស្ថិតិរួមទូទាំងឃុំ", "", "", "", "", "", ""])
    ws.merge_cells("A5:G5")
    ws["A5"].font = font_subtitle

    headers_kpi = ["បញ្ជីចាស់ (A)", f"ចុះថ្មី {year} (B)", f"ផ្ទេរចូល {year} (C)", "លុបចេញ (មរណភាព/ផ្លាស់ចេញ) (D)", "បញ្ជីផ្លូវការចុងក្រោយ (A+B+C-D)", "កំណើនសុទ្ធ (B+C-D)", "អត្រាកំណើន (%)"]
    ws.append(headers_kpi)
    for col_idx in range(1, 8):
        cell = ws.cell(row=6, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    growth_rate = round(((new_count + transferred_count) / legacy_count * 100), 2) if legacy_count > 0 else 0.0
    kpi_row = [legacy_count, new_count, transferred_count, removed_count, total_active, (new_count + transferred_count - removed_count), f"+{growth_rate}%"]
    ws.append(kpi_row)
    for col_idx in range(1, 8):
        cell = ws.cell(row=7, column=col_idx)
        cell.font = font_mono
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.fill = fill_total
        cell.border = thin_border

    # Table 2: 10 Villages Breakdown
    ws.append([])
    ws.append(["២. ស្ថិតិបំបែកតាមភូមិទាំង ១០", "", "", "", "", "", ""])
    ws["A9"].font = font_subtitle

    v_headers = ["ល.រ", "កូដភូមិ", "ឈ្មោះភូមិ", "បញ្ជីចាស់", f"ចុះថ្មី {year}", "ផ្ទេរចូល", "លុបចេញ", "បញ្ជីផ្លូវការចុងក្រោយ"]
    ws.append(v_headers)
    for col_idx in range(1, 9):
        cell = ws.cell(row=10, column=col_idx)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    curr_row = 11
    for idx, v in enumerate(villages, 1):
        v_voters = [vt for vt in all_voters if vt.village_id == v.id]
        v_leg = len([vt for vt in v_voters if vt.status == "active" and (vt.reg_type == "legacy" or (vt.reg_year and vt.reg_year < year))])
        v_nw = len([vt for vt in v_voters if vt.status == "active" and vt.reg_type == "new" and (vt.reg_year == year or not vt.reg_year)])
        v_tr = len([vt for vt in v_voters if vt.status == "active" and vt.reg_type == "transferred" and vt.reg_year == year])
        v_rm = len([vt for vt in v_voters if vt.status in ["moved", "deceased", "suspended"]])
        v_tot = v_leg + v_nw + v_tr

        row_data = [idx, v.code, v.name_kh, v_leg, v_nw, v_tr, v_rm, v_tot]
        ws.append(row_data)
        for col_idx in range(1, 9):
            c = ws.cell(row=curr_row, column=col_idx)
            c.font = font_mono if col_idx in [1, 2, 4, 5, 6, 7, 8] else font_data
            c.alignment = Alignment(horizontal="center" if col_idx in [1, 2, 4, 5, 6, 7, 8] else "left", vertical="center")
            c.border = thin_border
        curr_row += 1

    # Total row for villages
    ws.append(["", "សរុប", "១០ ភូមិ", legacy_count, new_count, transferred_count, removed_count, total_active])
    for col_idx in range(1, 9):
        c = ws.cell(row=curr_row, column=col_idx)
        c.font = font_bold
        c.fill = fill_sub
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    # Adjust widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Annual_Voter_Summary_Nokor_Pheas_{year}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
