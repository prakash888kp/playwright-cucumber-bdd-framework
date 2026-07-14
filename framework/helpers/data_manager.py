"""Test-data manager — cached sheets from config/testdata.xlsx, rows keyed by TC_ID."""
from pathlib import Path

from .excel_reader import read_sheet
from .logger import logger

ROOT = Path(__file__).resolve().parents[2]
TESTDATA_XLSX = ROOT / "config" / "testdata.xlsx"

_cache: dict[str, list[dict]] = {}


def get_sheet(sheet_name: str) -> list[dict]:
    if sheet_name not in _cache:
        _cache[sheet_name] = read_sheet(TESTDATA_XLSX, sheet_name)
        logger.debug(f"Loaded sheet {sheet_name}: {len(_cache[sheet_name])} rows")
    return _cache[sheet_name]


def get_data(sheet_name: str, tc_id: str) -> dict:
    row = next((r for r in get_sheet(sheet_name) if str(r.get("TC_ID")) == tc_id), None)
    if row is None:
        raise KeyError(f'No row with TC_ID "{tc_id}" in sheet "{sheet_name}" of testdata.xlsx')
    return row
