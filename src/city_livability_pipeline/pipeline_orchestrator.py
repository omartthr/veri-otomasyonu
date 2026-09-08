"""Şehir & Yaşam Rehberi — Pipeline Orkestratör.

Tüm sayfaları bağımlılık sırasına göre koordine eden ana işlem yöneticisi.

Çalışma sırası (bağımlılık zinciri):
1. Üniversiteler (bağımsız)
2. Şehirler (bağımsız statik veriler)
3. İlçeler (Şehirler verilerine bağlı)
4. Kampüsler (Şehirler + Üniversiteler verilerine bağlı)

Her sayfa bağımsız da çalıştırılabilir (alt mod).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from src.city_livability_pipeline.excel_handler import (
    get_output_filename,
    read_livability_sheet,
)
from src.city_livability_pipeline.models import LivabilityPipelineResult, SheetProcessorResult
from src.city_livability_pipeline.sheet_processors.sehirler_processor import SehirlerProcessor
from src.city_livability_pipeline.sheet_processors.ilceler_processor import IlcelerProcessor
from src.city_livability_pipeline.sheet_processors.kampusler_processor import KampuslerProcessor
from src.city_livability_pipeline.sheet_processors.universiteler_processor import UniversitelerProcessor
from src.city_livability_pipeline.sheet_processors.universite_sks_processor import UniversiteSKSProcessor

logger = logging.getLogger(__name__)


class LivabilityPipelineOrchestrator:
    """Tüm sayfaları sırayla veya tek tek çalıştıran orkestratör.

    Her sayfa sonrası çıktıyı bir sonraki sayfanın girdisi olarak kullanır
    (zincirleme yazma).
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ):
        self.progress_callback = progress_callback
        self.result = LivabilityPipelineResult()

    def _build_sehirler_context(
        self,
        file_path: Path,
    ) -> dict[str, dict]:
        """Şehirler verisini okuyarak sehir_id → satır sözlüğü oluştur."""
        try:
            rows, _ = read_livability_sheet(file_path, "Sehirler")
            return {
                str(row.get("Şehir ID", "")).strip(): row
                for row in rows
                if row.get("Şehir ID")
            }
        except Exception as e:
            logger.warning("Şehirler verisi okunamadı: %s", e)
            return {}

    def _build_universiteler_context(
        self,
        file_path: Path,
    ) -> dict[str, dict]:
        """Üniversiteler verisini okuyarak universite_id → satır sözlüğü oluştur."""
        try:
            rows, _ = read_livability_sheet(file_path, "Universiteler")
            return {
                str(row.get("Üniversite ID", "")).strip(): row
                for row in rows
                if row.get("Üniversite ID")
            }
        except Exception as e:
            logger.warning("Üniversiteler verisi okunamadı: %s", e)
            return {}

    def _build_kampusler_context(
        self,
        file_path: Path,
    ) -> dict[str, list[dict]]:
        """Kampüsler verisini okuyarak universite_id → [kampüs_satırları] sözlüğü oluştur."""
        try:
            rows, _ = read_livability_sheet(file_path, "Kampusler")
            result: dict[str, list[dict]] = {}
            for row in rows:
                uni_id = str(row.get("Üniversite ID", "")).strip()
                if uni_id:
                    result.setdefault(uni_id, []).append(row)
            return result
        except Exception as e:
            logger.warning("Kampüsler verisi okunamadı: %s", e)
            return {}

    def _build_kampusler_by_ilce(
        self,
        file_path: Path,
    ) -> dict[str, list[dict]]:
        """Kampüsler verisini okuyarak ilce_id → [kampüs_satırları] sözlüğü oluştur."""
        try:
            rows, _ = read_livability_sheet(file_path, "Kampusler")
            result: dict[str, list[dict]] = {}
            for row in rows:
                ilce_id = str(row.get("İlçe ID", "")).strip()
                if ilce_id:
                    result.setdefault(ilce_id, []).append(row)
            return result
        except Exception as e:
            logger.warning("Kampüsler verisi okunamadı: %s", e)
            return {}

    def _build_universiteler_by_sehir(
        self,
        file_path: Path,
    ) -> dict[str, list[dict]]:
        """Üniversiteler verisini okuyarak sehir_id → [üniversite_satırları] sözlüğü oluştur."""
        try:
            rows, _ = read_livability_sheet(file_path, "Universiteler")
            result: dict[str, list[dict]] = {}
            for row in rows:
                sid = str(row.get("Ana İl (Şehir ID)", "")).strip()
                if sid:
                    result.setdefault(sid, []).append(row)
            return result
        except Exception as e:
            logger.warning("Üniversiteler verisi okunamadı: %s", e)
            return {}

    def run_single_sheet(
        self,
        sheet_name: str,
        input_path: Path | str,
        output_path: Path | str,
        context: Optional[dict[str, Any]] = None,
    ) -> SheetProcessorResult:
        """Tek bir sayfa işlemcisini çalıştır.

        Args:
            sheet_name: "Sehirler" | "Ilceler" | "Kampusler" | "Universiteler"
            input_path: Kaynak Excel
            output_path: Çıktı Excel
            context: Ek bağlam (otomatik oluşturulur yoksa)

        Returns:
            SheetProcessorResult
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        ctx = context or {}

        processors = {
            "Sehirler": SehirlerProcessor,
            "Ilceler": IlcelerProcessor,
            "Kampusler": KampuslerProcessor,
            "Universiteler": UniversitelerProcessor,
            "2_Universite_SKS": UniversiteSKSProcessor,
        }

        processor_cls = processors.get(sheet_name)
        if processor_cls is None:
            return SheetProcessorResult(
                sheet_name=sheet_name,
                status="error",
                errors=[{"row": 0, "error": f"Bilinmeyen sayfa: {sheet_name}"}],
            )

        # Bağlam oluştur (yoksa)
        if sheet_name == "Sehirler":
            if "universiteler_by_sehir" not in ctx:
                ctx["universiteler_by_sehir"] = self._build_universiteler_by_sehir(input_path)
        elif sheet_name == "Ilceler":
            if "sehirler_data" not in ctx:
                ctx["sehirler_data"] = self._build_sehirler_context(input_path)
            if "kampusler_by_ilce" not in ctx:
                ctx["kampusler_by_ilce"] = self._build_kampusler_by_ilce(input_path)
        elif sheet_name == "Kampusler":
            if "sehirler_data" not in ctx:
                ctx["sehirler_data"] = self._build_sehirler_context(input_path)
            if "universiteler_data" not in ctx:
                ctx["universiteler_data"] = self._build_universiteler_context(input_path)
        elif sheet_name == "Universiteler" and "kampusler_data" not in ctx:
            ctx["kampusler_data"] = self._build_kampusler_context(input_path)

        processor = processor_cls(progress_callback=self.progress_callback)
        result = processor.run(input_path, output_path, ctx)

        self.result.sheet_results[sheet_name] = result
        return result

    def run_all(
        self,
        input_path: Path | str,
        output_dir: Path | str,
    ) -> LivabilityPipelineResult:
        """Tüm sayfaları bağımlılık sırasıyla çalıştır.

        Sıra: Üniversiteler → Şehirler → İlçeler → Kampüsler

        Her sayfa çıktısını bir sonraki sayfanın girdisi yapar.
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        output_path = get_output_filename(input_path, output_dir)

        # İlk kopyayı oluştur
        shutil.copy2(input_path, output_path)

        logger.info("Pipeline başlatıldı: %s → %s", input_path.name, output_path.name)

        # Her aşamada çıktıyı sonraki aşamanın girdisi yap (üzerine yaz)
        processing_path = output_path

        sheet_order = ["Universiteler", "Sehirler", "Ilceler", "Kampusler"]

        for i, sheet_name in enumerate(sheet_order):
            logger.info("Aşama %d/%d: %s", i + 1, len(sheet_order), sheet_name)
            self._report_progress(
                f"Aşama {i + 1}/{len(sheet_order)}: {sheet_name}",
                i, len(sheet_order),
            )

            result = self.run_single_sheet(
                sheet_name=sheet_name,
                input_path=processing_path,
                output_path=processing_path,  # Üzerine yaz
            )

            self.result.total_cells_filled += result.cells_filled
            self.result.total_errors += len(result.errors)

            if result.status == "error":
                logger.error("[%s] Hata ile tamamlandı.", sheet_name)

        self.result.output_path = str(output_path)

        self._report_progress("Pipeline tamamlandı!", len(sheet_order), len(sheet_order))

        logger.info(
            "Pipeline tamamlandı: %d hücre, %d hata → %s",
            self.result.total_cells_filled,
            self.result.total_errors,
            output_path.name,
        )

        return self.result

    def _report_progress(self, msg: str, current: int, total: int) -> None:
        if self.progress_callback:
            self.progress_callback(msg, current, total)
