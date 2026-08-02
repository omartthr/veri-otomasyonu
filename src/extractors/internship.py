"""Staj, co-op, exchange, çift diploma extractor."""

from __future__ import annotations

import re
from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection

_PATTERNS = {
    "internship": re.compile(r"\b(internship|practicum|field\s+placement)\b", re.I),
    "coop": re.compile(r"\bco[- ]?op(?:erative\s+education)?\b", re.I),
    "exchange": re.compile(r"\b(exchange\s+program|study\s+abroad|semester\s+abroad)\b", re.I),
    "dual_degree": re.compile(r"\b(dual\s+degree|double\s+degree|joint\s+degree)\b", re.I),
}

_AVAILABLE = re.compile(
    r"\b(available|offered|option|opportunity|partner|participate|included|integrated)\b",
    re.I,
)
_NOT_AVAILABLE = re.compile(
    r"\b(not\s+(?:available|offered)|no\s+(?:internship|co-?op|exchange))\b",
    re.I,
)


def extract_internship(sections: list[ContentSection], source_url: str = "") -> ExtractedField:
    return _extract_field("internship", sections, source_url)

def extract_coop(sections: list[ContentSection], source_url: str = "") -> ExtractedField:
    return _extract_field("coop", sections, source_url)

def extract_exchange(sections: list[ContentSection], source_url: str = "") -> ExtractedField:
    return _extract_field("exchange", sections, source_url)

def extract_dual_degree(sections: list[ContentSection], source_url: str = "") -> ExtractedField:
    return _extract_field("dual_degree", sections, source_url)


def _extract_field(
    field: str,
    sections: list[ContentSection],
    source_url: str,
) -> ExtractedField:
    pattern = _PATTERNS[field]
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        m = pattern.search(combined)
        if not m:
            continue
        ctx = combined[max(0, m.start()-100):m.end()+100]
        if _NOT_AVAILABLE.search(ctx):
            return ExtractedField(
                value=False, source_url=source_url,
                evidence=ctx[:300], source_type=section.source_type,
                page_number=section.page_number, confidence=0.85, is_explicit=True,
            )
        if _AVAILABLE.search(ctx):
            return ExtractedField(
                value=True, source_url=source_url,
                evidence=ctx[:300], source_type=section.source_type,
                page_number=section.page_number, confidence=0.85, is_explicit=True,
            )
    return ExtractedField()
