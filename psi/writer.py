"""Writer — applies a finished plan to the working tree.

Writes the generated files and appends rows to the two xlsx workbooks. Idempotent:
re-applying the same scenario id overwrites its files and skips duplicate rows,
so re-running a ticket does not pile up duplicates.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .models import DataRow, GeneratedArtifact

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
TESTDATA = CONFIG / "testdata.xlsx"
CONTROL = CONFIG / "execution-control.xlsx"


def write_files(artifacts: list[GeneratedArtifact]) -> list[str]:
    written = []
    for art in artifacts:
        dest = ROOT / art.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(art.content, encoding="utf-8")
        written.append(art.path)
    return written


def _upsert_row(workbook: Path, sheet: str, values: dict) -> str:
    """Update the row with this id in place, or append it. Upsert (not skip) so a
    healed/corrected generation overwrites the earlier wrong row."""
    wb = load_workbook(workbook)
    ws = wb[sheet]
    headers = [c.value for c in ws[1]]
    id_col = "ScenarioID" if "ScenarioID" in headers else headers[0]
    new_id = str(values.get(id_col, ""))
    action = "added"
    for row in ws.iter_rows(min_row=2):
        if str(row[headers.index(id_col)].value) == new_id:
            for cell, header in zip(row, headers, strict=False):
                cell.value = values.get(header, cell.value)
            action = "updated"
            break
    else:
        ws.append([values.get(h, "") for h in headers])
    wb.save(workbook)
    wb.close()
    return action


def apply_data_rows(rows: list[DataRow]) -> list[str]:
    applied = []
    for row in rows:
        target = CONTROL if row.sheet == "ExecutionControl" else TESTDATA
        action = _upsert_row(target, row.sheet, row.values)
        applied.append(f"{row.sheet}:{action} {row.values.get('ScenarioID') or row.values.get('TC_ID')}")
    return applied
