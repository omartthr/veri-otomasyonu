"""Son Başvuru Tarihi Formatlayıcı — Tüm tarihleri YYYY-MM-DD standart ISO formatına dönüştürür.

Örnekler:
- "15 Ocak 2025" -> "2025-01-15"
- "January 15, 2025" -> "2025-01-15"
- "15/01/2025" -> "2025-01-15"
- "2025-01-15" -> "2025-01-15"
- "Güz: 1 Aralık 2025 / Bahar: 1 Mayıs 2026" -> "Güz: 2025-12-01 / Bahar: 2026-05-01"
- "Rolling Admission" -> "Rolling Admission"
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Ay isimleri haritası
_MONTH_MAP = {
    # Türkçe
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
    # İngilizce
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _format_single_date(day: int, month: int, year: int) -> str:
    """Yıl, ay ve günü YYYY-MM-DD biçimine çevir."""
    curr_year = datetime.now().year
    if year < 100:
        year += 2000
    elif year == 0:
        year = curr_year

    return f"{year:04d}-{month:02d}-{day:02d}"


def normalize_date_to_iso(date_text: str) -> str:
    """Son başvuru tarihi metnindeki takvim tarihlerini YYYY-MM-DD formatına dönüştürür.

    Args:
        date_text: Ham veya mevcut tarih hücresi metni

    Returns:
        YYYY-MM-DD formatında düzenlenmiş metin
    """
    if not date_text:
        return ""

    text = str(date_text).strip()
    if text.lower() in ("rolling admission", "rolling", "sürekli kabul", "open enrollment", "n/a", "boş", "—"):
        return text

    # Zaten tek başına YYYY-MM-DD ise
    if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
        return text

    month_pattern = "|".join(_MONTH_MAP.keys())

    # 1. "15 Ocak 2025" veya "15 January 2025" veya "15 Jan 2025"
    def _replace_day_month_year(m: re.Match) -> str:
        day = int(m.group(1))
        m_str = m.group(2).lower()
        month = _MONTH_MAP.get(m_str, 1)
        year = int(m.group(3)) if m.group(3) else datetime.now().year
        return _format_single_date(day, month, year)

    text = re.sub(
        rf"\b(\d{{1,2}})\s+({month_pattern})\s*(20\d{{2}}|\d{{2}})?\b",
        _replace_day_month_year,
        text,
        flags=re.I,
    )

    # 2. "January 15, 2025" veya "Ocak 15 2025"
    def _replace_month_day_year(m: re.Match) -> str:
        m_str = m.group(1).lower()
        month = _MONTH_MAP.get(m_str, 1)
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else datetime.now().year
        return _format_single_date(day, month, year)

    text = re.sub(
        rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(20\d{{2}}|\d{{2}})?\b",
        _replace_month_day_year,
        text,
        flags=re.I,
    )

    # 3. "DD.MM.YYYY" veya "DD/MM/YYYY" (Örn: 15.01.2025 veya 15/01/2025)
    def _replace_slash_dot_date(m: re.Match) -> str:
        p1 = int(m.group(1))
        p2 = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else datetime.now().year

        # p1 > 12 ise p1 kesin gündür
        if p1 > 12:
            day, month = p1, p2
        elif p2 > 12:
            month, day = p1, p2
        else:
            # Standart olarak Türkçe/Avrupa sıralaması: GG/AA/YYYY
            day, month = p1, p2

        return _format_single_date(day, month, year)

    text = re.sub(
        r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2}|\d{2})\b",
        _replace_slash_dot_date,
        text,
    )

    return text
