"""Şehir & Yaşam Rehberi — Fiyat, Harç ve Tarife Çıkarıcısı.

Metin, duyuru veya tablolardan para birimi ve fiyat değerlerini alıntısıyla çıkarır.
8 Katı Kalite Kuralından geçirerek `ExtractedLivabilityField` üretir.
"""

from __future__ import annotations

import re
from typing import Optional

from src.city_livability_pipeline.extractors.base_livability_extractor import ExtractedLivabilityField
from src.city_livability_pipeline.validation.hard_quality_gates import HardQualityGates


class PriceAndTariffExtractor:
    """Fiyat ve tarife çıkarıcı."""

    # Fiyat kalıpları: "25 TL", "25,50 TL", "15.000 TL", "1.250,00 ₺", "15000TRY"
    PRICE_PATTERN = re.compile(
        r"(?:(?:₺|TL|TRY)\s*)?([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{1,2})?|[0-9]+(?:,[0-9]{1,2})?)\s*(?:TL|₺|TRY)?",
        re.IGNORECASE,
    )

    @classmethod
    def extract_dining_meal_price(
        cls,
        text: str,
        source_url: Optional[str] = None,
    ) -> ExtractedLivabilityField:
        """Yemekhane öğün ücretini (TL) metinden çıkar."""
        if not text:
            return ExtractedLivabilityField()

        # "öğrenci öğün", "öğrenci yemek", "yemekhane ücreti", "1 öğün" bağlamı
        context_patterns = [
            r"(?:öğrenci(?:ler\s+için)?|1\s+öğün|öğle\s+yemeği|yemekhane)[^\.\n]{0,60}?(?:ücreti|fiyatı|bedeli|tarifesi)?[^\.\n]{0,30}?(?:₺|TL|TRY)?\s*([0-9]{1,3}(?:,[0-9]{1,2})?)\s*(?:TL|₺|TRY)",
            r"(?:₺|TL|TRY)?\s*([0-9]{1,3}(?:,[0-9]{1,2})?)\s*(?:TL|₺|TRY)[^\.\n]{0,40}?(?:öğrenci\s+öğün|yemekhane)",
        ]

        for pat in context_patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                raw_num = match.group(1).replace(",", ".")
                try:
                    price_val = float(raw_num)
                    # Cümle kesiti
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    evidence = text[start:end].strip().replace("\n", " ")

                    decision = HardQualityGates.evaluate_field(
                        field_name="Yemekhane Öğün Ücreti (TL)",
                        raw_value=price_val,
                        source_url=source_url,
                        evidence_text=evidence,
                        price_category="yemekhane_ogun_ucreti",
                    )
                    return ExtractedLivabilityField(
                        value=decision.final_value,
                        source_url=source_url,
                        evidence=evidence,
                        confidence=decision.confidence,
                        confidence_level=decision.confidence_level,
                        needs_review=decision.needs_review,
                        rejection_reason=decision.rejection_reason,
                    )
                except ValueError:
                    pass

        return ExtractedLivabilityField()

    @classmethod
    def extract_student_transit_prices(
        cls,
        text: str,
        source_url: Optional[str] = None,
    ) -> tuple[ExtractedLivabilityField, ExtractedLivabilityField]:
        """Öğrenci tek bilet (TL) ve aylık abonman (TL) ücretlerini çıkar."""
        ticket_field = ExtractedLivabilityField()
        subscription_field = ExtractedLivabilityField()

        if not text:
            return ticket_field, subscription_field

        # 1. Tek Bilet
        ticket_pat = r"(?:öğrenci|indirimli)\s+(?:tek\s+biniş|bilet|ücreti|kartı)[^\.\n]{0,40}?([0-9]{1,2}(?:,[0-9]{1,2})?)\s*(?:TL|₺|TRY)"
        m_ticket = re.search(ticket_pat, text, re.IGNORECASE)
        if m_ticket:
            raw_num = m_ticket.group(1).replace(",", ".")
            try:
                val = float(raw_num)
                ev = text[max(0, m_ticket.start() - 20):min(len(text), m_ticket.end() + 20)].strip()
                dec = HardQualityGates.evaluate_field(
                    field_name="Öğrenci Tek Bilet (TL)",
                    raw_value=val,
                    source_url=source_url,
                    evidence_text=ev,
                    price_category="ogrenci_tek_bilet",
                )
                ticket_field = ExtractedLivabilityField(
                    value=dec.final_value,
                    source_url=source_url,
                    evidence=ev,
                    confidence=dec.confidence,
                    confidence_level=dec.confidence_level,
                    needs_review=dec.needs_review,
                )
            except ValueError:
                pass

        # 2. Abonman
        sub_pat = r"(?:öğrenci|indirimli)\s+(?:aylık|abonman)[^\.\n]{0,40}?([0-9]{2,4}(?:,[0-9]{1,2})?)\s*(?:TL|₺|TRY)"
        m_sub = re.search(sub_pat, text, re.IGNORECASE)
        if m_sub:
            raw_num = m_sub.group(1).replace(",", ".")
            try:
                val = float(raw_num)
                ev = text[max(0, m_sub.start() - 20):min(len(text), m_sub.end() + 20)].strip()
                dec = HardQualityGates.evaluate_field(
                    field_name="Öğrenci Aylık Abonman (TL/ay)",
                    raw_value=val,
                    source_url=source_url,
                    evidence_text=ev,
                    price_category="ogrenci_aylik_abonman",
                )
                subscription_field = ExtractedLivabilityField(
                    value=dec.final_value,
                    source_url=source_url,
                    evidence=ev,
                    confidence=dec.confidence,
                    confidence_level=dec.confidence_level,
                    needs_review=dec.needs_review,
                )
            except ValueError:
                pass

        return ticket_field, subscription_field

    @classmethod
    def extract_kyk_dorm_fee(
        cls,
        text: str,
        source_url: Optional[str] = None,
    ) -> ExtractedLivabilityField:
        """KYK yurt ücretini (TL/ay) çıkar."""
        if not text:
            return ExtractedLivabilityField()

        pat = r"(?:KYK|GSB)\s+(?:yurt\s+)?(?:ücreti|ücretleri|aylık|fiyatı)[^\.\n]{0,40}?([0-9]{3,4}(?:,[0-9]{1,2})?)\s*(?:TL|₺|TRY)"
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw_num = m.group(1).replace(",", ".")
            try:
                val = float(raw_num)
                ev = text[max(0, m.start() - 25):min(len(text), m.end() + 25)].strip()
                dec = HardQualityGates.evaluate_field(
                    field_name="KYK Yurt Ücreti (TL/ay)",
                    raw_value=val,
                    source_url=source_url,
                    evidence_text=ev,
                    price_category="kyk_yurt_ucreti",
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
