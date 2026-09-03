from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db, engine, Base
import app.models.financial  # Ensure all SQLAlchemy models are registered in Base.metadata
from app.schemas.common import HealthCheckResponse
from app.api.v1.api import api_router

# Create database tables if not existing and sync missing columns
Base.metadata.create_all(bind=engine)

def _auto_migrate_columns():
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        for model in Base.__subclasses__():
            tablename = getattr(model, "__tablename__", None)
            if tablename and tablename in tables:
                existing_cols = {col["name"] for col in inspector.get_columns(tablename)}
                for column in model.__table__.columns:
                    if column.name not in existing_cols:
                        col_type = column.type.compile(engine.dialect)
                        default_str = ""
                        if column.default is not None and column.default.arg is not None:
                            if isinstance(column.default.arg, (str, int, float)):
                                default_str = f" DEFAULT {repr(column.default.arg)}"
                        sql = f"ALTER TABLE {tablename} ADD COLUMN {column.name} {col_type}{default_str}"
                        with engine.begin() as conn:
                            conn.execute(text(sql))
    except Exception as e:
        pass

_auto_migrate_columns()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Autonomous Multi-Source Financial Reconciliation Engine API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configure CORS for Vite frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)



@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health Check Endpoint to verify API and database connectivity."""
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    return HealthCheckResponse(
        status="healthy" if db_connected else "degraded",
        project_name=settings.PROJECT_NAME,
        version="1.0.0",
        database_connected=db_connected,
    )


@app.get("/", tags=["Root"])
def root():
    """Root endpoint providing basic API details."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
