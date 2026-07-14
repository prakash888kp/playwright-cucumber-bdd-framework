"""Manual report rebuild from the last reports/behave-report.json.
Rarely needed — every run auto-reports via scripts/run.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.config.env_loader import load_env  # noqa: E402

load_env()

from framework.helpers.report_builder import build_report  # noqa: E402

if __name__ == "__main__":
    build_report()
