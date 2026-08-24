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
    except Exception as e:
        print(f"Migration note: {e}")

# Run schema check
ensure_schema_migrations()
