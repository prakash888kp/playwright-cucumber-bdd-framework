"""Read an xlsx sheet into a list of dicts (first row = headers)."""
from pathlib import Path

from openpyxl import load_workbook


def read_sheet(file_path, sheet_name: str) -> list[dict]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Workbook not found: {path}")
    wb = load_workbook(path, read_only=True, data_only=True)
    if sheet_name not in wb.sheetnames:
        raise KeyError(f'Sheet "{sheet_name}" not found in {path.name}. Available: {wb.sheetnames}')
    ws = wb[sheet_name]
    rows = ws.iter_rows(values_only=True)
    headers = [str(h) if h is not None else "" for h in next(rows, [])]
    result = []
    for row in rows:
        if all(cell is None for cell in row):
            continue
        result.append({h: ("" if v is None else v) for h, v in zip(headers, row)})
    wb.close()
    return result
