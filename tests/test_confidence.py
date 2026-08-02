"""Confidence modülü testleri."""
import pytest
from src.program_pipeline.models import ExtractedField
from src.program_pipeline.confidence import classify_confidence, adjust_confidence

def _field(confidence: float, scope: str = "university", value: object = 3.0):
    return ExtractedField(value=value, confidence=confidence, scope=scope)

# ── Sınıflandırma ──

def test_auto_write_above_threshold():
    assert classify_confidence(_field(0.90)) == "auto_write"

def test_needs_review_medium():
    assert classify_confidence(_field(0.70)) == "needs_review"

def test_skip_low():
    assert classify_confidence(_field(0.40)) == "skip"

def test_skip_none_value():
    assert classify_confidence(ExtractedField()) == "skip"

def test_custom_threshold():
    assert classify_confidence(_field(0.80), threshold=0.75) == "auto_write"
    assert classify_confidence(_field(0.80), threshold=0.90) == "needs_review"

# ── Ayarlama ──

def test_domain_penalty():
    field = _field(0.90)
    adjusted = adjust_confidence(field, is_official_domain=False)
    assert adjusted.confidence < 0.90

def test_evidence_penalty():
    field = _field(0.90)
    adjusted = adjust_confidence(field, evidence_verified=False)
    assert adjusted.confidence < 0.90

def test_program_scope_bonus():
    field = _field(0.85, scope="program")
    adjusted = adjust_confidence(field, is_program_scope=True)
    assert adjusted.confidence >= 0.85

def test_confidence_capped_at_1():
    field = _field(0.99)
    adjusted = adjust_confidence(field, is_program_scope=True)
    assert adjusted.confidence <= 1.0

def test_confidence_floor_0():
    field = _field(0.30)
    adjusted = adjust_confidence(
        field, is_official_domain=False, evidence_verified=False,
        is_recent_content=False
    )
    assert adjusted.confidence >= 0.0
