import os
import sys
import webbrowser
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

# Set stdout UTF-8 encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app.database import engine, Base, SessionLocal
from app.seed_data import seed_database
from app.routes import (
    auth_routes,
    dashboard_routes,
    voter_routes,
    geography_routes,
    checkin_routes,
    report_routes,
    user_routes,
    system_routes
)

import time

# Initialize Database Schema & Seed Data with safe retry
def init_database_with_retry(max_retries=6, delay_sec=2):
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Initializing database (Attempt {attempt}/{max_retries})...")
            Base.metadata.create_all(bind=engine)
            from app.database import ensure_schema_migrations
            ensure_schema_migrations()
            
            db = SessionLocal()
            try:
                seed_database(db)
            finally:
                db.close()
            print("✅ Database schema and seed data initialized successfully!")
            return True
        except Exception as e:
            print(f"⚠️ Database init attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(delay_sec)
            else:
                print("❌ Warning: Database connection failed after all retries. Continuing startup...")
                return False

init_database_with_retry()

# Create FastAPI App
app = FastAPI(
    title="ប្រព័ន្ធគ្រប់គ្រងអ្នកចុះឈ្មោះបោះឆ្នោត - រដ្ឋបាលឃុំនគរភាស",
    description="Nokor Pheas Commune Voter Registration and Election Day Management System",
    version="1.0.0"
)

# Add Session Middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key="nokor_pheas_commune_election_secret_key_2026",
    session_cookie="nokor_pheas_session",
    max_age=86400 # 24 hours
)

# Mount Static Files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Application Routers
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(voter_routes.router)
app.include_router(geography_routes.router)
app.include_router(checkin_routes.router)
app.include_router(report_routes.router)
app.include_router(user_routes.router)
app.include_router(system_routes.router)

if __name__ == "__main__":
    port = 8000
    print("=" * 70)
    print(" 🇰🇭  ប្រព័ន្ធគ្រប់គ្រងអ្នកចុះឈ្មោះបោះឆ្នោត រដ្ឋបាលឃុំនគរភាស")
    print("     (១០ ភូមិ • ១៤ ការិយាល័យបោះឆ្នោត)")
    print(f"     🚀 Server Running at: http://localhost:{port}")
    print("     👑 Admin Login: user='admin' | pass='admin123'")
    print("=" * 70)
    
    # Auto-open browser on startup
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass

    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=False)
