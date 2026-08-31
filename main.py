import os
import sys
import webbrowser
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
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
    system_routes,
    birth_routes
)

import time

# Initialize Database Schema & Seed Data with safe retry
def init_database_with_retry(max_retries=6, delay_sec=2):
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Initializing database (Attempt {attempt}/{max_retries})...")
            import app.models
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

# Environment & Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "nokor_pheas_commune_election_secret_key_2026")
IS_PRODUCTION = os.getenv("ENVIRONMENT", "").lower() == "production" or bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or os.getenv("VERCEL"))

# Add Session Middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY,
    session_cookie="nokor_pheas_session",
    max_age=86400, # 24 hours
    https_only=IS_PRODUCTION,
    same_site="lax"
)

# Prevent stale HTML caching in client browsers
@app.middleware("http")
async def add_no_cache_headers_for_html(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount Static Files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Root endpoints for PWA & Browser Icons
@app.get("/manifest.json", include_in_schema=False)
async def get_manifest():
    return FileResponse(os.path.join(static_dir, "manifest.json"), media_type="application/manifest+json")

@app.get("/sw.js", include_in_schema=False)
async def get_service_worker():
    return FileResponse(os.path.join(static_dir, "sw.js"), media_type="application/javascript")

@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon():
    return FileResponse(os.path.join(static_dir, "icons", "favicon.ico"), media_type="image/x-icon")

from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse

# Include Application Routers
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(voter_routes.router)
app.include_router(geography_routes.router)
app.include_router(checkin_routes.router)
app.include_router(report_routes.router)
app.include_router(user_routes.router)
app.include_router(system_routes.router)
app.include_router(birth_routes.router)

@app.exception_handler(500)
@app.exception_handler(Exception)
async def custom_500_handler(request: Request, exc: Exception):
    import traceback
    error_type = type(exc).__name__
    error_detail = str(exc) or "Internal Server Error"
    tb = traceback.format_exc()
    print(f"❌ HTTP 500 [{error_type}] on {request.method} {request.url}: {error_detail}")
    print(tb)
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="km">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>មានបញ្ហាបច្ចេកទេស - Error 500</title>
        <style>
            body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
            .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 24px; padding: 36px 28px; max-width: 540px; width: 100%; text-align: center; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }}
            .icon {{ font-size: 52px; margin-bottom: 16px; }}
            h1 {{ color: #f8fafc; font-size: 20px; font-weight: bold; margin: 0 0 12px 0; }}
            p {{ color: #94a3b8; font-size: 13px; line-height: 1.6; margin: 0 0 24px 0; }}
            .btn-group {{ display: flex; flex-direction: column; gap: 10px; }}
            .btn {{ display: inline-flex; align-items: center; justify-content: center; gap: 8px; background: #2563eb; color: white; padding: 12px 24px; border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 13px; border: none; cursor: pointer; transition: all 0.2s; }}
            .btn:hover {{ background: #1d4ed8; }}
            .btn-outline {{ background: transparent; border: 1px solid #475569; color: #cbd5e1; }}
            .btn-outline:hover {{ background: #334155; color: white; border-color: #64748b; }}
            details {{ margin-top: 20px; text-align: left; background: #0b1329; border-radius: 12px; padding: 12px; font-size: 11px; color: #94a3b8; border: 1px solid #1e293b; }}
            summary {{ cursor: pointer; font-weight: bold; color: #cbd5e1; user-select: none; }}
            pre {{ margin-top: 8px; font-family: monospace; white-space: pre-wrap; word-break: break-all; color: #fca5a5; font-size: 11px; max-height: 150px; overflow-y: auto; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">⚠️</div>
            <h1>មានបញ្ហាបច្ចេកទេសបណ្ដោះអាសន្ន</h1>
            <p>ប្រព័ន្ធបានជួបប្រទះបញ្ហាបច្ចេកទេសបណ្ដោះអាសន្ន ឬ Server កំពុងរៀបចំឡើងវិញ។ សូមចុច Refresh ឬជ្រើសរើសទំព័រខាងក្រោម៖</p>
            <div class="btn-group">
                <button onclick="window.location.reload()" class="btn">🔁 ព្យាយាមម្តងទៀត (Refresh Page)</button>
                <a href="/dashboard" class="btn btn-outline">🏠 ត្រឡប់ទៅផ្ទាំងគ្រប់គ្រង (Dashboard)</a>
                <a href="/voters" class="btn btn-outline">👥 បញ្ជីអ្នកបោះឆ្នោត</a>
                <a href="/birth-certificates" class="btn btn-outline">👶 បញ្ជីសំបុត្រកំណើត</a>
            </div>
            <details>
                <summary>🔍 ព័ត៌មានលម្អិតបច្ចេកទេស (Technical Details)</summary>
                <pre><strong>URL:</strong> {request.method} {request.url}
<strong>Type:</strong> {error_type}
<strong>Message:</strong> {error_detail}</pre>
            </details>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=500)

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
