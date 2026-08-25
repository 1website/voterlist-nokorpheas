import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "voter_list.db")

# Read DATABASE_URL from environment (e.g. Render / Supabase / Neon PostgreSQL)
raw_db_url = os.getenv("DATABASE_URL", "").strip()

if raw_db_url:
    # Fix postgres:// prefix for SQLAlchemy 2.0 (Render/Heroku compatibility)
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    
    DATABASE_URL = raw_db_url
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )
    IS_SQLITE = False
    DB_TYPE_NAME = "PostgreSQL (Cloud Database)"
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
    IS_SQLITE = True
    DB_TYPE_NAME = "SQLite (Local File)"

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_schema_migrations():
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if "users" in tables:
            columns = [col["name"] for col in inspector.get_columns("users")]
            if "photo_url" not in columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN photo_url VARCHAR(255)"))
                    conn.commit()

        # For SQLite only: Apply UTC timezone offset migration for existing legacy records
        if IS_SQLITE and "voters" in tables and "audit_logs" in tables:
            with engine.connect() as conn:
                conn.execute(text(
                    "UPDATE voters SET created_at = datetime(created_at, '+7 hours'), "
                    "updated_at = datetime(COALESCE(updated_at, created_at), '+7 hours') "
                    "WHERE created_at >= '2026-08-24 17:00:00' AND created_at <= '2026-08-24 23:59:59'"
                ))
                conn.execute(text(
                    "UPDATE audit_logs SET created_at = datetime(created_at, '+7 hours') "
                    "WHERE created_at >= '2026-08-24 17:00:00' AND created_at <= '2026-08-24 23:59:59'"
                ))
                conn.commit()
    except Exception as e:
        print(f"Migration note: {e}")
