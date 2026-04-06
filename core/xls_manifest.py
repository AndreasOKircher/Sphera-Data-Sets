# core/xls_manifest.py
from __future__ import annotations
from dataclasses import dataclass, field
import openpyxl


@dataclass
class ManifestEntry:
    uuid: str
    source_url: str
    xls_dataset_type: str
    databases: list[str]


# Column indices (0-based) in the XLS sheet
_COL_GUID = 0
_COL_URL = 1
_COL_TYPE = 2
_COL_DBS = 3


def load_manifest(xls_path: str) -> dict[str, ManifestEntry]:
    """Load the Sphera XLS manifest and return a dict keyed by GUID.

    Skips rows where GUID cell is blank.
    Multi-database cells are split on newline.
    """
    wb = openpyxl.load_workbook(xls_path, read_only=True, data_only=True)
    ws = wb.active
    result: dict[str, ManifestEntry] = {}

    for row in ws.iter_rows(min_row=2, values_only=False):
        def _cell(idx: int) -> str:
            v = row[idx].value if idx < len(row) else None
            return str(v).strip() if v is not None else ""

        guid = _cell(_COL_GUID)
        if not guid:
            continue

        raw_dbs = _cell(_COL_DBS)
        databases = [db.strip() for db in raw_dbs.splitlines() if db.strip()]

        result[guid] = ManifestEntry(
            uuid=guid,
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
