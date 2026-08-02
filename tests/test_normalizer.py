"""İsim normalizasyon testleri."""
import pytest
from src.program_pipeline.normalizer import normalize_for_comparison, similarity_score

def test_basic_normalization():
    # "seminary" suffix listesinde olduğu için kaldırılır
    norm = normalize_for_comparison("Phoenix Seminary")
    assert "phoenix" in norm

def test_suffix_removal():
    norm = normalize_for_comparison("Phoenix Seminary University")
    # "university" suffix'i kaldırılmalı
    assert "university" not in norm
    assert "phoenix" in norm

def test_unicode():
    # NFKD+ASCII encode sonucu: Ü→U, ü→u, ş→s vb. (trailing e korunabilir)
    norm = normalize_for_comparison("Üniversite")
    assert "universite" in norm or "universit" in norm

def test_similarity_exact():
    a = normalize_for_comparison("Harvard University")
    b = normalize_for_comparison("Harvard University")
    assert similarity_score(a, b) == 1.0

def test_similarity_partial():
    a = normalize_for_comparison("Harvard Divinity School")
    b = normalize_for_comparison("Harvard School of Divinity")
    score = similarity_score(a, b)
    assert score > 0.5

def test_similarity_empty():
    assert similarity_score("", "something") == 0.0
