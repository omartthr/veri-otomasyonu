"""Başvuru belgeleri extractor — required vs. optional ayrımı."""

from __future__ import annotations

import re
from typing import Optional

from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection

_SECTION_MARKERS = re.compile(
    r"\b(required\s+materials?|required\s+documents?|what\s+(?:we|you)\s+need|"
    r"application\s+checklist|how\s+to\s+apply|application\s+requirements?|"
    r"materials?\s+required)\b",
    re.I,
)

# Required/mandatory göstergeler
_REQUIRED_MARKERS = re.compile(
    r"^\s*[\*\-•–]\s*|^\s*\d+\.\s*|required|mandatory|must|submit",
    re.I | re.MULTILINE,
)

# Optional göstergeler
_OPTIONAL_MARKERS = re.compile(r"\b(optional|may|if\s+applicable|recommended)\b", re.I)

# Bilinen belge tipleri
_DOCUMENT_TYPES = [
    "official transcript", "unofficial transcript", "transcript",
    "letter of recommendation", "recommendation letter",
    "personal statement", "statement of purpose", "essay",
    "resume", "curriculum vitae", "cv",
    "test scores", "gre", "gmat",
    "writing sample",
    "proof of english proficiency",
    "financial documents",
    "application form",
]


def extract_application_documents(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Zorunlu başvuru belgelerini listele."""
    for section in sections:
        if not _SECTION_MARKERS.search(f"{section.heading or ''}\n{section.text[:100]}"):
            continue

        text = section.text
        required_docs: list[str] = []

        lines = text.split("\n")
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            if _OPTIONAL_MARKERS.search(line_clean):
                continue
            if any(doc.lower() in line_clean.lower() for doc in _DOCUMENT_TYPES):
                doc_text = line_clean.lstrip("•*-–1234567890. ")
                if doc_text and doc_text not in required_docs:
                    required_docs.append(doc_text[:80])

        if required_docs:
            return ExtractedField(
                value="; ".join(required_docs[:10]),
                source_url=source_url,
                evidence=text[:500],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=0.87,
                is_explicit=True,
            )

    return ExtractedField()
