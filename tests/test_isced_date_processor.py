"""Unit tests for ISCED mapping, YYYY-MM-DD date normalization, and processor."""

import pytest
from src.extractors.isced_mapper import map_to_isced_code
from src.extractors.date_formatter import normalize_date_to_iso


def test_isced_mapping_computer_science():
    res = map_to_isced_code("Master of Science in Computer Science")
    assert "0613" in res
    assert "Software and applications" in res


def test_isced_mapping_mba():
    res = map_to_isced_code("MBA Business Administration")
    assert "0413" in res
    assert "Management" in res


def test_isced_mapping_medicine():
    res = map_to_isced_code("Doctor of Medicine MD")
    assert "0912" in res
    assert "Medicine" in res


def test_date_formatting_turkish():
    assert normalize_date_to_iso("15 Ocak 2025") == "2025-01-15"
    assert normalize_date_to_iso("1 Aralık 2025") == "2025-12-01"


def test_date_formatting_english():
    assert normalize_date_to_iso("January 15, 2025") == "2025-01-15"
    assert normalize_date_to_iso("15 Jan 2025") == "2025-01-15"


def test_date_formatting_numeric():
    assert normalize_date_to_iso("15/01/2025") == "2025-01-15"
    assert normalize_date_to_iso("2025-01-15") == "2025-01-15"


def test_date_formatting_rolling():
    assert normalize_date_to_iso("Rolling Admission") == "Rolling Admission"
