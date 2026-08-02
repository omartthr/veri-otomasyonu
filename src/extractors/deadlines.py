"""Son başvuru tarihi extractor."""

from __future__ import annotations

import re
from typing import Optional

from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection

# Ay isimleri
_MONTHS = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec"
)

# Tarih kalıpları
_DATE_PATTERNS = [
    # "January 15, 2025" veya "January 15"
    re.compile(rf"({_MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(20\d{{2}})?", re.I),
    # "15 January 2025"
    re.compile(rf"(\d{{1,2}})\s+({_MONTHS})\s*(20\d{{2}})?", re.I),
    # "MM/DD/YYYY" veya "MM/DD"
    re.compile(r"(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?"),
    # "rolling admission"
    re.compile(r"\brolling\s+(?:admission|basis|enrollment)\b", re.I),
    # "open enrollment"
    re.compile(r"\bopen\s+(?:enrollment|admission)\b", re.I),
]

_DEADLINE_CONTEXT = re.compile(
    r"\b(deadline|last\s+date|final\s+date|application\s+due|"
    r"submit\s+by|by\s+(?:the\s+)?deadline|closing\s+date|"
    r"applications?\s+(?:are\s+due|must\s+be\s+received))\b",
    re.I,
)

_SEMESTER_MAP = {
    "fall": "Sonbahar",
    "spring": "İlkbahar",
    "summer": "Yaz",
    "winter": "Kış",
}


def extract_application_deadline(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Son başvuru tarihini çıkar."""
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"

        if not _DEADLINE_CONTEXT.search(combined):
            continue

        # Rolling admission
        if re.search(r"\brolling\s+(?:admission|basis)\b", combined, re.I):
            return ExtractedField(
                value="Rolling Admission",
                source_url=source_url,
                evidence=combined[:300],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=0.88,
                is_explicit=True,
            )

        # Tarih bul
        for pattern in _DATE_PATTERNS[:2]:
            m = pattern.search(combined)
            if m:
                date_str = m.group(0).strip()
                evidence = combined[max(0, m.start()-80):m.end()+80].strip()
                return ExtractedField(
                    value=date_str,
                    source_url=source_url,
                    evidence=evidence[:400],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="university",
                    confidence=0.90,
                    is_explicit=True,
                )

    return ExtractedField()
