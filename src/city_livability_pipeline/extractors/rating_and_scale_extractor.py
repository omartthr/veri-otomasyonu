"""Şehir & Yaşam Rehberi — 1-5 Skala ve Değerlendirme Çıkarıcısı.

Sosyal doku, güvenlik, ulaşım kalitesi gibi 1-5 ölçeğindeki metrikleri
sayısal veya nitel ifadelerden (çok iyi, orta, zayıf vb.) standartlaştırarak çıkarır.
"""

from __future__ import annotations

import re
from typing import Optional

from src.city_livability_pipeline.extractors.base_livability_extractor import ExtractedLivabilityField
from src.city_livability_pipeline.validation.hard_quality_gates import HardQualityGates

# Nitelik metinlerinden 1-5 puan eşleştirmesi
QUALITATIVE_MAP: dict[str, int] = {
    "çok yüksek": 5, "mükemmel": 5, "çok iyi": 5, "çok güvenli": 5, "çok canlı": 5,
    "yüksek": 4, "iyi": 4, "güvenli": 4, "canlı": 4, "kolay": 4, "yeterli": 4,
    "orta": 3, "ortalama": 3, "normal": 3, "standart": 3,
    "düşük": 2, "zayıf": 2, "az": 2, "zor": 2, "yetersiz": 2,
    "çok düşük": 1, "çok zayıf": 1, "çok az": 1, "çok zor": 1, "yok denecek kadar az": 1,
}


class RatingAndScaleExtractor:
    """1-5 skala çıkarıcısı."""

    @classmethod
    def extract_scale_1_to_5(
        cls,
        field_name: str,
        text: str,
        source_url: Optional[str] = None,
    ) -> ExtractedLivabilityField:
        """1-5 arası tam sayı puanını metinden çıkar."""
        if not text:
            return ExtractedLivabilityField()

        # 1. Doğrudan sayısal arama (Örn: "4/5", "Puan: 4", "Skor: 5")
        num_match = re.search(rf"(?:{field_name}|skor|puan|derece)[^\.\n]{{0,30}}?\b([1-5])\b(?:\s*/\s*5)?", text, re.IGNORECASE)
        if num_match:
            val = int(num_match.group(1))
            ev = text[max(0, num_match.start() - 20):min(len(text), num_match.end() + 20)].strip()
            dec = HardQualityGates.evaluate_field(
                field_name=field_name,
                raw_value=val,
                source_url=source_url,
                evidence_text=ev,
                is_scale_1_5=True,
            )
            return ExtractedLivabilityField(
                value=dec.final_value,
                source_url=source_url,
                evidence=ev,
                confidence=dec.confidence,
                confidence_level=dec.confidence_level,
                needs_review=dec.needs_review,
            )

        # 2. Niteliksel kelime arama
        text_lower = text.lower()
        for phrase, score in QUALITATIVE_MAP.items():
            if phrase in text_lower:
                idx = text_lower.find(phrase)
                ev = text[max(0, idx - 20):min(len(text), idx + len(phrase) + 20)].strip()
                dec = HardQualityGates.evaluate_field(
                    field_name=field_name,
                    raw_value=score,
                    source_url=source_url,
                    evidence_text=ev,
                    is_scale_1_5=True,
                )
                return ExtractedLivabilityField(
                    value=dec.final_value,
                    source_url=source_url,
                    evidence=ev,
                    confidence=min(dec.confidence, 0.75),  # Niteliksel çevrim maksimum 0.75
                    confidence_level="Orta",
                    needs_review=dec.needs_review,
                )

        return ExtractedLivabilityField()
