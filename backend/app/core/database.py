import os
import shutil
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings, IS_VERCEL, BASE_DIR

db_url = settings.DATABASE_URL

if db_url.startswith("sqlite"):
    db_path_str = db_url.replace("sqlite:///", "")
    if IS_VERCEL and db_path_str.startswith(tempfile.gettempdir()):
        tmp_db_path = Path(db_path_str)
        if not tmp_db_path.exists():
            for possible_source in [BASE_DIR / "finance.db", BASE_DIR.parent / "finance.db"]:
                if possible_source.exists():
                    try:
                        shutil.copy(possible_source, tmp_db_path)
                        break
                    except Exception:
                        pass

# SQLite connection check
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session to FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
