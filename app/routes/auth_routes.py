from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.models import User, PollingStation, Village
from app.auth import hash_password, verify_password, get_current_user_optional
from app.audit import log_activity

router = APIRouter()

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    # Fetch sample accounts for quick-login demo buttons
    admin_user = db.query(User).filter(User.role == "admin").first()
    officer_sample = db.query(User).filter(User.role == "officer").first()
    chief_sample = db.query(User).filter(User.role == "village_chief").first()

    return templates.TemplateResponse(request=request, name="login.html", context={
        "admin_user": admin_user,
        "officer_sample": officer_sample,
        "chief_sample": chief_sample,
        "error": None
    })

@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        log_activity(db, None, "LOGIN_FAILED", f"ការចូលប្រើប្រាស់បរាជ័យសម្រាប់គណនី: '{username}'", "auth", action_type="danger", request=request)
        return templates.TemplateResponse(request=request, name="login.html", context={
            "error": "ឈ្មោះគណនី ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវឡើយ (Invalid username or password)",
            "username": username
        }, status_code=400)

    if not user.is_active:
        log_activity(db, user, "LOGIN_BLOCKED", f"គណនីត្រូវបានផ្អាកដំណើរការ: '{username}'", "auth", action_type="warning", request=request)
        return templates.TemplateResponse(request=request, name="login.html", context={
            "error": "គណនីនេះត្រូវបានផ្អាកដំណើរការ (Account is disabled)",
            "username": username
        }, status_code=400)

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["role"] = user.role
    request.session["full_name"] = user.full_name

    log_activity(db, user, "LOGIN", f"បានចូលប្រើប្រាស់ប្រព័ន្ធដោយជោគជ័យ ({user.full_name})", "auth", str(user.id), "success", request=request)

    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if current_user:
        log_activity(db, current_user, "LOGOUT", f"បានចាកចេញពីប្រព័ន្ធ ({current_user.full_name})", "auth", str(current_user.id), "info", request=request)
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@router.get("/switch-user/{username}")
def switch_user(username: str, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if user and user.is_active:
        request.session["user_id"] = user.id
        request.session["username"] = user.username
        request.session["role"] = user.role
        request.session["full_name"] = user.full_name
        log_activity(db, user, "SWITCH_USER", f"បានប្តូរទៅកាន់គណនី '{user.full_name}' ({user.role})", "auth", str(user.id), "info", request=request)
    return RedirectResponse(url="/dashboard", status_code=302)
