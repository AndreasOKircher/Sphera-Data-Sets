# core/xls_manifest.py
from __future__ import annotations
from dataclasses import dataclass, field
import re
import openpyxl


@dataclass
class ManifestEntry:
    uuid: str
    source_url: str
    xls_dataset_type: str
    databases: list[str]


# Column indices (0-based) matching the actual Sphera XLS layout:
#   Row 4 = headers, Row 5+ = data
_COL_GUID = 1   # "GUID"
_COL_TYPE = 11  # "Dataset type"
_COL_DBS  = 16  # "All standard DBs that contain this dataset (new names only)"
_COL_URL  = 28  # "Website link"
_DATA_START_ROW = 5


def load_manifest(xls_path: str) -> dict[str, ManifestEntry]:
    """Load the Sphera XLS manifest and return a dict keyed by UUID.

    GUIDs in the XLS are upper-case with braces ({...}); they are normalised
    to lower-case without braces to match the UUID format used in dataset JSON.

    Skips rows where GUID cell is blank.
    Multi-database cells are split on newline or "/" separators.
    """
    wb = openpyxl.load_workbook(xls_path, read_only=True, data_only=True)
    ws = wb.active
    result: dict[str, ManifestEntry] = {}

    for row in ws.iter_rows(min_row=_DATA_START_ROW, values_only=False):
        def _cell(idx: int) -> str:
            v = row[idx].value if idx < len(row) else None
            return str(v).strip() if v is not None else ""

        raw_guid = _cell(_COL_GUID)
        if not raw_guid:
            continue

        # Normalise: strip braces, lower-case → "0009da54-4751-..."
        uuid = raw_guid.strip("{}").lower()

        raw_dbs = _cell(_COL_DBS)
        # Split on newline OR "/" — the XLS uses both as multi-DB separators
        databases = [db.strip() for db in re.split(r'[\n/]', raw_dbs) if db.strip()]

        result[uuid] = ManifestEntry(
            uuid=uuid,
            source_url=_cell(_COL_URL),
            xls_dataset_type=_cell(_COL_TYPE),
            databases=databases,
        )

    wb.close()
    return result


def get_uuids_for_databases(
    manifest: dict[str, ManifestEntry],
    db_names: list[str],
) -> list[str]:
    """Return UUIDs whose databases list overlaps with db_names."""
    target = set(db_names)
    return [
        entry.uuid
        for entry in manifest.values()
        if target.intersection(entry.databases)
    ]
