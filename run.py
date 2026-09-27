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
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "uvicorn",
                "app.main:app",
                "--reload",
                "--host", "0.0.0.0",
                "--port", "8000",
            ],
            cwd=str(BACKEND),
            check=False,
        )
    except KeyboardInterrupt:
        print("\nCSMS đã dừng theo yêu cầu.")
        raise SystemExit(0)

    if result.returncode in (0, -2, 130):
        print("CSMS đã dừng.")
        raise SystemExit(0)
    raise SystemExit(result.returncode)
