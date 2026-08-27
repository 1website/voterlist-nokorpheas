import os
import uuid
import shutil
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, PollingStation, Village, AuditLog
from app.auth import get_current_user_optional, hash_password, verify_password
from app.audit import log_activity

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

USER_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "users")
os.makedirs(USER_UPLOAD_DIR, exist_ok=True)

PRESET_AVATARS = [
    "/static/images/avatars/male_1.jpg",
    "/static/images/avatars/female_1.jpg",
    "/static/images/avatars/male_2.jpg",
    "/static/images/avatars/female_2.jpg",
    "/static/images/avatars/male_3.jpg",
    "/static/images/avatars/female_3.jpg",
    "/static/images/avatars/male_4.jpg",
]

from app.image_utils import process_and_encode_image

def save_user_avatar(upload_file: UploadFile) -> str:
    return process_and_encode_image(upload_file, subfolder="users", max_size=(300, 300), quality=85)

@router.get("/profile", response_class=HTMLResponse)
def user_profile_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    # Get recent activity logs of this user
    user_logs = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id
    ).order_by(AuditLog.created_at.desc()).limit(15).all()

    return templates.TemplateResponse(request=request, name="users/profile.html", context={
        "current_user": current_user,
        "preset_avatars": PRESET_AVATARS,
        "user_logs": user_logs
    })

@router.post("/api/profile/update")
async def update_user_profile(
    full_name: str = Form(...),
    phone: str = Form(""),
    photo_preset: str = Form(""),
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    photo: UploadFile = File(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_optional(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="សូមចូលប្រើប្រព័ន្ធជាមុនសិន")

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="រកមិនឃើញគណនី")

    # Update basic profile
    if full_name.strip():
        user.full_name = full_name.strip()
    user.phone = phone.strip()

    # Handle Photo (File upload or Preset)
    if photo and photo.filename:
        saved_path = save_user_avatar(photo)
        if saved_path:
            user.photo_url = saved_path
    elif photo_preset and photo_preset.strip():
        user.photo_url = photo_preset.strip()

    # Handle Password Change if requested
    password_changed = False
    if new_password.strip():
        if len(new_password.strip()) < 4:
            raise HTTPException(status_code=400, detail="ពាក្យសម្ងាត់ថ្មីត្រូវមានយ៉ាងហោចណាស់ ៤ តួអក្សរ")
        if new_password.strip() != confirm_password.strip():
            raise HTTPException(status_code=400, detail="ការបញ្ជាក់ពាក្យសម្ងាត់ថ្មីមិនត្រូវគ្នាទេ")
        
        # Verify current password
        if current_password.strip() and not verify_password(current_password.strip(), user.password_hash):
            raise HTTPException(status_code=400, detail="ពាក្យសម្ងាត់ចាស់មិនត្រឹមត្រូវទេ")

        user.password_hash = hash_password(new_password.strip())
        password_changed = True

    db.commit()
    db.refresh(user)

    # Log activity
    desc = f"បានកែប្រែព័ត៌មាន Profile ផ្ទាល់ខ្លួន"
    if password_changed:
        desc += " និងបានផ្លាស់ប្តូរពាក្យសម្ងាត់"
    log_activity(
        db,
        user=user,
        action="UPDATE_PROFILE",
        target_type="user",
        target_id=str(user.id),
        description=desc,
        action_type="success",
        request=request
    )

    return JSONResponse({
        "success": True,
        "message": "បានកែប្រែព័ត៌មាន Profile ជោគជ័យ!",
        "avatar_url": user.avatar_display,
        "full_name": user.full_name,
        "phone": user.phone
    })

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
        "villages": villages,
        "preset_avatars": PRESET_AVATARS
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
    photo_preset: str = Form(""),
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
        photo_url=photo_preset.strip() if photo_preset else None,
        is_active=True
    )
    db.add(new_user)
    db.commit()

    log_activity(
        db,
        user=current_user,
        action="CREATE_USER",
        target_type="user",
        target_id=str(new_user.id),
        description=f"បានបង្កើតគណនីថ្មី '{new_user.username}' ({new_user.full_name}) តួនាទី: {new_user.role}",
        action_type="success",
        request=request
    )

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

    status_str = "បើកដំណើរការ" if user.is_active else "ផ្អាកដំណើរការ"
    log_activity(
        db,
        user=current_user,
        action="TOGGLE_USER",
        target_type="user",
        target_id=str(user.id),
        description=f"បាន{status_str}គណនី '{user.username}'",
        action_type="warning" if not user.is_active else "info",
        request=request
    )

    return JSONResponse({
        "success": True,
        "is_active": user.is_active,
        "message": f"បាន{status_str}គណនីជោគជ័យ"
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

    log_activity(
        db,
        user=current_user,
        action="RESET_PASSWORD",
        target_type="user",
        target_id=str(user.id),
        description=f"Admin បានកំណត់ពាក្យសម្ងាត់ឡើងវិញសម្រាប់គណនី '{user.username}'",
        action_type="warning",
        request=request
    )

    return JSONResponse({"success": True, "message": f"បានប្តូរពាក្យសម្ងាត់សម្រាប់ '{user.username}' រួចរាល់"})
