"""Eğitim süresi extractor — 3 katmanlı tespit.

Tier 1: Derece seviyesiyle birlikte yıl ifadesi ("4-year bachelor's")
Tier 2: Bağlam cümlesiyle ("complete the program in 2 years")
Tier 3: Kredi saatinden tahmin ("120 credit hours" → 4 yıl)
"""

from __future__ import annotations

import re
from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection


# Tier 1: Derece terimi + yıl ifadesi → çok güçlü sinyal
_TIER1_DEGREE_YEAR = re.compile(
    r"(?:"
    r"(?:four|4)[- ]year\s+(?:bachelor|undergraduate|baccalaureate)"
    r"|(?:two|2)[- ]year\s+(?:associate|community\s+college)"
    r"|(?:one|1)[- ]year\s+(?:master|graduate\s+certificate|postgrad)"
    r"|(?:two|2)[- ]year\s+(?:master|m\.?s\.?|m\.?a\.?)"
    r"|(?:three|3)[- ]year\s+(?:bachelor|law|llb)"
    r"|\b(\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)\s*-?\s*year\b"
    r"\s+(?:bachelor|master|associate|doctorate|doctoral|phd|graduate|undergraduate)\b"
    r")",
    re.I,
)

# Yıl değerini çeken basit kalıp
_YEAR_VALUE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[-–]\s*(\d+(?:\.\d+)?))?\s*year[s]?",
    re.I,
)

# Tier 2: Bağlam cümlesiyle birlikte yıl/söm/kredi ifadesi
_TIER2_CONTEXT = re.compile(
    r"\b(program\s+(?:length|duration)|complete.{0,25}program|degree\s+(?:requires?|takes?|length)|"
    r"(?:minimum|total)\s+(?:of\s+)?\d+\s+(?:year|semester|credit)|"
    r"designed\s+to\s+be\s+complet|finish\s+in\s+\d|"
    r"typical(?:ly)?\s+(?:complet|tak)|can\s+be\s+complet|takes?\s+\d+\s+year)\b",
    re.I,
)

_TIER2_YEAR_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[-–]\s*(\d+(?:\.\d+)?))?\s*year[s]?(?:\s+to\s+complete)?",
    re.I,
)
_TIER2_SEM_PATTERN = re.compile(r"(\d+)\s*semester[s]?", re.I)

# Tier 3: Kredi saatinden tahmin (120 → 4 yıl, 60 → 2 yıl, 30 → 1 yıl)
_CREDIT_HOUR_PATTERN = re.compile(
    r"(\d{2,3})\s*credit(?:\s*[-–]\s*(\d{2,3}))?\s*hour[s]?",
    re.I,
)
_CREDIT_CONTEXT = re.compile(
    r"\b(required|total|minimum|program\s+requires?|must\s+complete|for\s+(?:the\s+)?(?:degree|program))\b",
    re.I,
)

# İçerik bölümü filtresi — menü/footer'ı atla
_SKIP_SOURCE_TYPES = {"json_ld", "menu", "footer", "nav"}


def _format_years(low: float, high: float | None = None) -> str:
    """Yıl değerlerini Idaho formatında döndür: '2 yıl', '4-5 yıl'."""
    if high and abs(high - low) > 0.1:
        lo_s = str(int(low)) if low == int(low) else str(low)
        hi_s = str(int(high)) if high == int(high) else str(high)
        return f"{lo_s}-{hi_s} yıl"
    lo_s = str(int(low)) if low == int(low) else str(low)
    return f"{lo_s} yıl"


def _credits_to_years(credits: int) -> str | None:
    """Kredi saatinden tipik süreyi tahmin et."""
    if credits >= 110:
        return "4 yıl"
    elif credits >= 90:
        return "3-4 yıl"
    elif credits >= 55:
        return "2 yıl"
    elif credits >= 25:
        return "1-2 yıl"
    return None


def extract_duration(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Program süresini 3 katmanlı yaklaşımla çıkar.

    Tier 1 (confidence=0.93): Derece terimi + yıl → en güçlü
    Tier 2 (confidence=0.88): Bağlam cümlesi + yıl/söm
    Tier 3 (confidence=0.78): Kredi saatinden tahmin
    """
    best: ExtractedField | None = None

    for section in sections:
        if section.source_type in _SKIP_SOURCE_TYPES:
            continue
        combined = f"{section.heading or ''}\n{section.text}"

        # ── Tier 1: Derece + Yıl ──────────────────────────────────────
        m1 = _TIER1_DEGREE_YEAR.search(combined)
        if m1:
            yr = _YEAR_VALUE.search(m1.group(0))
            if yr:
                low = float(yr.group(1))
                high = float(yr.group(2)) if yr.group(2) else None
                value = _format_years(low, high)
                evidence = combined[max(0, m1.start() - 60):m1.end() + 60].strip()
                candidate = ExtractedField(
                    value=value,
                    source_url=source_url,
                    evidence=evidence[:400],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="program",
                    confidence=0.93,
                    is_explicit=True,
                )
                if best is None or candidate.confidence > best.confidence:
                    best = candidate
                continue  # Tier 1 bulundu, Tier 2/3'e geçme

        # ── Tier 2: Bağlam + Yıl/Söm ─────────────────────────────────
        if _TIER2_CONTEXT.search(combined):
            yr2 = _TIER2_YEAR_PATTERN.search(combined)
            if yr2:
                low = float(yr2.group(1))
                high = float(yr2.group(2)) if yr2.group(2) else None
                value = _format_years(low, high)
                evidence = combined[max(0, yr2.start() - 80):yr2.end() + 80].strip()
                candidate = ExtractedField(
                    value=value,
                    source_url=source_url,
                    evidence=evidence[:400],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="program",
                    confidence=0.88,
                    is_explicit=True,
                )
                if best is None or candidate.confidence > best.confidence:
                    best = candidate
                continue

            sem2 = _TIER2_SEM_PATTERN.search(combined)
            if sem2:
                semesters = int(sem2.group(1))
                years = semesters / 2
                value = _format_years(years)
                evidence = combined[max(0, sem2.start() - 80):sem2.end() + 80].strip()
                candidate = ExtractedField(
                    value=value,
                    source_url=source_url,
                    evidence=evidence[:400],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="program",
                    confidence=0.86,
                    is_explicit=True,
                )
                if best is None or candidate.confidence > best.confidence:
                    best = candidate
                continue

        # ── Tier 3: Kredi Saatinden Tahmin ───────────────────────────
        if _CREDIT_CONTEXT.search(combined):
            cr = _CREDIT_HOUR_PATTERN.search(combined)
            if cr:
                credits = int(cr.group(1))
                year_estimate = _credits_to_years(credits)
                if year_estimate:
                    evidence = combined[max(0, cr.start() - 60):cr.end() + 60].strip()
                    candidate = ExtractedField(
                        value=year_estimate,
                        source_url=source_url,
                        evidence=f"{credits} credit hour → {evidence[:200]}",
                        source_type=section.source_type,
                        page_number=section.page_number,
                        scope="program",
                        confidence=0.78,
                        is_explicit=False,
                        notes=f"{credits} kredi saatinden tahminen hesaplandı",
                    )
                    if best is None or candidate.confidence > best.confidence:
                        best = candidate

    return best or ExtractedField()
