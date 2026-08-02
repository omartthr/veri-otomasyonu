"""Dil sınavı extractor testleri."""
import pytest
from src.program_pipeline.content_sections import ContentSection
from src.extractors.language_tests import extract_ielts, extract_toefl, extract_duolingo

URL = "https://example.edu/admissions"

def _s(text: str, heading: str = "Language Requirements") -> ContentSection:
    return ContentSection(heading=heading, text=text, source_url=URL)

# ── IELTS ──

def test_ielts_score():
    field = extract_ielts([_s("IELTS overall score of 6.5 or higher is required.")])
    assert field.value == 6.5

def test_ielts_colon_format():
    field = extract_ielts([_s("Minimum IELTS: 7.0")])
    assert field.value == 7.0

def test_ielts_band():
    field = extract_ielts([_s("IELTS band 6.0")])
    assert field.value == 6.0

# ── TOEFL ──

def test_toefl_ibt_explicit():
    field = extract_toefl([_s("TOEFL iBT score of 92 or above.")])
    assert field.value == 92.0

def test_toefl_internet_based():
    field = extract_toefl([_s("TOEFL Internet-based: 100")])
    assert field.value == 100.0

def test_toefl_generic():
    field = extract_toefl([_s("Minimum TOEFL score of 85.")])
    assert field.value == 85.0

def test_toefl_pbt_skipped():
    # PBT skoru 550 — iBT 0-120 dışı, atlanmalı
    field = extract_toefl([_s("TOEFL PBT: 550")])
    assert field.value is None or field.confidence < 0.85

# ── Duolingo ──

def test_duolingo_score():
    field = extract_duolingo([_s("Duolingo English Test score of 115 or higher.")])
    assert field.value == 115.0

def test_det_abbreviation():
    field = extract_duolingo([_s("DET: 110")])
    assert field.value == 110.0

# ── Boş ──

def test_no_language_test():
    field = extract_ielts([_s("Our programs are fully online.")])
    assert field.value is None
