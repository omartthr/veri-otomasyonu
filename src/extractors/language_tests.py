"""Dil sınavı çıkarım modülü — IELTS, TOEFL, Duolingo.

TOEFL iBT / PBT / CBT ayrımı yapar.
Muafiyet koşullarını tespit eder.
"""

from __future__ import annotations

import re
from typing import Optional

from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection


# ── IELTS ──
_IELTS_PATTERNS = [
    re.compile(r"ielts\s*(?:overall\s*)?(?:score\s*(?:of\s*)?)?(?:band\s*)?([\d]+\.?\d*)\s*(?:or\s+(?:higher|above))?", re.I),
    re.compile(r"ielts\s*[:\-=]\s*([\d]+\.?\d*)", re.I),
    re.compile(r"minimum\s+ielts\s+(?:of\s+)?([\d]+\.?\d*)", re.I),
]

# ── TOEFL iBT ──
_TOEFL_IBT_PATTERNS = [
    re.compile(r"toefl\s+ibt\s*(?:score\s*(?:of\s*)?)?[:\-=]?\s*([\d]{2,3})\s*(?:or\s+(?:higher|above))?", re.I),
    re.compile(r"toefl\s*(?:internet[- ]based|ibt)\s*[:\-=]?\s*([\d]{2,3})", re.I),
    re.compile(r"minimum\s+toefl\s+(?:ibt\s+)?(?:score\s+of\s+)?([\d]{2,3})", re.I),
]

# ── TOEFL (genel — PBT/CBT dışındaysa iBT sayılır) ──
_TOEFL_GENERIC_PATTERNS = [
    re.compile(r"toefl\s*[:\-=]\s*([\d]{2,3})", re.I),
    re.compile(r"toefl\s+score\s+of\s+([\d]{2,3})", re.I),
]

# ── Duolingo ──
_DUOLINGO_PATTERNS = [
    re.compile(r"duolingo\s+(?:english\s+test\s+)?(?:score\s*(?:of\s*)?)?[:\-=]?\s*([\d]{2,3})\s*(?:or\s+(?:higher|above))?", re.I),
    re.compile(r"minimum\s+duolingo\s+(?:score\s+of\s+)?([\d]{2,3})", re.I),
    re.compile(r"det\s*[:\-=]\s*([\d]{2,3})", re.I),  # DET = Duolingo English Test
]

# PBT ve CBT varlığını tespit et (generic TOEFL'u filtrelemek için)
_TOEFL_PBT = re.compile(r"toefl\s*(?:pbt|paper[- ]based)", re.I)
_TOEFL_CBT = re.compile(r"toefl\s*(?:cbt|computer[- ]based)", re.I)

# Muafiyet kalıpları
_EXEMPTION_PATTERNS = re.compile(
    r"(exempt|waived|not required|may be waived|native|first language|"
    r"citizen.{0,30}english|english.{0,30}citizen|"
    r"degree.{0,30}english.{0,30}medium|english.{0,30}medium.{0,30}instruct)",
    re.I,
)

_CONFIDENCE_EXPLICIT = 0.93
_CONFIDENCE_IMPLICIT = 0.80


def _extract_score(patterns: list, text: str, min_val: float, max_val: float) -> Optional[float]:
    """Verilen regex listesinden sayısal skor çıkar."""
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            try:
                val = float(m.group(1))
                if min_val <= val <= max_val:
                    return val
            except (ValueError, IndexError):
                pass
    return None


def extract_ielts(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """IELTS minimum skor çıkar."""
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        score = _extract_score(_IELTS_PATTERNS, combined, 4.0, 9.0)
        if score is not None:
            # Kanıt kesiti
            m = next(
                (pat.search(combined) for pat in _IELTS_PATTERNS if pat.search(combined)),
                None,
            )
            evidence = combined[max(0, m.start()-80):m.end()+80].strip() if m else ""
            return ExtractedField(
                value=score,
                source_url=source_url,
                evidence=evidence[:400],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=_CONFIDENCE_EXPLICIT,
                is_explicit=True,
            )
    return ExtractedField()


def extract_toefl(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """TOEFL iBT minimum skor çıkar (PBT/CBT'yi karıştırma)."""
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"

        # Önce açık iBT kalıplarını dene
        score = _extract_score(_TOEFL_IBT_PATTERNS, combined, 0, 120)
        if score is not None:
            m = next(
                (pat.search(combined) for pat in _TOEFL_IBT_PATTERNS if pat.search(combined)),
                None,
            )
            evidence = combined[max(0, m.start()-80):m.end()+80].strip() if m else ""
            return ExtractedField(
                value=score,
                source_url=source_url,
                evidence=evidence[:400],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=_CONFIDENCE_EXPLICIT,
                is_explicit=True,
                notes="TOEFL iBT",
            )

        # Genel TOEFL — PBT/CBT değilse kabul et
        if not _TOEFL_PBT.search(combined) and not _TOEFL_CBT.search(combined):
            score = _extract_score(_TOEFL_GENERIC_PATTERNS, combined, 0, 120)
            if score is not None:
                # 300+ muhtemelen PBT (500-677 arası), 0-120 iBT
                if score > 120:
                    continue  # PBT skoru — atla
                m = next(
                    (pat.search(combined) for pat in _TOEFL_GENERIC_PATTERNS if pat.search(combined)),
                    None,
                )
                evidence = combined[max(0, m.start()-80):m.end()+80].strip() if m else ""
                return ExtractedField(
                    value=score,
                    source_url=source_url,
                    evidence=evidence[:400],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="university",
                    confidence=_CONFIDENCE_IMPLICIT,
                    is_explicit=False,
                    notes="TOEFL (tür belirtilmemiş, muhtemelen iBT)",
                )

    return ExtractedField()


def extract_duolingo(
    sections: list[ContentSection],
    source_url: str = "",
) -> ExtractedField:
    """Duolingo English Test minimum skor çıkar."""
    for section in sections:
        combined = f"{section.heading or ''}\n{section.text}"
        score = _extract_score(_DUOLINGO_PATTERNS, combined, 10, 160)
        if score is not None:
            m = next(
                (pat.search(combined) for pat in _DUOLINGO_PATTERNS if pat.search(combined)),
                None,
            )
            evidence = combined[max(0, m.start()-80):m.end()+80].strip() if m else ""
            return ExtractedField(
                value=score,
                source_url=source_url,
                evidence=evidence[:400],
                source_type=section.source_type,
                page_number=section.page_number,
                scope="university",
                confidence=_CONFIDENCE_EXPLICIT,
                is_explicit=True,
            )
    return ExtractedField()
