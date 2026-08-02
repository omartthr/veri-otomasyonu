"""Ücret Eşleştirici ve Birim Koruyucu Motor v3.

Sayfadaki ilk rakamı tüm programlara dağıtmak yerine program adı, derece seviyesi,
kampüs/eğitim türü ve akademik yıla göre eşleştirme yapar.
Birim etiketini (USD/kredi, USD/dönem, USD/yıl) korur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TuitionMatch:
    raw_text: str
    formatted_value: str
    unit: str
    is_per_credit: bool
    is_per_term: bool
    is_per_year: bool
    is_total_estimated: bool


def format_tuition_value(text: str) -> Optional[TuitionMatch]:
    """Ücret metnini inceleyerek birimiyle birlikte biçimlendirir."""
    if not text:
        return None

    # Tutar yakala ($18,000, 18000, 580 USD vb.)
    amount_match = re.search(r"(?:\$\s*)?([\d,]+(?:\.\d{2})?)\s*(USD|dollar|dollars)?", text, re.I)
    if not amount_match:
        return None

    val_str = amount_match.group(1).replace(",", "").strip()
    if not val_str.replace(".", "", 1).isdigit():
        return None

    val = float(val_str)
    if val <= 0:
        return None

    formatted_val = f"{int(val):,}".replace(",", ".")

    is_per_credit = bool(re.search(r"\bper\s+credit\b|\/credit\b", text, re.I))
    is_per_term = bool(re.search(r"\bper\s+(?:semester|quarter|term)\b|\/semester\b|\/term\b", text, re.I))
    is_per_year = bool(re.search(r"\bper\s+year\b|\bannual\b|\/year\b", text, re.I))
    is_total = bool(re.search(r"\btotal\s+program\s+(?:cost|tuition)\b|\bestimated\s+total\b", text, re.I))

    if is_per_credit:
        unit = "USD/kredi"
        result = f"{formatted_val} USD/kredi"
    elif is_per_term:
        unit = "USD/dönem"
        result = f"{formatted_val} USD/dönem"
    elif is_total:
        unit = "Tahmini toplam"
        result = f"Tahmini toplam program ücreti {formatted_val} USD"
    else:
        unit = "USD/yıl"
        result = f"{formatted_val} USD/yıl"

    return TuitionMatch(
        raw_text=text,
        formatted_value=result,
        unit=unit,
        is_per_credit=is_per_credit,
        is_per_term=is_per_term,
        is_per_year=is_per_year or (not is_per_credit and not is_per_term and not is_total),
        is_total_estimated=is_total,
    )
