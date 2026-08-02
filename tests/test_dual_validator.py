"""Çift Gemini doğrulama karar mekanizması testleri.

Sahte (fake) sağlayıcılarla test eder — gerçek API çağrısı YAPMAZ.
"""

from __future__ import annotations

import pytest

from src.models import (
    AIValidationResponse,
    DecisionType,
    DualValidationResult,
    ProviderValidationResult,
    ScoreBreakdown,
)
from src.validation.dual_validator import (
    build_dual_validation,
    make_acceptance_decision,
)
from src.validation.evidence_checker import verify_evidence


def _make_valid_response(
    category: str = "program",
    confidence: float = 0.95,
    evidence: list[str] | None = None,
) -> AIValidationResponse:
    """Geçerli bir AI yanıtı oluştur."""
    return AIValidationResponse(
        is_relevant=True,
        category=category,
        institution_match=True,
        campus_match=True,
        evidence=evidence or ["Bachelor of Science in Computer Science"],
        reason="Test value",
        confidence=confidence,
        content_year=2026,
    )


def _make_invalid_response(
    reason: str = "not relevant",
) -> AIValidationResponse:
    return AIValidationResponse(
        is_relevant=False,
        category="unknown",
        institution_match=False,
        campus_match=False,
        evidence=[],
        reason=reason,
        confidence=0.1,
    )


PAGE_TEXT = "Bachelor of Science in Computer Science and Master of Business Administration"


def _make_provider_result(
    provider: str,
    response: AIValidationResponse,
    page_text: str = PAGE_TEXT,
) -> ProviderValidationResult:
    """Kanıt doğrulaması dahil sağlayıcı sonucu oluştur."""
    return verify_evidence(response, page_text, provider)


# ─────────── Çift doğrulama birleştirme testleri ───────────

class TestBuildDualValidation:
    def test_unanimous_agreement(self):
        """İki Gemini geçişi de aynı sonucu verirse tam uzlaşma."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response())
        p2 = _make_provider_result("gemini_pass2", _make_valid_response())
        dual = build_dual_validation(p1, p2)

        assert dual.is_unanimous is True
        assert dual.both_relevant is True
        assert dual.categories_agree is True
        assert dual.institutions_agree is True
        assert dual.campuses_agree is True
        assert dual.both_confident is True
        assert dual.both_evidence_verified is True
        assert dual.agreed_category == "program"
        assert dual.consensus_confidence == 0.95
        assert len(dual.disagreement_details) == 0

    def test_category_disagreement(self):
        """Kategori uyuşmazlığı → uzlaşma yok."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response(category="program"))
        p2 = _make_provider_result("gemini_pass2", _make_valid_response(category="admission"))
        dual = build_dual_validation(p1, p2)

        assert dual.is_unanimous is False
        assert dual.categories_agree is False
        assert dual.agreed_category is None
        assert any("Kategori" in d for d in dual.disagreement_details)

    def test_one_not_relevant(self):
        """Bir geçiş is_relevant=False → uzlaşma yok."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response())
        p2 = _make_provider_result("gemini_pass2", _make_invalid_response())
        dual = build_dual_validation(p1, p2)

        assert dual.is_unanimous is False
        assert dual.both_relevant is False

    def test_low_confidence(self):
        """Bir geçişin confidence < 0.90 → uzlaşma yok."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response(confidence=0.95))
        p2 = _make_provider_result("gemini_pass2", _make_valid_response(confidence=0.85))
        dual = build_dual_validation(p1, p2)

        assert dual.is_unanimous is False
        assert dual.both_confident is False
        assert dual.consensus_confidence == 0.85

    def test_missing_pass1(self):
        """Pass-1 sonucu yoksa çift doğrulama eksik."""
        p2 = _make_provider_result("gemini_pass2", _make_valid_response())
        dual = build_dual_validation(None, p2)

        assert dual.is_unanimous is False
        assert any("Birinci" in d for d in dual.disagreement_details)

    def test_missing_pass2(self):
        """Pass-2 sonucu yoksa çift doğrulama eksik."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response())
        dual = build_dual_validation(p1, None)

        assert dual.is_unanimous is False
        assert any("İkinci" in d for d in dual.disagreement_details)

    def test_both_missing(self):
        dual = build_dual_validation(None, None)
        assert dual.is_unanimous is False

    def test_evidence_not_verified(self):
        """Kanıt doğrulanamazsa uzlaşma yok."""
        bad_response = _make_valid_response(
            evidence=["Completely fabricated evidence sentence"]
        )
        p1 = _make_provider_result("gemini_pass1", _make_valid_response())
        p2 = _make_provider_result("gemini_pass2", bad_response)
        dual = build_dual_validation(p1, p2)

        assert dual.is_unanimous is False
        assert dual.both_evidence_verified is False


# ─────────── Nihai karar testleri ───────────

class TestMakeAcceptanceDecision:
    def _perfect_dual(self) -> DualValidationResult:
        """Tam uzlaşmalı çift Gemini sonucu."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response())
        p2 = _make_provider_result("gemini_pass2", _make_valid_response())
        return build_dual_validation(p1, p2)

    def _perfect_score(self) -> ScoreBreakdown:
        return ScoreBreakdown(
            official_domain=20, http_accessible=10,
            institution_name_match=15, campus_match=10,
            category_keywords=15, strong_category_evidence=15,
            ai_confidence=9, recency=5,
        )

    def test_accepted_all_conditions_met(self):
        """Tüm koşullar sağlandığında ACCEPTED."""
        dual = self._perfect_dual()
        score = self._perfect_score()
        decision, reason = make_acceptance_decision(dual, score)
        assert decision == DecisionType.ACCEPTED

    def test_rejected_not_relevant(self):
        """Model sayfayı ilgisiz bulursa REJECTED."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response())
        p2 = _make_provider_result("gemini_pass2", _make_invalid_response())
        dual = build_dual_validation(p1, p2)
        score = self._perfect_score()
        decision, reason = make_acceptance_decision(dual, score)
        assert decision == DecisionType.REJECTED

    def test_manual_review_category_disagree(self):
        """Kategori uyuşmazlığı → MANUAL_REVIEW."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response(category="program"))
        p2 = _make_provider_result("gemini_pass2", _make_valid_response(category="admission"))
        dual = build_dual_validation(p1, p2)
        score = self._perfect_score()
        decision, reason = make_acceptance_decision(dual, score)
        assert decision == DecisionType.MANUAL_REVIEW

    def test_rejected_when_agreed_category_is_not_expected_category(self):
        p1 = _make_provider_result("gemini_pass1", _make_valid_response(category="admission"))
        p2 = _make_provider_result("gemini_pass2", _make_valid_response(category="admission"))
        dual = build_dual_validation(p1, p2)
        score = self._perfect_score()
        decision, reason = make_acceptance_decision(
            dual, score, expected_category="language"
        )
        assert decision == DecisionType.REJECTED
        assert "Beklenen kategori" in reason

    def test_manual_review_low_confidence(self):
        """Düşük güven → MANUAL_REVIEW."""
        p1 = _make_provider_result("gemini_pass1", _make_valid_response(confidence=0.95))
        p2 = _make_provider_result("gemini_pass2", _make_valid_response(confidence=0.80))
        dual = build_dual_validation(p1, p2)
        score = self._perfect_score()
        decision, reason = make_acceptance_decision(dual, score)
        assert decision == DecisionType.MANUAL_REVIEW

    def test_manual_review_low_score(self):
        """Puan 90 altında ama 70 üstünde → MANUAL_REVIEW."""
        dual = self._perfect_dual()
        score = ScoreBreakdown(
            official_domain=20, http_accessible=10,
            institution_name_match=15, campus_match=10,
            category_keywords=15, strong_category_evidence=15,
        )
        decision, reason = make_acceptance_decision(dual, score)
        assert decision == DecisionType.MANUAL_REVIEW

    def test_rejected_very_low_score(self):
        """Puan 70 altında → REJECTED."""
        dual = self._perfect_dual()
        score = ScoreBreakdown(
            official_domain=20, http_accessible=10,
        )
        decision, reason = make_acceptance_decision(dual, score)
        assert decision == DecisionType.REJECTED
