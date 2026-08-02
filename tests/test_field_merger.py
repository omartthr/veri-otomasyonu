"""Field merger testleri."""
import pytest
from src.program_pipeline.models import ExtractedField
from src.program_pipeline.field_merger import merge_fields, merge_all_fields

def _field(value, confidence=0.90, scope="university", is_explicit=True):
    return ExtractedField(
        value=value, confidence=confidence, scope=scope,
        is_explicit=is_explicit, source_url="https://example.edu"
    )

# ── Temel öncelik ──

def test_program_over_general():
    prog = _field(3.0, confidence=0.90, scope="program")
    gen = _field(2.5, confidence=0.92, scope="university")
    result = merge_fields(prog, gen)
    # Program özel yüksek önceliğe sahip (scope bonus +0.15)
    assert result.value == 3.0

def test_general_wins_when_program_empty():
    prog = ExtractedField()
    gen = _field(2.5)
    result = merge_fields(prog, gen)
    assert result.value == 2.5

def test_both_empty():
    result = merge_fields(ExtractedField(), ExtractedField())
    assert result.value is None

def test_higher_confidence_wins():
    prog = _field(3.0, confidence=0.75, scope="university")
    gen = _field(2.5, confidence=0.95, scope="university")
    result = merge_fields(prog, gen)
    # Confidence farkı büyük, gen kazanmalı
    assert result.value == 2.5

def test_historical_penalty():
    gen_historical = ExtractedField(
        value=3.0, confidence=0.88, scope="university",
        is_historical=True, source_url="https://example.edu"
    )
    gen_fresh = _field(3.0, confidence=0.80)
    result = merge_fields(None, gen_historical)
    # Sadece historical var, yine de döndürmeli
    assert result.value == 3.0

# ── Toplu birleştirme ──

def test_merge_all_fields():
    prog_fields = {"GPA": _field(3.0, scope="program"), "IELTS": ExtractedField()}
    gen_fields = {"GPA": _field(2.5), "IELTS": _field(6.5), "TOEFL": _field(92)}
    merged = merge_all_fields(prog_fields, gen_fields)
    assert merged["GPA"].value == 3.0
    assert merged["IELTS"].value == 6.5
    assert merged["TOEFL"].value == 92
