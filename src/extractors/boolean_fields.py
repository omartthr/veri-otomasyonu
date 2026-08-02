"""Boolean gereksinim çıkarım modülü.

Portfolyo, mülakat, CV, essay, video başvuru vb. için
True/False/None değerleri üretir.

KURAL: Yalnızca açıkça "required" yazıyorsa True.
Belirsiz, koşullu veya "may be requested" → None (boş hücre).
"""

from __future__ import annotations

import re
from typing import Optional

from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection

# Zorunluluk ifadeleri
_REQUIRED = re.compile(
    r"\b(required|mandatory|must\s+submit|must\s+provide|must\s+include|"
    r"is\s+required|are\s+required|will\s+be\s+required)\b",
    re.I,
)

# Koşullu/opsiyonel ifadeler
_OPTIONAL = re.compile(
    r"\b(optional|may\s+be|encouraged|recommended|if\s+applicable|"
    r"when\s+available|as\s+needed|upon\s+request|at\s+the\s+discretion)\b",
    re.I,
)

# Yokluk ifadeleri
_NOT_REQUIRED = re.compile(
    r"\b(not\s+required|no\s+(?:portfolio|interview|essay|cv|resume|video)|"
    r"waived|do\s+not\s+require)\b",
    re.I,
)

# Alan kalıpları
_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "portfolio": re.compile(r"\bportfolio\b", re.I),
    "interview": re.compile(r"\b(interview|personal\s+interview)\b", re.I),
    "essay": re.compile(r"\b(essay|personal\s+statement|statement\s+of\s+purpose|"
                        r"writing\s+sample)\b", re.I),
    "cv": re.compile(r"\b(curriculum\s+vitae|cv|resume|résumé)\b", re.I),
    "video": re.compile(r"\b(video\s+(?:essay|response|submission|interview|statement))\b", re.I),
    "reference": re.compile(
        r"\b(letter\s+of\s+recommendation|recommendation\s+letter|"
        r"reference\s+letter|letters?\s+of\s+reference)\b",
        re.I,
    ),
    "reference_count": re.compile(
        r"(\d+)\s*(?:letters?\s+of\s+recommendation|recommendation\s+letters?|"
        r"reference\s+letters?)\b",
        re.I,
    ),
}


def _check_field(text: str, field_pattern: re.Pattern) -> Optional[bool]:
    """Alan varlığını kontrol et ve zorunluluk durumunu döndür."""
    # Alan metinde geçiyor mu?
    m = field_pattern.search(text)
    if not m:
        return None  # Hiç bahsedilmemiş

    # Alanın çevresindeki bağlam
    ctx_start = max(0, m.start() - 120)
    ctx_end = min(len(text), m.end() + 120)
    context = text[ctx_start:ctx_end]

    if _NOT_REQUIRED.search(context):
        return False

    if _REQUIRED.search(context):
        return True

    if _OPTIONAL.search(context):
        return None  # Opsiyonel → boş hücre

    return None  # Belirsiz → boş hücre


def _find_evidence(text: str, field_pattern: re.Pattern) -> str:
    """Alan için en iyi kanıt kesitini bul."""
    m = field_pattern.search(text)
    if not m:
        return ""
    return text[max(0, m.start()-80):min(len(text), m.end()+120)].strip()


def extract_boolean_field(
    field_name: str,
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Verilen alan adı için True/False/None döndür.

    Args:
        field_name: "portfolio", "interview", "essay", "cv", "video", "reference"
        sections: İçerik bölümleri
        source_url: Kaynak URL

    Returns:
        ExtractedField (value: True | False | None)
    """
    pattern = _FIELD_PATTERNS.get(field_name.lower())
    if not pattern:
        return ExtractedField()

    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        result = _check_field(combined, pattern)

        if result is True:
            evidence = _find_evidence(combined, pattern)
            return ExtractedField(
                value=True,
                source_url=source_url,
                evidence=evidence[:400],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=0.90,
                is_explicit=True,
            )
        elif result is False:
            evidence = _find_evidence(combined, pattern)
            return ExtractedField(
                value=False,
                source_url=source_url,
                evidence=evidence[:400],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=0.88,
                is_explicit=True,
            )

    return ExtractedField()  # Hiç bulunmadı → boş


def extract_reference_count(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Referans mektup sayısını çıkar.

    Sayı yazılmamışsa None döndür — tahmin etme.
    """
    count_pattern = _FIELD_PATTERNS["reference_count"]

    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        m = count_pattern.search(combined)
        if m:
            try:
                count = int(m.group(1))
                if 1 <= count <= 10:
                    evidence = combined[max(0, m.start()-60):m.end()+80].strip()
                    return ExtractedField(
                        value=count,
                        source_url=source_url,
                        evidence=evidence[:300],
                        source_type=section.source_type,
                        page_number=section.page_number,
                        scope="university",
                        confidence=0.92,
                        is_explicit=True,
                    )
            except ValueError:
                pass

    return ExtractedField()  # Sayı yoksa boş
