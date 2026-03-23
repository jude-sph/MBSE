from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

from src.models import Requirement


def parse_requirements_file(file_path: Path) -> list[Requirement]:
    """Parse XLSX or CSV file into a list of Requirement objects."""
    suffix = file_path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return _parse_xlsx(file_path)
    elif suffix == ".csv":
        return _parse_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .xlsx, .xls, or .csv")


def _normalise_header(headers: list[str]) -> dict[str, int]:
    """Return a mapping of canonical column name -> zero-based column index."""
    normalised: dict[str, int] = {}
    for idx, header in enumerate(headers):
        if header is None:
            continue
        key = str(header).strip().lower()
        normalised[key] = idx
    return normalised


def _row_to_requirement(
    values: list,
    col_map: dict[str, int],
) -> Requirement | None:
    """Convert a list of cell values into a Requirement, or None if the row is empty."""

    def get(col: str) -> str:
        idx = col_map.get(col)
        if idx is None:
            return ""
        raw = values[idx] if idx < len(values) else None
        return str(raw).strip() if raw is not None else ""

    req_id = get("id")
    text = get("text")
    source_dig = get("source_dig")

    # Skip entirely empty rows
    if not req_id and not text:
        return None

    return Requirement(id=req_id, text=text, source_dig=source_dig)


def _parse_xlsx(file_path: Path) -> list[Requirement]:
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active

    requirements: list[Requirement] = []
    col_map: dict[str, int] | None = None

    for row in ws.iter_rows(values_only=True):
        # Skip completely empty rows before the header
        if all(cell is None for cell in row):
            continue

        if col_map is None:
            # Auto-detect header row: must contain at least 'id' and 'text'
            candidate = _normalise_header(list(row))
            if "id" in candidate and "text" in candidate:
                col_map = candidate
            continue

        req = _row_to_requirement(list(row), col_map)
        if req is not None:
            requirements.append(req)

    wb.close()
    return requirements


def _parse_csv(file_path: Path) -> list[Requirement]:
    requirements: list[Requirement] = []

    with file_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        # Build a normalised key map from whatever headers are present
        if reader.fieldnames is None:
            return requirements

        col_map: dict[str, str] = {
            h.strip().lower(): h for h in reader.fieldnames if h is not None
        }

        id_col = col_map.get("id")
        text_col = col_map.get("text")
        source_col = col_map.get("source_dig")

        for row in reader:
            req_id = row.get(id_col, "").strip() if id_col else ""
            text = row.get(text_col, "").strip() if text_col else ""
            source_dig = row.get(source_col, "").strip() if source_col else ""

            if not req_id and not text:
                continue

            requirements.append(Requirement(id=req_id, text=text, source_dig=source_dig))

    return requirements
