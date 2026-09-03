import sys
from pathlib import Path

# Add root_dir and backend_dir to sys.path for Vercel Serverless Function
file_path = Path(__file__).resolve()
root_dir = file_path.parent.parent
backend_dir = root_dir / "backend"

for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from backend.app.main import app
except Exception:
    from app.main import app
