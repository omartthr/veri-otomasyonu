"""Şehir & Yaşam Rehberi — Excel Handler Testleri.

excel_handler.py'deki okuma/yazma fonksiyonlarını test eder.
"""

import pytest
from pathlib import Path

from src.city_livability_pipeline.excel_handler import (
    read_livability_sheet,
    read_all_sheets,
    SHEET_COLUMN_MAPS,
)


LIVABILITY_EXCEL = Path(__file__).resolve().parent.parent / "turkey_city_livability_review.xlsx"


@pytest.fixture
def excel_path():
    if not LIVABILITY_EXCEL.exists():
        pytest.skip("turkey_city_livability_review.xlsx bulunamadı")
    return LIVABILITY_EXCEL


class TestReadLivabilitySheet:
    def test_read_sehirler(self, excel_path):
        rows, header_map = read_livability_sheet(excel_path, "Sehirler")
        assert len(rows) == 87
        assert "Şehir ID" in header_map
        assert "İl Adı" in header_map
        assert rows[0].get("Şehir ID") is not None

    def test_read_ilceler(self, excel_path):
        rows, header_map = read_livability_sheet(excel_path, "Ilceler")
        assert len(rows) == 659
        assert "İlçe ID" in header_map

    def test_read_kampusler(self, excel_path):
        rows, header_map = read_livability_sheet(excel_path, "Kampusler")
        assert len(rows) == 846
        assert "Kampüs ID" in header_map

    def test_read_universiteler(self, excel_path):
        rows, header_map = read_livability_sheet(excel_path, "Universiteler")
        assert len(rows) == 229
        assert "Üniversite ID" in header_map

    def test_read_alan_rehberi(self, excel_path):
        rows, header_map = read_livability_sheet(excel_path, "AlanRehberi")
        assert len(rows) == 180
        assert "Sheet" in header_map

    def test_read_kaynaklar(self, excel_path):
        rows, header_map = read_livability_sheet(excel_path, "Kaynaklar")
        assert len(rows) == 22
        assert "source_key" in header_map

    def test_read_nonexistent_sheet(self, excel_path):
        with pytest.raises(ValueError, match="bulunamadı"):
            read_livability_sheet(excel_path, "OlmayanSayfa")

    def test_read_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            read_livability_sheet(Path("olmayan_dosya.xlsx"), "Sehirler")


class TestReadAllSheets:
    def test_reads_all_data_sheets(self, excel_path):
        result = read_all_sheets(excel_path)
        expected_sheets = {"Sehirler", "Ilceler", "Kampusler", "Universiteler"}
        assert expected_sheets.issubset(set(result.keys()))

    def test_each_sheet_has_rows_and_headers(self, excel_path):
        result = read_all_sheets(excel_path)
        for sheet_name, (rows, header_map) in result.items():
            assert len(rows) > 0, f"{sheet_name} boş"
            assert len(header_map) > 0, f"{sheet_name} başlık yok"


class TestColumnMaps:
    def test_all_sheets_have_audit_columns(self):
        for sheet_name, col_map in SHEET_COLUMN_MAPS.items():
            assert "Kaynak Türü" in col_map, f"{sheet_name} Kaynak Türü eksik"
            assert "_source_urls" in col_map, f"{sheet_name} _source_urls eksik"
            assert "_confidence" in col_map, f"{sheet_name} _confidence eksik"
            assert "_needs_review" in col_map, f"{sheet_name} _needs_review eksik"

    def test_sehirler_has_key_columns(self):
        cols = SHEET_COLUMN_MAPS["Sehirler"]
        assert "Şehir ID" in cols
        assert "Nüfus" in cols
        assert "İklim Tipi" in cols
        assert "Deprem Risk Bölgesi (1-5)" in cols
