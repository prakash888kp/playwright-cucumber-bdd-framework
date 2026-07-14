"""Excel-driven execution (run mode 1) — build a behave tag expression from
every ExecutionControl row where Run = YES.
"""
from pathlib import Path

from ..helpers.excel_reader import read_sheet
from ..helpers.logger import logger

ROOT = Path(__file__).resolve().parents[2]
CONTROL_XLSX = ROOT / "config" / "execution-control.xlsx"


def excel_tag_expression() -> str | None:
    rows = read_sheet(CONTROL_XLSX, "ExecutionControl")
    selected = [r for r in rows if str(r.get("Run", "")).strip().upper() == "YES"]
    logger.info(f"Execution control: {len(selected)}/{len(rows)} scenarios flagged YES")
    if not selected:
        return None
    return " or ".join(f"@{r['ScenarioID']}" for r in selected)
