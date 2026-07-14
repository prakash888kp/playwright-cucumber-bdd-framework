"""Excel-driven execution (run mode 1) — build a behave tag expression from
every ExecutionControl row where Run = YES.

Also audits the control sheet against the feature files: a ScenarioID with no
matching @tag would silently run nothing, so drift is surfaced loudly.
"""
import re
from pathlib import Path

from ..helpers.excel_reader import read_sheet
from ..helpers.logger import logger

ROOT = Path(__file__).resolve().parents[2]
CONTROL_XLSX = ROOT / "config" / "execution-control.xlsx"
FEATURES_DIR = ROOT / "features"


def feature_scenario_ids() -> set[str]:
    """All @TC_* tags present in the feature files."""
    ids = set()
    for feature in FEATURES_DIR.rglob("*.feature"):
        ids.update(re.findall(r"@(TC_\w+)", feature.read_text(encoding="utf-8")))
    return ids


def excel_tag_expression() -> str | None:
    rows = read_sheet(CONTROL_XLSX, "ExecutionControl")
    selected = [r for r in rows if str(r.get("Run", "")).strip().upper() == "YES"]
    logger.info(f"Execution control: {len(selected)}/{len(rows)} scenarios flagged YES")

    known = feature_scenario_ids()
    orphans = [r["ScenarioID"] for r in selected if r["ScenarioID"] not in known]
    if orphans:
        logger.warning(
            f"Control sheet rows with no matching scenario tag (will run nothing): {', '.join(orphans)}"
        )
    untracked = known - {str(r.get("ScenarioID")) for r in rows}
    if untracked:
        logger.warning(
            f"Scenarios tagged in features but missing from the control sheet: {', '.join(sorted(untracked))}"
        )

    if not selected:
        return None
    return " or ".join(f"@{r['ScenarioID']}" for r in selected)
