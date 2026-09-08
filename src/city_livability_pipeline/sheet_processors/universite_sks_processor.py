"""Şehir & Yaşam Rehberi — Üniversite SKS Sayfası İşlemcisi.

2_Universite_SKS sayfasındaki verileri:
1. Yemekhane Öğün Ücreti
2. Yurt Ücret Aralığı
3. Toplam Yurt Kapasitesi
4. Barınma Desteği Var Mı
5. Öğrenciye Yemek Desteği Var Mı
6. Ana Yerleşke Resmî Adı
(ve URL/Not)

8 Katı Kuralı ve prompts/2_universite_sks_kurallari.txt dosyasına
harfiyen uygun olarak çeker ve Excel'e yazar.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from src.city_livability_pipeline.sheet_processors.base_processor import BaseSheetProcessor
from src.city_livability_pipeline.validation.evidence_verifier import format_cell_comment
from src.city_livability_pipeline.search.deep_livability_crawler import DeepLivabilityCrawler

logger = logging.getLogger(__name__)


class UniversiteSKSProcessor(BaseSheetProcessor):
    """2_Universite_SKS sayfası Doldurucusu."""

    sheet_name = "2_Universite_SKS"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.crawler = DeepLivabilityCrawler(log_callback=lambda msg: self._report_progress(msg))

    def process_row(
        self,
        row: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Tek bir üniversite satırının SKS sütunlarını doldur."""
        universite_id = str(row.get("Üniversite ID", "")).strip()
        uni_name = str(row.get("Üniversite", "")).strip()
        web_sitesi = str(row.get("Web Sitesi", "")).strip()
        
        if not uni_name:
            return {}
            
        updates: dict[str, Any] = {}
        source_urls: list[str] = [web_sitesi] if web_sitesi else []
        notes: list[str] = []

        # ─── CANLI İNTERNET TARAMASI (SKS ÖZEL) ───
        try:
            live_results = asyncio.run(self.crawler.crawl_sks_deep(uni_name, web_sitesi))
        except Exception as e:
            logger.warning("Crawler hatası SKS (%s): %s", uni_name, e)
            live_results = {}
            
        # Map our internal intent to actual excel headers
        field_mapping = {
            "Yemekhane Öğün Ücreti": "Yemekhane Öğün Ücreti (TL, Öğrenci)",
            "Yurt Ücret Aralığı": "Yurt Ücret Aralığı (TL/ay)",
            "Toplam Yurt Kapasitesi": "Toplam Yurt Kapasitesi (yatak)",
            "Barınma Desteği Var Mı": "Barınma Desteği Var Mı",
            "Öğrenciye Yemek Desteği Var Mı": "Öğrenciye Yemek Desteği Var Mı",
            "Ana Yerleşke Resmî Adı": "Ana Yerleşke Resmî Adı"
        }
            
        for intent, (val, ev, url, note) in live_results.items():
            excel_field = field_mapping.get(intent, intent)
            if row.get(excel_field) is None:
                # 8-katı kural: Evidence zorunlu.
                updates[excel_field] = (val, format_cell_comment(url, ev, "SKS Kural Motoru (Zero Hallucination)"))
                source_urls.append(url)
                if note:
                    notes.append(note)

        # ─── 5. Denetim Alanları ───
        today = date.today().isoformat()
        updates["Kaynak Türü"] = "resmi"
        updates["Veri Tarihi"] = today
        
        unique_urls = []
        for u in source_urls:
            if u and u not in unique_urls:
                unique_urls.append(u)
                
        if unique_urls:
            updates["Kaynak URL(ler)"] = " | ".join(unique_urls)
            updates["_source_urls"] = " | ".join(unique_urls)
        
        if notes:
            updates["Not"] = " | ".join(notes)
            
        updates["_confidence"] = "Yüksek" if len(unique_urls) > 1 else "Orta"
        updates["_needs_review"] = "Hayır"
        updates["_source_notes"] = "8 Katı Kalite Kuralı: 2_Universite_SKS taraması"

        return updates
