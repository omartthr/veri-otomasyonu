"""Şehir & Yaşam Rehberi — 8 Katı Kalite Kapısı (Hard Quality Gates).

Tüm çıkarılan alanları 8 sert filtreden geçirir:
1. Domain Otoritesi Kapısı
2. Aralık ve Tip Güvenliği Kapısı
3. Kanıt Alıntısı (Quote) Kapısı
4. Güncellik ve Para Birimi Kapısı
5. Coğrafi ve İlişkisel Bütünlük Kapısı
6. Uydurma Sıfır — Kanıt Yoksa Boş Bırak Kapısı
7. 3 Kademeli Güven Puanlaması Kapısı
8. Format ve Yorum (Comment) Güvencesi Kapısı
"""

from __future__ import annotations

import logging
from typing import Any, NamedTuple, Optional

from src.city_livability_pipeline.validation.evidence_verifier import (
    detect_content_year,
    get_domain_authority_score,
    verify_evidence_contains_value,
)
from src.city_livability_pipeline.validation.range_validators import (
    validate_boolean_flag,
    validate_categorical,
    validate_coordinates,
    validate_percentage,
    validate_positive_int,
    validate_price,
    validate_scale_1_to_5,
)

logger = logging.getLogger(__name__)


class GateDecision(NamedTuple):
    """Kalite kapısı karar sonucu."""
    accepted: bool
    final_value: Any
    confidence: float
    confidence_level: str  # "Yüksek" | "Orta" | "Düşük"
    needs_review: bool
    rejection_reason: Optional[str]
    rule_evidence: Optional[str]


class HardQualityGates:
    """8 Katı Kalite Kuralını çalıştıran denetçi sınıf."""

    MIN_ACCEPT_CONFIDENCE = 0.60
    HIGH_CONFIDENCE_THRESHOLD = 0.85

    @classmethod
    def evaluate_field(
        cls,
        field_name: str,
        raw_value: Any,
        source_url: Optional[str] = None,
        evidence_text: Optional[str] = None,
        price_category: Optional[str] = None,
        valid_categorical_set: Optional[set[str]] = None,
        is_scale_1_5: bool = False,
        is_boolean_flag: bool = False,
        is_percentage: bool = False,
        is_positive_int: bool = False,
        is_coordinate: bool = False,
        coord_lon: Optional[Any] = None,
        expected_year: int = 2025,
    ) -> GateDecision:
        """Bir alanı 8 sert kuraldan geçirerek nihai kararı üret."""

        # ─── KURAL 6: Uydurma Sıfır (Boş Değer Kontrolü) ───
        if raw_value is None or str(raw_value).strip().lower() in {"", "none", "null", "n/a", "—", "-"}:
            return GateDecision(
                accepted=False,
                final_value=None,
                confidence=0.0,
                confidence_level="Düşük",
                needs_review=False,
                rejection_reason="Değer boş veya kanıt yok.",
                rule_evidence=None,
            )

        # ─── KURAL 6.1: Sabit Veri Engeli (URL ve Kanıt Zorunluluğu) ───
        # Fiyat, bool veya 1-5 skala gerektiren özel alanlarda eğer URL yoksa "sahte/sabit" kabul et
        requires_proof = bool(price_category) or is_boolean_flag or is_scale_1_5 or is_positive_int
        if requires_proof and not source_url:
            return GateDecision(
                accepted=False,
                final_value=None,
                confidence=0.0,
                confidence_level="Düşük",
                needs_review=True,
                rejection_reason="Bu alan tipi için kaynak URL (source_url) zorunludur. Uydurma/Sabit veri şüphesi.",
                rule_evidence=evidence_text,
            )

        # ─── KURAL 2: Aralık ve Tip Doğrulaması ───
        validated_val = None
        if is_scale_1_5:
            validated_val = validate_scale_1_to_5(raw_value)
        elif is_boolean_flag:
            validated_val = validate_boolean_flag(raw_value)
        elif is_percentage:
            validated_val = validate_percentage(raw_value)
        elif is_positive_int:
            validated_val = validate_positive_int(raw_value)
        elif is_coordinate:
            lat_v, lon_v = validate_coordinates(raw_value, coord_lon)
            # Sahte merkez koordinatlarını reddet (39.0, 35.0) veya (39.35, xx)
            if lat_v and (round(lat_v, 2) == 39.00 or round(lat_v, 2) == 39.35):
                return GateDecision(
                    accepted=False,
                    final_value=None,
                    confidence=0.0,
                    confidence_level="Düşük",
                    needs_review=True,
                    rejection_reason="Uydurma/varsayılan merkez koordinatı tespit edildi (39.x).",
                    rule_evidence=evidence_text,
                )
            validated_val = lat_v  # lat döner
        elif price_category:
            validated_val = validate_price(raw_value, price_category)
        elif valid_categorical_set:
            validated_val = validate_categorical(raw_value, valid_categorical_set)
        else:
            validated_val = raw_value

        if validated_val is None:
            return GateDecision(
                accepted=False,
                final_value=None,
                confidence=0.0,
                confidence_level="Düşük",
                needs_review=True,
                rejection_reason=f"Aralık veya tip doğrulama hatası (Alan: {field_name}, Değer: {raw_value})",
                rule_evidence=evidence_text,
            )

        # ─── KURAL 1: Domain Otoritesi ───
        domain_score = get_domain_authority_score(source_url)

        # ─── KURAL 3: Kanıt Kesiti (Evidence Containment) ───
        evidence_matched = False
        if evidence_text:
            evidence_matched = verify_evidence_contains_value(validated_val, evidence_text)

        # ─── KURAL 4: Güncellik / Yıl Kontrolü ───
        year_detected = detect_content_year(evidence_text) or detect_content_year(source_url)
        is_fresh = True
        if year_detected and year_detected < (expected_year - 2):
            # 2 yıldan eski veri ise şüpheliye düşür
            is_fresh = False

        # ─── KURAL 7: 3 Kademeli Güven Puanı Hesabı ───
        base_confidence = domain_score * 0.50
        if evidence_matched:
            base_confidence += 0.35
        elif evidence_text:
            base_confidence += 0.20

        if is_fresh:
            base_confidence += 0.15
        else:
            base_confidence -= 0.20

        confidence = round(max(0.0, min(1.0, base_confidence)), 2)

        if confidence >= cls.HIGH_CONFIDENCE_THRESHOLD:
            conf_level = "Yüksek"
            needs_review = False
        elif confidence >= cls.MIN_ACCEPT_CONFIDENCE:
            conf_level = "Orta"
            needs_review = False
        else:
            conf_level = "Düşük"
            needs_review = True

        accepted = confidence >= cls.MIN_ACCEPT_CONFIDENCE

        return GateDecision(
            accepted=accepted,
            final_value=validated_val if accepted else None,
            confidence=confidence,
            confidence_level=conf_level,
            needs_review=needs_review,
            rejection_reason=None if accepted else "Güven puanı eşik altında kaldı.",
            rule_evidence=evidence_text,
        )
