"""Boş hücre kuralı testleri — value=None → hücre boş olmalı."""
import pytest
from src.program_pipeline.models import ExtractedField
from src.program_pipeline.excel_writer import _cell_value

def test_none_value():
    field = ExtractedField(value=None)
    assert _cell_value(field) is None

def test_literal_none_string():
    field = ExtractedField(value="None")
    assert _cell_value(field) is None

def test_literal_na_string():
    field = ExtractedField(value="N/A")
    assert _cell_value(field) is None

def test_empty_string():
    field = ExtractedField(value="")
    assert _cell_value(field) is None

def test_valid_gpa():
    field = ExtractedField(value=3.0)
    assert _cell_value(field) == 3.0

def test_bool_true():
    field = ExtractedField(value=True)
    assert _cell_value(field) == "Evet"

def test_bool_false():
    field = ExtractedField(value=False)
    assert _cell_value(field) == "Hayır"

def test_string_value():
    field = ExtractedField(value="IELTS 6.5")
    assert _cell_value(field) == "IELTS 6.5"

def test_dash_sentinel():
    field = ExtractedField(value="—")
    assert _cell_value(field) is None
