"""Excel dosyasından üniversite verilerini okuma modülü.

openpyxl ile .xlsx dosyalarını okur, satırları UniversityRow modeline dönüştürür
ve eksik alanları belirler.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.models import ResearchCategory, UniversityRow

logger = logging.getLogger(__name__)

# Beklenen sütun eşleştirmesi (1-tabanlı)
COLUMN_MAP: dict[str, int] = {
    "university_id": 1,       # A
    "university_name": 2,     # B
    "city": 3,                # C
    "institution_type": 4,    # D
    "website": 5,             # E
    "program_missing": 6,     # F
    "admission_missing": 7,   # G
    "language_missing": 8,    # H
    "tuition_missing": 9,     # I
    "program_url": 10,        # J
    "admission_url": 11,      # K
    "language_url": 12,       # L
    "tuition_url": 13,        # M
    "assigned_person": 14,    # N
    "status": 15,             # O
    "notes": 16,              # P
}

# Başlık satırı varsayılan olarak 1. satır
DEFAULT_HEADER_ROW = 1


def _cell_value_str(ws: Worksheet, row: int, col: int) -> Optional[str]:
    """Hücre değerini string olarak döndür. Boşsa None döner."""
    cell = ws.cell(row=row, column=col)
    val = cell.value
    if val is None:
        return None
    return str(val).strip()


def read_excel(
    file_path: Path | str,
    sheet_name: Optional[str] = None,
    header_row: int = DEFAULT_HEADER_ROW,
) -> list[UniversityRow]:
    """Excel dosyasını okuyarak UniversityRow listesi döndür.

    Args:
        file_path: .xlsx dosya yolu
        sheet_name: Okunacak sayfa adı (None = aktif sayfa)
        header_row: Başlık satır numarası (veri bu satırın altından başlar)

    Returns:
        UniversityRow nesnelerinin listesi

    Raises:
        FileNotFoundError: Dosya bulunamazsa
        ValueError: Geçerli veri satırı bulunamazsa
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Excel dosyası bulunamadı: {file_path}")
    if not file_path.suffix.lower() == ".xlsx":
        raise ValueError(f"Desteklenmeyen dosya formatı: {file_path.suffix}. Yalnızca .xlsx desteklenir.")

    logger.info("Excel dosyası okunuyor: %s", file_path)

    wb = load_workbook(file_path, data_only=True)
    if sheet_name:
        ws = wb[sheet_name]
    elif "Takip" in wb.sheetnames:
        ws = wb["Takip"]
    else:
        ws = wb.active

    if ws is None:
        raise ValueError("Excel dosyasında aktif sayfa bulunamadı.")

    rows: list[UniversityRow] = []
    data_start_row = header_row + 1

    for row_idx in range(data_start_row, ws.max_row + 1):
        # B sütunu (üniversite adı) boşsa satırı atla
        name = _cell_value_str(ws, row_idx, COLUMN_MAP["university_name"])
        if not name:
            continue

        try:
            uni_row = UniversityRow(
                row_number=row_idx,
                university_id=_cell_value_str(ws, row_idx, COLUMN_MAP["university_id"]),
                university_name=name,
                city=_cell_value_str(ws, row_idx, COLUMN_MAP["city"]),
                institution_type=_cell_value_str(ws, row_idx, COLUMN_MAP["institution_type"]),
                website=_cell_value_str(ws, row_idx, COLUMN_MAP["website"]),
                program_missing=_cell_value_str(ws, row_idx, COLUMN_MAP["program_missing"]),
                admission_missing=_cell_value_str(ws, row_idx, COLUMN_MAP["admission_missing"]),
                language_missing=_cell_value_str(ws, row_idx, COLUMN_MAP["language_missing"]),
                tuition_missing=_cell_value_str(ws, row_idx, COLUMN_MAP["tuition_missing"]),
                program_url=_cell_value_str(ws, row_idx, COLUMN_MAP["program_url"]),
                admission_url=_cell_value_str(ws, row_idx, COLUMN_MAP["admission_url"]),
                language_url=_cell_value_str(ws, row_idx, COLUMN_MAP["language_url"]),
                tuition_url=_cell_value_str(ws, row_idx, COLUMN_MAP["tuition_url"]),
                assigned_person=_cell_value_str(ws, row_idx, COLUMN_MAP["assigned_person"]),
                status=_cell_value_str(ws, row_idx, COLUMN_MAP["status"]),
                notes=_cell_value_str(ws, row_idx, COLUMN_MAP["notes"]),
            )
            rows.append(uni_row)
        except Exception as e:
            logger.warning("Satır %d okunamadı: %s", row_idx, e)
            continue

    wb.close()
    logger.info("%d üniversite satırı okundu.", len(rows))
    return rows


def count_missing_fields(rows: list[UniversityRow]) -> dict[str, int]:
    """Eksik alan istatistiklerini döndür.

    Returns:
        {"total": N, "program": N, "admission": N, "language": N, "tuition": N}
    """
    stats: dict[str, int] = {
        "total": 0,
        "program": 0,
        "admission": 0,
        "language": 0,
        "tuition": 0,
    }

    for row in rows:
        missing = row.get_missing_categories()
        for cat in missing:
            stats[cat.value] += 1
            stats["total"] += 1

    return stats


def get_universities_needing_research(rows: list[UniversityRow]) -> list[UniversityRow]:
    """En az bir eksik alanı olan üniversiteleri döndür."""
    return [row for row in rows if row.get_missing_categories()]
