from pathlib import Path

def get_frontend_dir():
    # Try docker path first
    p = Path("/app/frontend")
    if p.exists():
        return p
    # Try local path
    return Path(__file__).parent.parent.parent / "frontend"
