"""Ücret çıkarım modülü — yıllık, dönemlik, kredi başı, toplam.

Matematiksel tahmin YASAK: yalnızca açık kayıtlanan değerleri yaz.
Kaynak yalnızca kredi başı veriyorsa yıllık hesaplama yapma.
"""

from __future__ import annotations

import re
from typing import Optional

from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection

# Para birimi çıkarma
_CURRENCY_RE = re.compile(
    r"(?:"
    r"\$\s*([\d,]+(?:\.\d{2})?)"                        # $1,234 veya $1234.00
    r"|"
    r"([\d,]+(?:\.\d{2})?)\s*(?:USD|CAD|AUD|GBP)\b"    # 1234 USD
    r"|"
    r"USD\s*([\d,]+(?:\.\d{2})?)"                       # USD 1234
    r")",
    re.I,
)

# Yıllık bağlam
_ANNUAL_CONTEXT = re.compile(
    r"\b(per\s+year|annual(ly)?|per\s+academic\s+year|yearly|full[- ]year)\b", re.I
)

# Dönemlik bağlam
_SEMESTER_CONTEXT = re.compile(
    r"\b(per\s+semester|per\s+term|semester(ly)?|term(ly)?)\b", re.I
)

# Kredi başı bağlam
_CREDIT_CONTEXT = re.compile(
    r"\b(per\s+credit(?:\s+hour)?|per\s+unit|credit\s+hour)\b", re.I
)

# Toplam program ücreti
_TOTAL_CONTEXT = re.compile(
    r"\b(total\s+(?:program|degree|tuition)\s+cost|program\s+total|"
    r"full\s+program\s+tuition)\b",
    re.I,
)

# Başvuru ücreti bağlamı
_APPLICATION_FEE = re.compile(
    r"\b(application\s+fee|application\s+cost)\b", re.I
)

# Yıl bilgisi
_YEAR_RE = re.compile(r"\b(20\d{2})\s*[-–]\s*(?:20\d{2}|\d{2})\b")


def _extract_amount(text: str) -> Optional[float]:
    """Metinden para tutarını çıkar."""
    m = _CURRENCY_RE.search(text)
    if not m:
        return None
    val_str = next(g for g in m.groups() if g is not None)
    try:
        return float(val_str.replace(",", ""))
    except ValueError:
        return None


def extract_annual_tuition(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Yıllık öğrenim ücretini çıkar.

    Yalnızca açıkça 'per year' veya 'annual' yazanları döndür.
    Kredi başı değerden hesaplama YAPMA.
    """
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"

        # Başvuru ücreti bağlamını atla
        if _APPLICATION_FEE.search(section.heading or ""):
            continue

        if _ANNUAL_CONTEXT.search(combined):
            amount = _extract_amount(combined)
            if amount and 100 < amount < 200_000:
                # Yıl bilgisi varsa ekle
                year_m = _YEAR_RE.search(combined)
                year_note = f" ({year_m.group(0)})" if year_m else ""

                m = _CURRENCY_RE.search(combined)
                if m:
                    evidence = combined[max(0, m.start()-100):m.end()+100].strip()
                else:
                    evidence = ""

                return ExtractedField(
                    value=f"{amount:,.0f} USD{year_note}",
                    source_url=source_url,
                    evidence=evidence[:400],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="university",
                    confidence=0.92,
                    is_explicit=True,
                    notes="Yıllık ücret",
                )

    # Yıllık bağlam yoksa dönemlik de yok — kredi başı veya bilinmeyen
    # Kredi başı varsa olduğu gibi yaz
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        if _APPLICATION_FEE.search(section.heading or ""):
            continue
        if _CREDIT_CONTEXT.search(combined):
            amount = _extract_amount(combined)
            if amount and 10 < amount < 5_000:
                year_m = _YEAR_RE.search(combined)
                year_note = f" ({year_m.group(0)})" if year_m else ""
                return ExtractedField(
                    value=f"{amount:,.0f} USD/kredi{year_note}",
                    source_url=source_url,
                    evidence=combined[:300],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="university",
                    confidence=0.85,
                    is_explicit=True,
                    notes="Kredi başı ücret (yıllık hesaplanmadı)",
                )

    return ExtractedField()


def extract_application_fee(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Başvuru ücretini çıkar."""
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        if not _APPLICATION_FEE.search(combined):
            continue
        amount = _extract_amount(combined)
        if amount and 0 < amount < 1_000:
            m = _CURRENCY_RE.search(combined)
            evidence = combined[max(0, m.start()-80):m.end()+80].strip() if m else ""
            return ExtractedField(
                value=f"{amount:,.0f} USD",
                source_url=source_url,
                evidence=evidence[:400],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=0.93,
                is_explicit=True,
            )
    return ExtractedField()
