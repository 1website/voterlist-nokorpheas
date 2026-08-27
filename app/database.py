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

        if "voters" in tables:
            voter_columns = [col["name"] for col in inspector.get_columns("voters")]
            with engine.connect() as conn:
                if "reg_type" not in voter_columns:
                    conn.execute(text("ALTER TABLE voters ADD COLUMN reg_type VARCHAR(30) DEFAULT 'new'"))
                if "reg_year" not in voter_columns:
                    conn.execute(text("ALTER TABLE voters ADD COLUMN reg_year INTEGER DEFAULT 2026"))
                if "reg_reason" not in voter_columns:
                    conn.execute(text("ALTER TABLE voters ADD COLUMN reg_reason VARCHAR(100)"))
                conn.commit()

        if "birth_certificates" in tables:
            bc_columns = [col["name"] for col in inspector.get_columns("birth_certificates")]
            with engine.connect() as conn:
                if "attachment_url" not in bc_columns:
                    conn.execute(text("ALTER TABLE birth_certificates ADD COLUMN attachment_url VARCHAR(255)"))
                if "registered_date" not in bc_columns:
                    conn.execute(text("ALTER TABLE birth_certificates ADD COLUMN registered_date VARCHAR(50)"))
                    if IS_SQLITE:
                        conn.execute(text("UPDATE birth_certificates SET registered_date = SUBSTR(created_at, 1, 10) WHERE registered_date IS NULL AND created_at IS NOT NULL"))
                    else:
                        conn.execute(text("UPDATE birth_certificates SET registered_date = CAST(created_at AS VARCHAR(10)) WHERE registered_date IS NULL AND created_at IS NOT NULL"))
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
