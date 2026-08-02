"""Güven puanı hesaplama modülü.

Kural tabanlı ve çift AI doğrulama sonuçlarını birleştirerek
100 üzerinden güven puanı hesaplar.

Yüksek doğruluk modu:
- Otomatik kabul eşiği: 90/100
- Maliyet sınırlaması YOKTUR
"""

from __future__ import annotations

from src.models import DualValidationResult, ScoreBreakdown


def calculate_score(
    is_official_domain: bool = False,
    http_accessible: bool = False,
    institution_name_found: bool = False,
    campus_match: bool = True,
    category_keywords_found: bool = False,
    strong_evidence: bool = False,
    ai_confidence: float = 0.0,
    is_recent: bool = False,
    is_old_catalog: bool = False,
    is_homepage_only: bool = False,
    is_wrong_campus: bool = False,
) -> ScoreBreakdown:
    """Güven puanı bileşenlerini hesapla ve ScoreBreakdown döndür.

    ai_confidence parametresi çift doğrulama modunda
    iki modelin consensus (minimum) confidence değerini temsil eder.
    """
    return ScoreBreakdown(
        official_domain=20 if is_official_domain else 0,
        http_accessible=10 if http_accessible else 0,
        institution_name_match=15 if institution_name_found else 0,
        campus_match=10 if campus_match else 0,
        category_keywords=15 if category_keywords_found else 0,
        strong_category_evidence=15 if strong_evidence else 0,
        ai_confidence=int(ai_confidence * 10),
        recency=5 if is_recent else 0,
        penalty_old_catalog=-10 if is_old_catalog else 0,
        penalty_homepage_only=-15 if is_homepage_only else 0,
        penalty_wrong_campus=-25 if is_wrong_campus else 0,
    )


def calculate_score_from_dual(
    dual: DualValidationResult,
    is_official_domain: bool = False,
    http_accessible: bool = False,
    institution_name_found: bool = False,
    campus_match: bool = True,
    category_keywords_found: bool = False,
    strong_evidence: bool = False,
    is_recent: bool = False,
    is_old_catalog: bool = False,
    is_homepage_only: bool = False,
    is_wrong_campus: bool = False,
) -> ScoreBreakdown:
    """Çift doğrulama sonucundan güven puanı hesapla.

    ai_confidence olarak iki modelin minimum confidence değerini kullanır.
    """
    return calculate_score(
        is_official_domain=is_official_domain,
        http_accessible=http_accessible,
        institution_name_found=institution_name_found,
        campus_match=campus_match,
        category_keywords_found=category_keywords_found,
        strong_evidence=strong_evidence,
        ai_confidence=dual.consensus_confidence,
        is_recent=is_recent,
        is_old_catalog=is_old_catalog,
        is_homepage_only=is_homepage_only,
        is_wrong_campus=is_wrong_campus,
    )
