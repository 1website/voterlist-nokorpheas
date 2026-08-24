import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PollingStation, Village, Voter
from app.auth import get_current_user_optional

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

@router.get("/checkin", response_class=HTMLResponse)
def checkin_kiosk(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    stations = db.query(PollingStation).order_by(PollingStation.code).all()
    villages = db.query(Village).order_by(Village.code).all()

    # Recent check-ins for the current view
    recent_query = db.query(Voter).filter(Voter.has_voted == True).order_by(Voter.voted_at.desc())
    if current_user.role == "officer" and current_user.station_id:
        recent_query = recent_query.filter(Voter.station_id == current_user.station_id)
    elif current_user.role == "village_chief" and current_user.village_id:
        recent_query = recent_query.filter(Voter.village_id == current_user.village_id)

    recent_checkins = recent_query.limit(15).all()

    return templates.TemplateResponse(request=request, name="checkin/index.html", context={
        "current_user": current_user,
        "stations": stations,
        "villages": villages,
        "recent_checkins": recent_checkins
    })
