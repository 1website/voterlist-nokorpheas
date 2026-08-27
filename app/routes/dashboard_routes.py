import os
import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Village, PollingStation, Voter
from app.auth import get_current_user_optional, get_current_user

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

@router.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role == "viewer":
        return RedirectResponse(url="/reports", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role == "viewer":
        return RedirectResponse(url="/reports", status_code=302)

    # Calculate statistics based on user role
    villages = db.query(Village).order_by(Village.code).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()

    # Scope query
    voter_query = db.query(Voter).filter(Voter.status == "active")
    all_status_query = db.query(Voter)

    target_station = None
    target_village = None

    if user.role == "officer" and user.station_id:
        voter_query = voter_query.filter(Voter.station_id == user.station_id)
        all_status_query = all_status_query.filter(Voter.station_id == user.station_id)
        target_station = db.query(PollingStation).filter(PollingStation.id == user.station_id).first()
    elif user.role == "village_chief" and user.village_id:
        voter_query = voter_query.filter(Voter.village_id == user.village_id)
        all_status_query = all_status_query.filter(Voter.village_id == user.village_id)
        target_village = db.query(Village).filter(Village.id == user.village_id).first()

    total_active_voters = voter_query.count()
    total_voted = voter_query.filter(Voter.has_voted == True).count()
    total_not_voted = total_active_voters - total_voted
    turnout_pct = round((total_voted / total_active_voters * 100), 1) if total_active_voters > 0 else 0.0

    # Gender breakdown
    male_count = voter_query.filter(Voter.gender == "ប្រុស").count()
    female_count = voter_query.filter(Voter.gender == "ស្រី").count()
    male_voted = voter_query.filter(Voter.gender == "ប្រុស", Voter.has_voted == True).count()
    female_voted = voter_query.filter(Voter.gender == "ស្រី", Voter.has_voted == True).count()

    # Status counts
    active_count = all_status_query.filter(Voter.status == "active").count()
    moved_count = all_status_query.filter(Voter.status == "moved").count()
    deceased_count = all_status_query.filter(Voter.status == "deceased").count()
    suspended_count = all_status_query.filter(Voter.status == "suspended").count()

    # Recent check-ins
    recent_checkins = (
        db.query(Voter)
        .filter(Voter.has_voted == True)
        .order_by(Voter.voted_at.desc())
        .limit(10)
        .all()
    )
    if user.role == "officer" and user.station_id:
        recent_checkins = [v for v in recent_checkins if v.station_id == user.station_id]
    elif user.role == "village_chief" and user.village_id:
        recent_checkins = [v for v in recent_checkins if v.village_id == user.village_id]

    # Station turnout list (for Admin)
    station_stats = []
    for s in stations:
        st_voters = [v for v in s.voters if v.status == "active"]
        st_voted = len([v for v in st_voters if v.has_voted])
        st_total = len(st_voters)
        st_pct = round((st_voted / st_total * 100), 1) if st_total > 0 else 0.0
        station_stats.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "location": s.location,
            "capacity": s.capacity,
            "registered": st_total,
            "voted": st_voted,
            "turnout_pct": st_pct,
            "officer_name": s.officer_name,
            "village_name": s.village.name_kh if s.village else ""
        })

    # Village turnout list (for Admin/Village Chief)
    village_stats = []
    for v in villages:
        v_voters = [vt for vt in v.voters if vt.status == "active"]
        v_voted = len([vt for vt in v_voters if vt.has_voted])
        v_total = len(v_voters)
        v_pct = round((v_voted / v_total * 100), 1) if v_total > 0 else 0.0
        village_stats.append({
            "id": v.id,
            "code": v.code,
            "name_kh": v.name_kh,
            "name_en": v.name_en,
            "chief_name": v.chief_name,
            "households": v.total_households,
            "registered": v_total,
            "voted": v_voted,
            "turnout_pct": v_pct
        })

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "current_user": user,
        "total_active_voters": total_active_voters,
        "total_voted": total_voted,
        "total_not_voted": total_not_voted,
        "turnout_pct": turnout_pct,
        "male_count": male_count,
        "female_count": female_count,
        "male_voted": male_voted,
        "female_voted": female_voted,
        "active_count": active_count,
        "moved_count": moved_count,
        "deceased_count": deceased_count,
        "suspended_count": suspended_count,
        "recent_checkins": recent_checkins,
        "station_stats": station_stats,
        "village_stats": village_stats,
        "target_station": target_station,
        "target_village": target_village,
        "total_villages": len(villages),
        "total_stations": len(stations)
    })

@router.get("/api/dashboard/stats")
def api_dashboard_stats(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    
    # Base query
    voter_query = db.query(Voter).filter(Voter.status == "active")
    if user and user.role == "officer" and user.station_id:
        voter_query = voter_query.filter(Voter.station_id == user.station_id)
    elif user and user.role == "village_chief" and user.village_id:
        voter_query = voter_query.filter(Voter.village_id == user.village_id)

    total_active = voter_query.count()
    total_voted = voter_query.filter(Voter.has_voted == True).count()
    turnout_pct = round((total_voted / total_active * 100), 1) if total_active > 0 else 0.0

    stations = db.query(PollingStation).order_by(PollingStation.code).all()
    station_labels = [s.code for s in stations]
    station_voted_data = []
    station_total_data = []
    for s in stations:
        s_act = [v for v in s.voters if v.status == "active"]
        s_vod = len([v for v in s_act if v.has_voted])
        station_voted_data.append(s_vod)
        station_total_data.append(len(s_act))

    villages = db.query(Village).order_by(Village.code).all()
    village_labels = [v.name_kh for v in villages]
    village_voted_data = []
    village_total_data = []
    for v in villages:
        v_act = [vt for vt in v.voters if vt.status == "active"]
        v_vod = len([vt for vt in v_act if vt.has_voted])
        village_voted_data.append(v_vod)
        village_total_data.append(len(v_act))

    return JSONResponse({
        "total_active": total_active,
        "total_voted": total_voted,
        "total_not_voted": total_active - total_voted,
        "turnout_pct": turnout_pct,
        "stations": {
            "labels": station_labels,
            "voted": station_voted_data,
            "total": station_total_data
        },
        "villages": {
            "labels": village_labels,
            "voted": village_voted_data,
            "total": village_total_data
        }
    })
