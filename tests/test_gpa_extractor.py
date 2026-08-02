"""GPA extractor testleri."""
import pytest
from src.program_pipeline.content_sections import ContentSection
from src.extractors.gpa import extract_gpa

def _section(text: str, heading: str = "") -> ContentSection:
    return ContentSection(heading=heading, text=text, source_url="https://example.edu/test")

# ── Başarılı çıkarım ──

def test_minimum_gpa_explicit():
    sections = [_section(
        "Applicants must have a minimum GPA of 3.0 to be considered.",
        heading="Admission Requirements"
    )]
    field = extract_gpa(sections, source_url="https://example.edu")
    assert field.value == 3.0
    assert field.confidence >= 0.90

def test_gpa_of_pattern():
    sections = [_section("We require a GPA of 2.75 or higher.", heading="How to Apply")]
    field = extract_gpa(sections, source_url="https://example.edu")
    assert field.value == 2.75

def test_cumulative_gpa():
    sections = [_section("Cumulative GPA: 3.25", heading="Requirements")]
    field = extract_gpa(sections, source_url="https://example.edu")
    assert field.value == 3.25

def test_at_least_gpa():
    sections = [_section("You must have at least a 3.5 GPA to apply.", heading="Admission")]
    field = extract_gpa(sections, source_url="https://example.edu")
    assert field.value == 3.5

# ── Mezuniyet GPA'sı atlanmalı ──

def test_graduation_gpa_skipped():
    sections = [_section(
        "Students must maintain a GPA of 2.0 to graduate.",
        heading="Academic Standing"
    )]
    field = extract_gpa(sections, source_url="https://example.edu")
    # Mezuniyet bağlamı — atlanmalı
    assert field.value is None or field.confidence < 0.85

# ── Geçersiz değer ──

def test_gpa_out_of_range():
    sections = [_section("GPA of 5.0 is required.", heading="Requirements")]
    field = extract_gpa(sections, source_url="https://example.edu")
    assert field.value is None

# ── Boş içerik ──

def test_empty_sections():
    field = extract_gpa([], source_url="https://example.edu")
    assert field.value is None
