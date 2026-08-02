"""Sütun alias tespiti testleri."""
import pytest
from src.program_pipeline.source_excel_reader import _detect_column_map

def test_exact_headers():
    headers = ["Üniversite ID", "Üniversite Adı", "Web Sitesi", "Program URL", "Kabul Şartları URL"]
    col_map = _detect_column_map(headers)
    assert col_map["university_name"] == 1
    assert col_map["university_id"] == 0
    assert col_map["program_url"] == 3

def test_english_headers():
    headers = ["University ID", "University Name", "Website", "Programs URL", "Admission URL"]
    col_map = _detect_column_map(headers)
    assert col_map["university_name"] == 1
    assert col_map["program_url"] == 3

def test_missing_name_col():
    headers = ["Some Col", "Other Col"]
    col_map = _detect_column_map(headers)
    assert "university_name" not in col_map

def test_case_insensitive():
    headers = ["üniversite adı", "program url"]
    col_map = _detect_column_map(headers)
    assert col_map.get("university_name") == 0
