"""Verify SCRUM-135 against isolated pytest fixtures and shipped frontend scripts.

Run from the repository root: python tests/verify_scrum135_live.py
The historical filename is retained; this command no longer logs into the
running web app or triggers an IP lockout on the user's database.
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_auth.py", "tests/test_scrum135_live.py",
         "tests/test_frontend_assets.py", "--tb=short", "-q"],
        cwd=repo_root,
        check=False,
    )
    if result.returncode:
        return result.returncode
    return subprocess.run(
        ["node", "--test", "tests/frontend_behavior.cjs"], cwd=repo_root, check=False
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
