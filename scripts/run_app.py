"""Run the MoreyMachine Streamlit dashboard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "src" / "moreymachine" / "app" / "streamlit_app.py"


def main() -> int:
    """Launch Streamlit against the project dashboard entry point."""
    command = [sys.executable, "-m", "streamlit", "run", str(APP_PATH)]
    return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
