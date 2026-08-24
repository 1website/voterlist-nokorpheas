import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "voter_list.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_schema_migrations():
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            # Check if photo_url exists in users table
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            if "photo_url" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN photo_url VARCHAR(255)"))
                conn.commit()

            # Migration: Shift any voters/logs registered during early morning hours in UTC to local Cambodia time (UTC+7)
            # Records created between 2026-08-24 17:00:00 UTC and 2026-08-24 23:59:59 UTC correspond to 2026-08-25 Cambodia time (00:00 to 06:59)
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

# Run schema check
ensure_schema_migrations()
