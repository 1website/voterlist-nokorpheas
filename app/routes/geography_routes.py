import os
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Village, PollingStation, Voter, User
from app.auth import get_current_user_optional, require_admin

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

# --- Villages ---
@router.get("/villages", response_class=HTMLResponse)
def list_villages(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    villages = db.query(Village).order_by(Village.code).all()
    return templates.TemplateResponse(request=request, name="villages/index.html", context={
        "current_user": current_user,
        "villages": villages
    })

@router.post("/api/villages")
def save_village(
    id: int = Form(0),
    code: str = Form(...),
    name_kh: str = Form(...),
    name_en: str = Form(...),
    chief_name: str = Form(""),
    chief_phone: str = Form(""),
    total_households: int = Form(0),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="មានតែ Admin ប៉ុណ្ណោះដែលអាចកែប្រែទិន្នន័យភូមិបាន")

    if id > 0:
        village = db.query(Village).filter(Village.id == id).first()
        if not village:
            raise HTTPException(status_code=404, detail="រកមិនឃើញភូមិនេះឡើយ")
        village.code = code.strip().upper()
        village.name_kh = name_kh.strip()
        village.name_en = name_en.strip()
        village.chief_name = chief_name.strip()
        village.chief_phone = chief_phone.strip()
        village.total_households = total_households
        msg = f"បានកែប្រែទិន្នន័យ '{village.name_kh}' រួចរាល់"
    else:
        # Check duplicate code
        existing = db.query(Village).filter(Village.code == code.strip().upper()).first()
        if existing:
            raise HTTPException(status_code=400, detail="កូដភូមិនេះមានរួចហើយ")
        village = Village(
            code=code.strip().upper(),
            name_kh=name_kh.strip(),
            name_en=name_en.strip(),
            chief_name=chief_name.strip(),
            chief_phone=chief_phone.strip(),
            total_households=total_households
        )
        db.add(village)
        msg = f"បានបង្កើត '{village.name_kh}' ជោគជ័យ"

    db.commit()
    return JSONResponse({"success": True, "message": msg})

@router.post("/api/villages/{village_id}/delete")
def delete_village(village_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="មានតែ Admin ប៉ុណ្ណោះដែលអាចលុបភូមិបាន")

    village = db.query(Village).filter(Village.id == village_id).first()
    if not village:
        raise HTTPException(status_code=404, detail="រកមិនឃើញភូមិ")

    if len(village.voters) > 0:
        raise HTTPException(status_code=400, detail="មិនអាចលុបភូមិដែលមានអ្នកបោះឆ្នោតបានទេ សូមផ្ទេរអ្នកបោះឆ្នោតជាមុនសិន")

    db.delete(village)
    db.commit()
    return JSONResponse({"success": True, "message": "បានលុបភូមិរួចរាល់"})


# --- Polling Stations ---
@router.get("/stations", response_class=HTMLResponse)
def list_stations(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    stations = db.query(PollingStation).order_by(PollingStation.code).all()
    villages = db.query(Village).order_by(Village.code).all()
    return templates.TemplateResponse(request=request, name="stations/index.html", context={
        "current_user": current_user,
        "stations": stations,
        "villages": villages
    })

@router.post("/api/stations")
def save_station(
    id: int = Form(0),
    code: str = Form(...),
    name: str = Form(...),
    location: str = Form(...),
    capacity: int = Form(600),
    village_id: int = Form(...),
    officer_name: str = Form(""),
    officer_phone: str = Form(""),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="មានតែ Admin ប៉ុណ្ណោះដែលអាចកែប្រែការិយាល័យបាន")

    if id > 0:
        station = db.query(PollingStation).filter(PollingStation.id == id).first()
        if not station:
            raise HTTPException(status_code=404, detail="រកមិនឃើញការិយាល័យនេះឡើយ")
        station.code = code.strip()
        station.name = name.strip()
        station.location = location.strip()
        station.capacity = capacity
        station.village_id = village_id
        station.officer_name = officer_name.strip()
        station.officer_phone = officer_phone.strip()
        msg = f"បានកែប្រែព័ត៌មាន '{station.name}' រួចរាល់"
    else:
        existing = db.query(PollingStation).filter(PollingStation.code == code.strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="កូដការិយាល័យនេះមានរួចហើយ")
        station = PollingStation(
            code=code.strip(),
            name=name.strip(),
            location=location.strip(),
            capacity=capacity,
            village_id=village_id,
            officer_name=officer_name.strip(),
            officer_phone=officer_phone.strip()
        )
        db.add(station)
        msg = f"បានបង្កើត '{station.name}' ជោគជ័យ"

    db.commit()
    return JSONResponse({"success": True, "message": msg})

@router.post("/api/stations/{station_id}/delete")
def delete_station(station_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="មានតែ Admin ប៉ុណ្ណោះដែលអាចលុបការិយាល័យបាន")

    station = db.query(PollingStation).filter(PollingStation.id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="រកមិនឃើញការិយាល័យ")

    if len(station.voters) > 0:
        raise HTTPException(status_code=400, detail="មិនអាចលុបការិយាល័យដែលមានអ្នកបោះឆ្នោតបានទេ សូមផ្ទេរអ្នកបោះឆ្នោតជាមុនសិន")

    db.delete(station)
    db.commit()
    return JSONResponse({"success": True, "message": "បានលុបការិយាល័យរួចរាល់"})
