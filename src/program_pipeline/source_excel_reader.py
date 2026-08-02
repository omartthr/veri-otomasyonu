"""URL kaynak Excel dosyasını okuma modülü.

Sütun isimlerinde küçük farklılıklar olabilir.
COLUMN_ALIASES tablosuyla sütunları otomatik tespit eder.

"Gerekli değil (... verisi mevcut)" yazılı URL sütunları için official_website
fallback mekanizması: Bot bu durumda official_website üzerinden keşif yapar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from src.program_pipeline.models import SourceUniversityRow

logger = logging.getLogger(__name__)

# Sütun takma adları — farklı Excel versiyonlarındaki başlıkları normalleştirir
COLUMN_ALIASES: dict[str, list[str]] = {
    "university_id": [
        "Üniversite ID", "University ID", "university_id", "ID", "Uni ID",
        "ÜNİVERSİTE ID", "Üniversite No",
    ],
    "university_name": [
        "Üniversite Adı", "University Name", "Üniversite", "university_name",
        "ÜNİVERSİTE ADI", "Kurum Adı", "Institution Name",
    ],
    "official_website": [
        "Web Sitesi", "Website", "Official Website", "Resmi Site",
        "official_website", "Resmî Web Sitesi", "URL", "Web",
    ],
    "program_url": [
        # Gerçek dosyadaki isimler
        "[DOLDUR] Program Listesi URL", "Program Listesi URL",
        "Program URL", "Programlar URL",
        "Programs URL", "program_url", "Program Link",
        "J",  # eski format
    ],
    "admission_url": [
        # Gerçek dosyadaki isimler
        "[DOLDUR] Kabul Şartları URL", "Kabul Şartları URL",
        "Kabul URL", "Admission URL",
        "Admissions URL", "admission_url", "Kabul Link",
        "K",
    ],
    "language_url": [
        # Gerçek dosyadaki isimler
        "[DOLDUR] Dil Şartları URL", "Dil Şartları URL",
        "Dil Şartı URL", "Language URL",
        "English Requirements URL", "language_url", "Dil Şartı Link",
        "L",
    ],
    "tuition_url": [
        # Gerçek dosyadaki isimler
        "[DOLDUR] Ücret URL", "Ücret URL",
        "Tuition URL", "Fees URL",
        "Tuition and Fees URL", "tuition_url", "Ücret Link",
        "M",
    ],
    "notes": [
        "Notlar", "Notes", "notes", "Not", "Açıklamalar",
    ],
}

# "Gerekli değil" anlamına gelen anahtar kelimeler (küçük harf).
# URL sütununda bu metinler varsa veri zaten mevcut → official_website fallback.
_NOT_NEEDED_KEYWORDS = [
    "gerekli değil",
    "gerekli degil",
    "not needed",
    "mevcut",          # "program verisi mevcut"
    "n/a",
    "zaten mevcut",
    "not required",
    "already available",
]


def _normalize_header(text: str) -> str:
    """Başlık metnini karşılaştırma için normalize et."""
    return str(text).strip().lower().replace("  ", " ")


def _is_not_needed(val: Optional[str]) -> bool:
    """Hücre değeri 'gerekli değil' anlamı taşıyor mu?

    Örnek: "gerekli değil (program verisi mevcut)" → True
    """
    if not val:
        return False
    v = val.strip().lower()
    return any(kw in v for kw in _NOT_NEEDED_KEYWORDS)


def _detect_column_map(headers: list[str]) -> dict[str, int]:
    """Başlık listesinden sütun → konum haritasını oluştur (0-tabanlı)."""
    header_lower = {_normalize_header(h): i for i, h in enumerate(headers)}
    result: dict[str, int] = {}

    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_norm = _normalize_header(alias)
            if alias_norm in header_lower:
                result[field] = header_lower[alias_norm]
                break

    return result


def read_source_excel(
    file_path: Path | str,
    sheet_name: Optional[str] = None,
) -> list[SourceUniversityRow]:
    """URL kaynak Excel dosyasını okuyarak SourceUniversityRow listesi döndür.

    Args:
        file_path: .xlsx dosya yolu
        sheet_name: Okunacak sayfa adı (None = önce 'Takip', sonra aktif sayfa)

    Returns:
        SourceUniversityRow listesi

    Raises:
        FileNotFoundError: Dosya bulunamazsa
        ValueError: Başlık satırı veya zorunlu sütunlar bulunamazsa
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Kaynak Excel bulunamadı: {file_path}")

    logger.info("Kaynak Excel okunuyor: %s", file_path)

    wb = load_workbook(file_path, data_only=True)

    # Sheet seç
    if sheet_name and sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    elif "Takip" in wb.sheetnames:
        ws = wb["Takip"]
    else:
        ws = wb.active

    if ws is None:
        raise ValueError("Excel'de aktif sayfa bulunamadı.")

    # İlk satırı başlık kabul et; boş satırları atla
    max_col = ws.max_column or 1
    header_row_vals = [
        str(ws.cell(row=1, column=c).value or "").strip()
        for c in range(1, max_col + 1)
    ]

    col_map = _detect_column_map(header_row_vals)

    if "university_name" not in col_map:
        # Başlık satırı yoksa sabit konumları dene (eski format A-M)
        col_map = _try_fixed_columns()
        logger.warning(
            "Başlık satırı tespit edilemedi, sabit sütun konumları deneniyor: %s", file_path
        )

    logger.info("Sütun haritası: %s", col_map)

    rows: list[SourceUniversityRow] = []

    def _clean_url(val: Optional[str]) -> Optional[str]:
        """Geçersiz URL gösterge değerlerini None'a çevir."""
        if not val:
            return None
        v = val.strip()
        # Gerçek URL olmalı
        if not (v.startswith("http://") or v.startswith("https://")):
            return None
        return v

    def _resolve_url(
        raw_val: Optional[str],
        fallback_website: Optional[str],
    ) -> tuple[Optional[str], bool]:
        """URL hücresini çöz.

        Mantık:
        1. Gerçek URL varsa → onu kullan, not_needed=False
        2. "Gerekli değil" yazıyorsa → official_website'i fallback yap, not_needed=True
        3. Boşsa → None, not_needed=False

        Returns:
            (url, not_needed) çifti
        """
        if not raw_val:
            return None, False

        cleaned = _clean_url(raw_val)
        if cleaned:
            # Gerçek URL var — doğrudan kullan
            return cleaned, False

        if _is_not_needed(raw_val):
            # "gerekli değil ..." yazıyor → official_website'i fallback olarak ata
            fallback = _clean_url(fallback_website)
            if fallback:
                logger.debug(
                    "'gerekli değil' tespiti → official_website fallback: %s", fallback
                )
            return fallback, True

        # Ne URL ne de "gerekli değil" → boş
        return None, False

    for row_idx in range(2, ws.max_row + 1):
        def _cell(field: str, row: int = row_idx) -> Optional[str]:
            col = col_map.get(field)
            if col is None:
                return None
            cell_val = ws.cell(row=row, column=col + 1).value
            return str(cell_val).strip() if cell_val is not None else None

        name = _cell("university_name")
        if not name:
            continue

        official_site = _clean_url(_cell("official_website"))

        # Her URL sütununu çöz — "gerekli değil" ise official_website fallback
        prog_url, prog_not_needed = _resolve_url(_cell("program_url"), official_site)
        adm_url, adm_not_needed = _resolve_url(_cell("admission_url"), official_site)
        lang_url, lang_not_needed = _resolve_url(_cell("language_url"), official_site)
        tuit_url, tuit_not_needed = _resolve_url(_cell("tuition_url"), official_site)

        rows.append(
            SourceUniversityRow(
                row_number=row_idx,
                university_id=_cell("university_id"),
                university_name=name,
                official_website=official_site,
                program_url=prog_url,
                admission_url=adm_url,
                language_url=lang_url,
                tuition_url=tuit_url,
                notes=_cell("notes"),
                program_not_needed=prog_not_needed,
                admission_not_needed=adm_not_needed,
                language_not_needed=lang_not_needed,
                tuition_not_needed=tuit_not_needed,
            )
        )

    wb.close()
    logger.info("%d üniversite satırı okundu (kaynak Excel).", len(rows))
    return rows


def _try_fixed_columns() -> dict[str, int]:
    """Başlık tespit edilemezse eski sabit sütun konumlarını kullan."""
    return {
        "university_id": 0,       # A
        "university_name": 1,     # B
        "official_website": 4,    # E
        "program_url": 9,         # J
        "admission_url": 10,      # K
        "language_url": 11,       # L
        "tuition_url": 12,        # M
        "notes": 15,              # P
    }
