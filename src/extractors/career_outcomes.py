"""Mezun çıktıları extractor — istihdam oranı, ortalama maaş, meslek listesi."""

from __future__ import annotations

import re
from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection

_EMPLOYMENT_RATE = re.compile(
    r"(\d{2,3})\s*%\s*(?:of\s+(?:our\s+)?graduates?|employment\s+rate|"
    r"employed\s+within\s+\d+\s+(?:month|year))",
    re.I,
)

_SALARY = re.compile(
    r"(?:average|median|starting)\s+(?:salary|wage|earnings?)\s*(?:of\s+)?"
    r"(?:\$\s?[\d,]+|[\d,]+\s*(?:USD|dollars?))",
    re.I,
)

_CAREER_SECTION = re.compile(
    r"\b(career|employment|job\s+placement|alumni\s+outcomes?|graduate\s+outcomes?|"
    r"career\s+outcomes?|job\s+prospects?)\b",
    re.I,
)


def extract_employment_rate(sections: list[ContentSection], source_url: str = "") -> ExtractedField:
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        if not _CAREER_SECTION.search(combined):
            continue
        m = _EMPLOYMENT_RATE.search(combined)
        if m:
            val = int(m.group(1))
            if 0 <= val <= 100:
                evidence = combined[max(0, m.start()-60):m.end()+80].strip()
                return ExtractedField(
                    value=f"%{val}", source_url=source_url,
                    evidence=evidence[:300], source_type=section.source_type,
                    page_number=section.page_number, confidence=0.85, is_explicit=True,
                )
    return ExtractedField()


def extract_average_salary(sections: list[ContentSection], source_url: str = "") -> ExtractedField:
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        if not _CAREER_SECTION.search(combined):
            continue
        m = _SALARY.search(combined)
        if m:
            evidence = combined[max(0, m.start()-60):m.end()+80].strip()
            return ExtractedField(
                value=m.group(0).strip(), source_url=source_url,
                evidence=evidence[:300], source_type=section.source_type,
                page_number=section.page_number, confidence=0.82, is_explicit=True,
            )
    return ExtractedField()
