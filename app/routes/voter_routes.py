import os
import re
import shutil
import uuid
import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, Query, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc, func

from app.database import get_db
from app.models import User, Village, PollingStation, Voter
from app.auth import get_current_user_optional, get_current_user, require_admin, require_admin_or_officer
from app.schemas import VoterCreateSchema, VoterUpdateSchema
from app.audit import log_activity
from app.timezone_utils import get_cambodia_now, get_cambodia_today

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "voters")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitize_national_id_backend(raw_id: str) -> str:
    if not raw_id:
        raise HTTPException(status_code=400, detail="សូមបញ្ចូលលេខអត្តសញ្ញាណប័ណ្ណ ឬឯកសារបញ្ជាក់អត្តសញ្ញាណ")
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
    if len(clean) not in [7, 9]:
        raise HTTPException(
            status_code=400,
            detail=f"លេខឯកសារមិនត្រឹមត្រូវ ({len(clean)} ខ្ទង់)៖ ប្រព័ន្ធអនុញ្ញាតលេខ ៩ ខ្ទង់ (អត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ) ឬ ៧ ខ្ទង់ (ឯកសារបញ្ជាក់អត្តសញ្ញាណ)"
        )
    return clean

def save_uploaded_photo(upload_file: UploadFile) -> str:
    if not upload_file or not upload_file.filename:
        return None
    ext = os.path.splitext(upload_file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        ext = ".jpg"
    filename = f"voter_{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return f"/static/uploads/voters/{filename}"

@router.get("/voters", response_class=HTMLResponse)
def voter_list_page(
    request: Request,
    q: str = Query("", description="Search text"),
    village_id: str = Query("", description="Village filter"),
    station_id: str = Query("", description="Station filter"),
    status_filter: str = Query("", description="Status filter"),
    gender_filter: str = Query("", description="Gender filter"),
    voted_filter: str = Query("", description="Voted filter (all, voted, not_voted)"),
    date_created: str = Query("", description="Registration date filter YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    query = db.query(Voter)

    # Role-based restriction
    if current_user.role == "officer" and current_user.station_id:
        query = query.filter(Voter.station_id == current_user.station_id)
        station_id = str(current_user.station_id)
    elif current_user.role == "village_chief" and current_user.village_id:
        query = query.filter(Voter.village_id == current_user.village_id)
        village_id = str(current_user.village_id)

    # Keyword Search (Name Khmer, Name Latin, National ID, Voter Code)
    if q.strip():
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
    if village_id and village_id.isdigit():
        query = query.filter(Voter.village_id == int(village_id))

    # Polling station filter
    if station_id and station_id.isdigit():
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

    # Registration date filter
    if date_created and date_created.strip():
        query = query.filter(func.date(Voter.created_at) == date_created.strip())

    total_count = query.count()
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    # Order by station, list_no
    voters = (
        query.order_by(Voter.station_id.asc(), Voter.list_no.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    return templates.TemplateResponse(request=request, name="voters/list.html", context={
        "current_user": current_user,
        "voters": voters,
        "total_count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "q": q,
        "village_id": village_id,
        "station_id": station_id,
        "status_filter": status_filter,
        "gender_filter": gender_filter,
        "voted_filter": voted_filter,
        "date_created": date_created,
        "villages": villages,
        "stations": stations
    })

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
            "message": f"លេខអត្តសញ្ញាណប័ណ្ណ '{clean_id}' ត្រូវបានចុះឈ្មោះដោយឈ្មោះ '{existing.name_kh}' ({details}) រួចហើយ!",
            "voter": {
                "id": existing.id,
                "name_kh": existing.name_kh,
                "voter_code": existing.voter_code,
                "station_code": existing.station.code if existing.station else "",
                "station_name": existing.station.name if existing.station else ""
            }
        }
    return {"duplicate": False, "message": "លេខអត្តសញ្ញាណប័ណ្ណត្រឹមត្រូវ (អាចប្រើប្រាស់បាន)"}

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
    address: str = Form(""),
    notes: str = Form(""),
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
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"លេខអត្តសញ្ញាណប័ណ្ណ '{clean_id}' ត្រូវបានចុះឈ្មោះរួចហើយសម្រាប់ឈ្មោះ {existing.name_kh}"
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
        f"បានចុះឈ្មោះអ្នកបោះឆ្នោតថ្មី៖ '{new_voter.name_kh}' (កូដ: {new_voter.voter_code} | អត្តសញ្ញាណប័ណ្ណ: {new_voter.national_id})",
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
    address: str = Form(""),
    notes: str = Form(""),
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
    if duplicate:
        raise HTTPException(
            status_code=400,
            detail=f"លេខអត្តសញ្ញាណប័ណ្ណ '{clean_id}' ត្រូវបានប្រើប្រាស់ដោយឈ្មោះ {duplicate.name_kh} រួចហើយ"
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
