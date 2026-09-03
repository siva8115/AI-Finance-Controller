import sys
import logging
from pathlib import Path

# Configure logger to output explicit tracebacks in Vercel Function Logs
logger = logging.getLogger("vercel_entrypoint")

file_path = Path(__file__).resolve()
api_dir = file_path.parent
root_dir = api_dir.parent
backend_dir = root_dir / "backend"

# Ensure backend directory is at the head of sys.path for deterministic package import
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from app.main import app
except Exception as e:
    logger.error("Failed to import FastAPI application 'app.main': %s", e, exc_info=True)
    raise e
