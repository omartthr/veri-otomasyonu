"""Şehir & Yaşam Rehberi — Uçtan Uca (E2E) Pipeline Testi."""

import pytest
from pathlib import Path
from openpyxl import load_workbook

from src.city_livability_pipeline.pipeline_orchestrator import LivabilityPipelineOrchestrator


LIVABILITY_EXCEL = Path(__file__).resolve().parent.parent / "turkey_city_livability_review.xlsx"


@pytest.fixture
def excel_path():
    if not LIVABILITY_EXCEL.exists():
        pytest.skip("turkey_city_livability_review.xlsx bulunamadı")
    return LIVABILITY_EXCEL


class TestLivabilityE2EResearch:
    def test_run_full_pipeline_preserves_workbook(self, excel_path, tmp_path):
        orchestrator = LivabilityPipelineOrchestrator()
        result = orchestrator.run_all(
            input_path=excel_path,
            output_dir=tmp_path,
        )

        assert result.output_path is not None
        out_file = Path(result.output_path)
        assert out_file.exists()

        # Doğrulama: Tüm 4 sayfa başarıyla işlendi mi?
        assert "Universiteler" in result.sheet_results
        assert "Sehirler" in result.sheet_results
        assert "Ilceler" in result.sheet_results
        assert "Kampusler" in result.sheet_results

        assert result.total_cells_filled > 0
        assert result.total_errors == 0

        # openpyxl ile çıktıyı açıp incele
        wb = load_workbook(out_file, data_only=False)
        assert "Kapsam" in wb.sheetnames
        assert "Sehirler" in wb.sheetnames
        assert "Ilceler" in wb.sheetnames
        assert "Kampusler" in wb.sheetnames
        assert "Universiteler" in wb.sheetnames
        assert "AlanRehberi" in wb.sheetnames
        assert "Kaynaklar" in wb.sheetnames

        # Sehirler sayfasındaki Nüfus, İklim, Deprem sütunlarını kontrol et
        ws_sehir = wb["Sehirler"]
        # Satır 2 = Adana (01)
        # Nüfus sütununu bul
        header_row = [ws_sehir.cell(1, c).value for c in range(1, ws_sehir.max_column + 1)]
        nufus_col = header_row.index("Nüfus") + 1
        adana_nufus = ws_sehir.cell(2, nufus_col).value
        assert adana_nufus == 2274106  # TÜİK ADNKS Adana nüfusu

        # Hücre yorumu (comment) kontrolü
        cell = ws_sehir.cell(2, nufus_col)
        assert cell.comment is not None
        assert "tuik.gov.tr" in cell.comment.text

        wb.close()
