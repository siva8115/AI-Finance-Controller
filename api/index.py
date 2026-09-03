import os
import sys
from pathlib import Path

# Ensure root, backend, and api directories are added to sys.path
file_path = Path(__file__).resolve()
api_dir = file_path.parent
root_dir = api_dir.parent
backend_dir = root_dir / "backend"

for path_str in [str(backend_dir), str(root_dir), str(api_dir)]:
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

try:
    from app.main import app
except Exception:
    from backend.app.main import app
