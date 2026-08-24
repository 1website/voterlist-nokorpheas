import os
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, PollingStation, Village
from app.auth import get_current_user_optional, hash_password

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

@router.get("/users", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="មានតែ Admin ប៉ុណ្ណោះដែលអាចមើលគណនីបាន")

    users = db.query(User).order_by(User.role.asc(), User.username.asc()).all()
    stations = db.query(PollingStation).order_by(PollingStation.code).all()
    villages = db.query(Village).order_by(Village.code).all()

    return templates.TemplateResponse(request=request, name="users/index.html", context={
        "current_user": current_user,
        "users": users,
        "stations": stations,
        "villages": villages
    })

@router.post("/api/users")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    station_id: int = Form(0),
    village_id: int = Form(0),
    phone: str = Form(""),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិបង្កើតគណនី")

    clean_user = username.strip().lower()
    existing = db.query(User).filter(User.username == clean_user).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"ឈ្មោះគណនី '{clean_user}' មានរួចហើយ")

    st_id = station_id if (role == "officer" and station_id > 0) else None
    vg_id = village_id if (role == "village_chief" and village_id > 0) else None

    new_user = User(
        username=clean_user,
        password_hash=hash_password(password.strip()),
        full_name=full_name.strip(),
        role=role,
        station_id=st_id,
        village_id=vg_id,
        phone=phone.strip(),
        is_active=True
    )
    db.add(new_user)
    db.commit()
    return JSONResponse({"success": True, "message": f"បានបង្កើតគណនី '{new_user.username}' ជោគជ័យ"})

@router.post("/api/users/{user_id}/toggle")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិ")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="មិនអាចផ្អាកគណនីផ្ទាល់ខ្លួនបានទេ")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="រកមិនឃើញគណនី")

    user.is_active = not user.is_active
    db.commit()
    return JSONResponse({
        "success": True,
        "is_active": user.is_active,
        "message": "បានផ្លាស់ប្តូរស្ថានភាពគណនីជោគជ័យ"
    })

@router.post("/api/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    new_password: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិ")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="រកមិនឃើញគណនី")

    user.password_hash = hash_password(new_password.strip())
    db.commit()
    return JSONResponse({"success": True, "message": f"បានប្តូរពាក្យសម្ងាត់សម្រាប់ '{user.username}' រួចរាល់"})
