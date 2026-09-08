"""Şehir & Yaşam Rehberi — Kampüs Tesisleri ve Olanakları Çıkarıcısı.

Spor salonu, mediko/sağlık merkezi, ring servisi, kafe/market sayısı ve yurt kapasitelerini çıkarır.
"""

from __future__ import annotations

import re
from typing import Optional

from src.city_livability_pipeline.extractors.base_livability_extractor import ExtractedLivabilityField
from src.city_livability_pipeline.extractors.boolean_flag_extractor import BooleanFlagExtractor
from src.city_livability_pipeline.validation.hard_quality_gates import HardQualityGates


class CampusFacilitiesExtractor:
    """Kampüs tesis ve olanak çıkarıcısı."""

    @classmethod
    def extract_ring_shuttle(
        cls,
        text: str,
        source_url: Optional[str] = None,
    ) -> tuple[ExtractedLivabilityField, ExtractedLivabilityField]:
        """Ring Servisi Var Mı ve Ring Ücretli Mi alanlarını çıkar."""
        var_mi = BooleanFlagExtractor.extract_flag(
            field_name="Ring Servisi Var Mı",
            text=text,
            positive_keywords=["ring servisi", "ring seferleri", "kampüs içi ring", "yerleşke içi servis", "ücretsiz ring"],
            negative_keywords=["ring servisi bulunmamaktadır", "ring hizmeti yoktur", "servis yoktur"],
            source_url=source_url,
        )

        ucretli_mi = BooleanFlagExtractor.extract_flag(
            field_name="Ring Ücretli Mi",
            text=text,
            positive_keywords=["ücretli ring", "bilet karşılığı", "öğrenci tarifesi uygulanır"],
            negative_keywords=["ücretsiz ring", "ücretsiz servis", "ring seferleri ücretsizdir", "bedelsiz"],
            source_url=source_url,
        )

        return var_mi, ucretli_mi

    @classmethod
    def extract_dorm_capacity(
        cls,
        text: str,
        source_url: Optional[str] = None,
    ) -> ExtractedLivabilityField:
        """Yurt kapasitesini (yatak/öğrenci sayısı) pozitif tam sayı olarak çıkar."""
        if not text:
            return ExtractedLivabilityField()

        pat = r"(?:yurt\s+kapasitesi|kapasite)[^\.\n]{0,30}?([1-9][0-9]{1,4})\s*(?:öğrenci|yatak|kişi)"
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw_num = m.group(1).replace(".", "").replace(",", "")
            try:
                val = int(raw_num)
                ev = text[max(0, m.start() - 25):min(len(text), m.end() + 25)].strip()
                dec = HardQualityGates.evaluate_field(
                    field_name="Kampüs Yurt Kapasitesi",
                    raw_value=val,
                    source_url=source_url,
                    evidence_text=ev,
                    is_positive_int=True,
                )
                return ExtractedLivabilityField(
                    value=dec.final_value,
                    source_url=source_url,
                    evidence=ev,
                    confidence=dec.confidence,
                    confidence_level=dec.confidence_level,
                    needs_review=dec.needs_review,
                )
            except ValueError:
                pass

        return ExtractedLivabilityField()
