"""Şehir & Yaşam Rehberi — Mantıksal Bayrak (Evet / Hayır / Koşullu) Çıkarıcısı.

Var/Yok, Evet/Hayır, Kapsam/Koşul sorularını metin içinden çıkararak
standart 'Evet' | 'Hayır' | 'Koşullu' değerlerine dönüştürür.
"""

from __future__ import annotations

import re
from typing import Optional

from src.city_livability_pipeline.extractors.base_livability_extractor import ExtractedLivabilityField
from src.city_livability_pipeline.validation.hard_quality_gates import HardQualityGates


class BooleanFlagExtractor:
    """Evet / Hayır / Koşullu çıkarıcısı."""

    @classmethod
    def extract_flag(
        cls,
        field_name: str,
        text: str,
        positive_keywords: list[str],
        negative_keywords: list[str],
        conditional_keywords: Optional[list[str]] = None,
        source_url: Optional[str] = None,
    ) -> ExtractedLivabilityField:
        """Pozitif, negatif ve koşullu anahtar kelimelere göre bayrak çıkar."""
        if not text:
            return ExtractedLivabilityField()

        text_lower = text.replace("İ", "i").replace("I", "ı").lower()

        # 1. Koşullu kontrolü
        if conditional_keywords:
            for kw in conditional_keywords:
                kw_l = kw.replace("İ", "i").replace("I", "ı").lower()
                if kw_l in text_lower:
                    idx = text_lower.find(kw_l)
                    ev = text[max(0, idx - 20):min(len(text), idx + len(kw) + 20)].strip()
                    dec = HardQualityGates.evaluate_field(
                        field_name=field_name,
                        raw_value="Koşullu",
                        source_url=source_url,
                        evidence_text=ev,
                        is_boolean_flag=True,
                    )
                    return ExtractedLivabilityField(
                        value=dec.final_value,
                        source_url=source_url,
                        evidence=ev,
                        confidence=dec.confidence,
                        confidence_level=dec.confidence_level,
                        needs_review=dec.needs_review,
                    )

        # 2. Pozitif (Evet) kontrolü
        for kw in positive_keywords:
            kw_l = kw.replace("İ", "i").replace("I", "ı").lower()
            if kw_l in text_lower:
                idx = text_lower.find(kw_l)
                ev = text[max(0, idx - 20):min(len(text), idx + len(kw) + 20)].strip()
                dec = HardQualityGates.evaluate_field(
                    field_name=field_name,
                    raw_value="Evet",
                    source_url=source_url,
                    evidence_text=ev,
                    is_boolean_flag=True,
                )
                return ExtractedLivabilityField(
                    value=dec.final_value,
                    source_url=source_url,
                    evidence=ev,
                    confidence=dec.confidence,
                    confidence_level=dec.confidence_level,
                    needs_review=dec.needs_review,
                )

        # 3. Negatif (Hayır) kontrolü
        for kw in negative_keywords:
            kw_l = kw.replace("İ", "i").replace("I", "ı").lower()
            if kw_l in text_lower:
                idx = text_lower.find(kw_l)
                ev = text[max(0, idx - 20):min(len(text), idx + len(kw) + 20)].strip()
                dec = HardQualityGates.evaluate_field(
                    field_name=field_name,
                    raw_value="Hayır",
                    source_url=source_url,
                    evidence_text=ev,
                    is_boolean_flag=True,
                )
                return ExtractedLivabilityField(
                    value=dec.final_value,
                    source_url=source_url,
                    evidence=ev,
                    confidence=dec.confidence,
                    confidence_level=dec.confidence_level,
                    needs_review=dec.needs_review,
                )

        return ExtractedLivabilityField()

    @classmethod
    def extract_prep_school_mandatory(
        cls,
        text: str,
        source_url: Optional[str] = None,
    ) -> ExtractedLivabilityField:
        """Zorunlu İngilizce Hazırlık Mı alanını çıkar."""
        return cls.extract_flag(
            field_name="Zorunlu İngilizce Hazırlık Mı",
            text=text,
            positive_keywords=[
                "zorunlu hazırlık", "zorunlu ingilizce", "hazırlık sınıfı zorunlu",
                "hazırlık sınıfı zorunludur", "1 yıl zorunlu", "zorunlu yabancı dil",
            ],
            negative_keywords=["hazırlık sınıfı yoktur", "hazırlık zorunlu değildir", "isteğe bağlı hazırlık"],
            conditional_keywords=["bölümlere göre zorunlu", "%30 ingilizce bölümlerde zorunlu", "kısmen zorunlu"],
            source_url=source_url,
        )

    @classmethod
    def extract_library_24_7(
        cls,
        text: str,
        source_url: Optional[str] = None,
    ) -> ExtractedLivabilityField:
        """Kütüphane 7/24 Açık Mı alanını çıkar."""
        return cls.extract_flag(
            field_name="Kütüphane 7/24 Mi",
            text=text,
            positive_keywords=["7/24", "7 gün 24 saat", "24 saat açık", "kesintisiz hizmet", "gece açık"],
            negative_keywords=["saat 17:00", "saat 22:00'ye kadar", "hafta sonu kapalı", "gece kapalı"],
            conditional_keywords=["vize ve final dönemlerinde 7/24", "sınav döneminde 24 saat"],
            source_url=source_url,
        )
