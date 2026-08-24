import hashlib
import secrets
from typing import Optional
from fastapi import Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

SECRET_SALT = "nokor_pheas_voter_system_salt_2026"

def hash_password(password: str) -> str:
    return hashlib.sha256((password + SECRET_SALT).encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id") if hasattr(request, "session") else None
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="សូមចូលប្រើប្រាស់ប្រព័ន្ធជាមុនសិន (Please login first)"
        )
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="លោកអ្នកពុំមានសិទ្ធិគ្រប់គ្រងជា Admin ឡើយ"
        )
    return current_user

def require_admin_or_officer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["admin", "officer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="សិទ្ធិត្រូវបានកំណត់សម្រាប់តែ Admin ឬមន្ត្រីការិយាល័យប៉ុណ្ណោះ"
        )
    return current_user
