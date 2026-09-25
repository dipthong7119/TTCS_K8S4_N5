#!/usr/bin/env python3
"""
run.py -- Entry point chay du an CSMS tren may local (khong qua Docker).
Su dung:
    python run.py
    # hoac
    uvicorn backend.app.main:app --reload

De chay voi Docker:
    docker compose up --build
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"

if __name__ == "__main__":
    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000",
        ],
        cwd=str(BACKEND),
        check=True,
    )
