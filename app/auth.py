import os
import hashlib
import secrets
from typing import Optional
from fastapi import Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

LEGACY_SALT = "nokor_pheas_voter_system_salt_2026"
SECRET_SALT = os.getenv("SECRET_SALT", LEGACY_SALT)

def hash_password(password: str, salt: Optional[str] = None) -> str:
    use_salt = salt if salt is not None else SECRET_SALT
    return hashlib.sha256((password + use_salt).encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # 1. Primary check with current configured SECRET_SALT
    if hash_password(plain_password, SECRET_SALT) == hashed_password:
        return True
    # 2. Fallback check with default legacy salt (in case SECRET_SALT was added after initial database seeding)
    if SECRET_SALT != LEGACY_SALT and hash_password(plain_password, LEGACY_SALT) == hashed_password:
        return True
    return False

# Session Idle Timeout (Default 15 minutes = 900 seconds)
SESSION_TIMEOUT_SECONDS = int(os.getenv("SESSION_TIMEOUT_SECONDS", "900"))

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    if not hasattr(request, "session"):
        return None
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    import time
    now = int(time.time())
    last_activity = request.session.get("last_activity")

    # Check idle timeout (clear session if exceeded)
    if last_activity and (now - last_activity > SESSION_TIMEOUT_SECONDS):
        request.session.clear()
        return None

    # Update last activity timestamp
    request.session["last_activity"] = now

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
