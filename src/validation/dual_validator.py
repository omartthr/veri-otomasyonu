"""Çift Gemini doğrulama karar modülü.

İki bağımsız Gemini doğrulama geçişinden gelen sonuçları birleştirir.
İkinci geçiş birinci geçişin cevabını GÖRMEZ (tam bağımsız değerlendirme).

Otomatik kabul için TÜM koşulların sağlanması zorunludur:
- İki doğrulama da is_relevant=True
- Kategori değerleri aynı
- institution_match=True
- campus_match=True (veya uygulanamaz)
- İki güven puanı da >= 0.90
- Kanıt cümleleri kodla doğrulanmış
- Puan >= 90/100
"""

from __future__ import annotations

import logging
from typing import Optional

from src.models import (
    AIValidationResponse,
    CandidateResult,
    CandidateURL,
    DecisionType,
    DualValidationResult,
    ProviderValidationResult,
    ScoreBreakdown,
)

logger = logging.getLogger(__name__)

# Minimum confidence eşiği (her iki doğrulama için)
MIN_CONFIDENCE = 0.90


def build_dual_validation(
    pass1_result: Optional[ProviderValidationResult],
    pass2_result: Optional[ProviderValidationResult],
    min_confidence: float = MIN_CONFIDENCE,
) -> DualValidationResult:
    """İki bağımsız Gemini doğrulama sonucunu birleştirerek DualValidationResult oluştur.

    Args:
        pass1_result: Birinci Gemini doğrulama sonucu
        pass2_result: İkinci bağımsız Gemini doğrulama sonucu
        min_confidence: Minimum confidence eşiği

    Returns:
        DualValidationResult
    """
    disagreements: list[str] = []

    # İki sonuç da yoksa
    if pass1_result is None and pass2_result is None:
        return DualValidationResult(
            disagreement_details=["İki Gemini doğrulamasından da sonuç alınamadı."],
        )

    # Tek sonuç varsa — çift doğrulama sağlanamaz
    if pass1_result is None:
        return DualValidationResult(
            gemini_pass2_result=pass2_result,
            disagreement_details=["Birinci Gemini doğrulama sonucu eksik."],
        )
    if pass2_result is None:
        return DualValidationResult(
            gemini_pass1_result=pass1_result,
            disagreement_details=["İkinci bağımsız Gemini doğrulama sonucu eksik."],
        )

    p1 = pass1_result
    p2 = pass2_result

    # ─── Uzlaşma kontrolleri ───

    both_relevant = p1.is_valid and p2.is_valid
    if not p1.is_valid:
        disagreements.append(f"Gemini Pass-1 geçersiz: {p1.invalidation_reason}")
    if not p2.is_valid:
        disagreements.append(f"Gemini Pass-2 geçersiz: {p2.invalidation_reason}")

    categories_agree = (
        p1.response.category == p2.response.category
        and p1.response.category != "unknown"
    )
    if not categories_agree:
        disagreements.append(
            f"Kategori uyuşmazlığı: Pass-1={p1.response.category}, "
            f"Pass-2={p2.response.category}"
        )

    institutions_agree = (
        p1.response.institution_match and p2.response.institution_match
    )
    if not institutions_agree:
        disagreements.append(
            f"Kurum eşleşme uyuşmazlığı: Pass-1={p1.response.institution_match}, "
            f"Pass-2={p2.response.institution_match}"
        )

    campuses_agree = p1.response.campus_match and p2.response.campus_match
    if not campuses_agree:
        disagreements.append(
            f"Kampüs eşleşme uyuşmazlığı: Pass-1={p1.response.campus_match}, "
            f"Pass-2={p2.response.campus_match}"
        )

    both_confident = (
        p1.response.confidence >= min_confidence
        and p2.response.confidence >= min_confidence
    )
    if not both_confident:
        disagreements.append(
            f"Düşük güven: Pass-1={p1.response.confidence:.2f}, "
            f"Pass-2={p2.response.confidence:.2f} (min={min_confidence})"
        )

    both_evidence_verified = p1.evidence_verified and p2.evidence_verified
    if not both_evidence_verified:
        if not p1.evidence_verified:
            disagreements.append("Gemini Pass-1 kanıtları doğrulamayı geçemedi.")
        if not p2.evidence_verified:
            disagreements.append("Gemini Pass-2 kanıtları doğrulamayı geçemedi.")

    agreed_category = (
        p1.response.category if categories_agree else None
    )
    consensus_confidence = min(p1.response.confidence, p2.response.confidence)

    return DualValidationResult(
        gemini_pass1_result=p1,
        gemini_pass2_result=p2,
        both_relevant=both_relevant,
        categories_agree=categories_agree,
        institutions_agree=institutions_agree,
        campuses_agree=campuses_agree,
        both_confident=both_confident,
        both_evidence_verified=both_evidence_verified,
        agreed_category=agreed_category,
        consensus_confidence=consensus_confidence,
        disagreement_details=disagreements,
    )


def make_acceptance_decision(
    dual: DualValidationResult,
    score: ScoreBreakdown,
    has_stronger_alternative: bool = False,
    auto_accept_threshold: int = 90,
    expected_category: Optional[str] = None,
) -> tuple[DecisionType, str]:
    """Çift Gemini doğrulama ve puana dayalı nihai karar ver.

    Otomatik kabul için TÜM koşullar sağlanmalı:
    1. İki bağımsız Gemini doğrulamasının tam uzlaşması
    2. Nihai puan >= auto_accept_threshold (90)
    3. Kanıt cümlelerinin iki geçişte de doğrulanması
    4. Daha güçlü alternatif olmaması

    Args:
        dual: Çift Gemini doğrulama sonucu
        score: Kurallı güven puanı
        has_stronger_alternative: Daha güçlü/eşit aday var mı?
        auto_accept_threshold: Otomatik kabul eşiği (varsayılan 90)

    Returns:
        (DecisionType, gerekçe) çifti
    """
    # ─── Eksik değerlendirme kontrolleri ───

    if dual.gemini_pass1_result is None or dual.gemini_pass2_result is None:
        return (
            DecisionType.MANUAL_REVIEW,
            "Çift Gemini doğrulaması eksik — iki geçiş de tamamlanamadı.",
        )

    # İki geçişin is_relevant yanıtını kontrol et
    p1_relevant = dual.gemini_pass1_result.response.is_relevant
    p2_relevant = dual.gemini_pass2_result.response.is_relevant

    if not p1_relevant or not p2_relevant:
        reasons = []
        if not p1_relevant:
            reasons.append("Gemini Pass-1: is_relevant=False")
        if not p2_relevant:
            reasons.append("Gemini Pass-2: is_relevant=False")
        return (
            DecisionType.REJECTED,
            f"Gemini sayfa(ları) ilgisiz buldu: {'; '.join(reasons)}",
        )

    if not dual.institutions_agree:
        return (
            DecisionType.REJECTED,
            "Kurum eşleşmesi iki Gemini doğrulamasında da sağlanamadı.",
        )

    # ─── Manuel kontrol sebepleri ───

    if not dual.both_evidence_verified:
        details = [d for d in dual.disagreement_details if "kanıt" in d.lower()]
        return (
            DecisionType.MANUAL_REVIEW,
            f"Kanıt cümleleri tam doğrulanamadı: {'; '.join(details)}",
        )

    if not dual.categories_agree:
        return (
            DecisionType.MANUAL_REVIEW,
            f"Kategori uyuşmazlığı: {'; '.join(dual.disagreement_details)}",
        )

    if expected_category and dual.agreed_category != expected_category:
        return (
            DecisionType.REJECTED,
            f"Beklenen kategori={expected_category}, doğrulanan kategori={dual.agreed_category}.",
        )

    if not dual.campuses_agree:
        return (
            DecisionType.MANUAL_REVIEW,
            "Kampüs eşleşme uyuşmazlığı.",
        )

    if not dual.both_confident:
        return (
            DecisionType.MANUAL_REVIEW,
            f"Düşük güven puanı — consensus={dual.consensus_confidence:.2f} (min=0.90).",
        )

    if score.total < auto_accept_threshold:
        if score.total >= 70:
            return (
                DecisionType.MANUAL_REVIEW,
                f"Puan={score.total}, eşik={auto_accept_threshold} altında.",
            )
        return (
            DecisionType.REJECTED,
            f"Puan={score.total}, kabul eşiğinin çok altında.",
        )

    if has_stronger_alternative:
        return (
            DecisionType.MANUAL_REVIEW,
            "Aynı kategori için daha güçlü alternatif mevcut.",
        )

    # ─── Tüm koşullar sağlandı → Otomatik kabul ───
    return (
        DecisionType.ACCEPTED,
        f"Çift Gemini doğrulama uzlaşması + Puan={score.total}/100.",
    )
