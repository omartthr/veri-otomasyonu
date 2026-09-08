"""Şehir & Yaşam Rehberi — Ortak Sayfa İşlemci Taban Sınıfı.

Tüm sayfa işlemcilerinin (Şehirler, İlçeler, Kampüsler, Üniversiteler)
miras aldığı soyut taban sınıf.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

from src.city_livability_pipeline.excel_handler import (
    read_livability_sheet,
    write_livability_sheet,
)
from src.city_livability_pipeline.models import SheetProcessorResult

logger = logging.getLogger(__name__)


class BaseSheetProcessor(ABC):
    """Her sayfa işlemcisinin taban sınıfı.

    Alt sınıflar sadece `process_row()` ve `sheet_name` tanımlar.
    Okuma, yazma, ilerleme takibi ve hata yönetimi burada merkezileşir.
    """

    sheet_name: str = ""

    def __init__(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ):
        """
        Args:
            progress_callback: (mesaj, işlenen, toplam) parametreli ilerleme geri çağrısı
        """
        self.progress_callback = progress_callback
        self.result = SheetProcessorResult(sheet_name=self.sheet_name)

    def _report_progress(self, msg: str, current: int, total: int) -> None:
        if self.progress_callback:
            self.progress_callback(msg, current, total)

    @abstractmethod
    def process_row(
        self,
        row: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Tek bir satırı işleyerek güncellenmesi gereken sütunları döndür.

        Args:
            row: Excel satırından okunan ham sözlük
            context: Ek bağlam (diğer sayfalardan gelen veriler vs.)

        Returns:
            {"Sütun Başlığı": yeni_değer, ...} formatında güncellemeler.
            Boş sözlük = güncelleme yok.
        """
        ...

    def run(
        self,
        input_path: Path | str,
        output_path: Path | str,
        context: Optional[dict[str, Any]] = None,
    ) -> SheetProcessorResult:
        """Sayfayı oku → satırları işle → güncellenmiş Excel yaz.

        Args:
            input_path: Kaynak Excel yolu
            output_path: Çıktı Excel yolu
            context: Ek bağlam verisi

        Returns:
            SheetProcessorResult
        """
        ctx = context or {}
        self.result = SheetProcessorResult(sheet_name=self.sheet_name, status="running")

        try:
            rows, header_map = read_livability_sheet(input_path, self.sheet_name)
            self.result.total_rows = len(rows)

            logger.info(
                "[%s] %d satır okundu, işleniyor...",
                self.sheet_name, len(rows),
            )

            updates: dict[int, dict[str, Any]] = {}

            for i, row in enumerate(rows):
                row_num = row.get("_row_number", i + 2)

                try:
                    row_updates = self.process_row(row, ctx)

                    if row_updates:
                        # Denetim alanları ekleniyor
                        today = date.today().isoformat()
                        if "Kaynak Türü" not in row_updates and row.get("Kaynak Türü") is None:
                            row_updates["Kaynak Türü"] = "resmi"
                        if "Veri Tarihi" not in row_updates and row.get("Veri Tarihi") is None:
                            row_updates["Veri Tarihi"] = today
                        if "_confidence" not in row_updates and row.get("_confidence") is None:
                            row_updates["_confidence"] = "Yüksek"
                        if "_needs_review" not in row_updates and row.get("_needs_review") is None:
                            row_updates["_needs_review"] = "Hayır"

                        updates[row_num] = row_updates
                        self.result.cells_filled += len(row_updates)

                except Exception as e:
                    logger.error(
                        "[%s] Satır %d hatası: %s",
                        self.sheet_name, row_num, e,
                    )
                    self.result.errors.append({
                        "row": row_num,
                        "error": str(e),
                    })

                entity_name = (
                    row.get("İl Adı")
                    or row.get("Üniversite Adı")
                    or row.get("İlçe Adı")
                    or row.get("Kampüs Adı")
                    or f"Satır {i + 1}"
                )
                self._report_progress(
                    f"[{i + 1}/{len(rows)}] {entity_name} taranıyor & 8 kural ile doğrulanıyor...",
                    i + 1,
                    len(rows),
                )

            # Excel'e yaz
            if updates:
                write_livability_sheet(input_path, output_path, self.sheet_name, updates)
                logger.info(
                    "[%s] %d satır güncellendi, %d hücre yazıldı.",
                    self.sheet_name, len(updates), self.result.cells_filled,
                )
            else:
                logger.info("[%s] Güncellenecek satır yok.", self.sheet_name)

            self.result.needs_review_count = sum(
                1 for upd in updates.values()
                if upd.get("_needs_review") == "Evet"
            )
            self.result.status = "completed"

        except Exception as e:
            logger.error("[%s] Sayfa işleme hatası: %s", self.sheet_name, e)
            self.result.status = "error"
            self.result.errors.append({"row": 0, "error": str(e)})

        return self.result
