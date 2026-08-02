"""Ücret extractor testleri."""
import pytest
from src.program_pipeline.content_sections import ContentSection
from src.extractors.tuition import extract_annual_tuition, extract_application_fee

URL = "https://example.edu/tuition"

def _s(text: str, heading: str = "") -> ContentSection:
    return ContentSection(heading=heading, text=text, source_url=URL)

# ── Yıllık ücret ──

def test_annual_tuition_dollar():
    field = extract_annual_tuition([_s(
        "Annual tuition is $32,000 per year for full-time students.",
        "Tuition and Fees"
    )])
    assert field.value is not None
    assert "32" in str(field.value)

def test_annual_tuition_usd():
    field = extract_annual_tuition([_s("Yearly tuition: 28,500 USD (2025-2026)", "Cost")])
    assert field.value is not None
    assert "2025" in str(field.value)

def test_credit_hour_not_calculated_to_annual():
    # Kredi başı ücret — yıllığa çevirilmemeli
    field = extract_annual_tuition([_s("$580 per credit hour.", "Tuition")])
    # Değer olabilir ama yıllık olarak sunulmamalı, "kredi" içermeli
    if field.value is not None:
        assert "kredi" in str(field.value).lower() or "credit" in str(field.value).lower()

# ── Başvuru ücreti ──

def test_application_fee_dollar():
    field = extract_application_fee([_s(
        "There is a non-refundable application fee of $40.", "Apply Now"
    )])
    assert field.value is not None
    assert "40" in str(field.value)

def test_application_fee_usd():
    field = extract_application_fee([_s("Application cost: 50 USD", "Application Fee")])
    assert field.value is not None
    assert "50" in str(field.value)

def test_no_tuition():
    field = extract_annual_tuition([_s("We offer a world-class education.", "About")])
    assert field.value is None
