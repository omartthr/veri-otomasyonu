"""Güven puanı hesaplama testleri — yüksek doğruluk eşikleriyle."""

from __future__ import annotations

import pytest

from src.models import DecisionType, DualValidationResult, ScoreBreakdown
from src.validation.scoring import calculate_score, calculate_score_from_dual


class TestScoring:
    def test_perfect_score(self):
        score = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            ai_confidence=1.0, is_recent=True,
        )
        assert score.total == 100
        assert score.decision == DecisionType.ACCEPTED

    def test_zero_score(self):
        score = calculate_score(campus_match=False)
        assert score.total == 0
        assert score.decision == DecisionType.REJECTED

    def test_borderline_accepted_90(self):
        """90 puan — yeni eşik ile otomatik kabul."""
        score = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            ai_confidence=0.0, is_recent=True,
        )
        # 20+10+15+10+15+15+0+5 = 90
        assert score.total == 90
        assert score.decision == DecisionType.ACCEPTED

    def test_89_is_manual_review(self):
        """89 puan — yeni eşikte otomatik kabul DEĞİL, manuel kontrol."""
        score = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            ai_confidence=0.0, is_recent=False,
        )
        # 20+10+15+10+15+15+0+0 = 85 → manuel kontrol
        assert score.total == 85
        assert score.decision == DecisionType.MANUAL_REVIEW

    def test_manual_review_range(self):
        score = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True,
        )
        # 20+10+15+10+15 = 70
        assert 70 <= score.total < 90
        assert score.decision == DecisionType.MANUAL_REVIEW

    def test_penalty_old_catalog(self):
        base = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            ai_confidence=1.0, is_recent=True,
        )
        penalized = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            ai_confidence=1.0, is_recent=True,
            is_old_catalog=True,
        )
        assert penalized.total == base.total - 10

    def test_penalty_homepage(self):
        score = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            ai_confidence=1.0, is_recent=True,
            is_homepage_only=True,
        )
        assert score.penalty_homepage_only == -15

    def test_penalty_wrong_campus(self):
        score = calculate_score(
            is_official_domain=True, http_accessible=True,
            institution_name_found=True,
            category_keywords_found=True, strong_evidence=True,
            ai_confidence=0.8,
            is_wrong_campus=True,
        )
        assert score.penalty_wrong_campus == -25

    def test_score_clamped_to_zero(self):
        score = ScoreBreakdown(
            penalty_old_catalog=-10,
            penalty_homepage_only=-15,
            penalty_wrong_campus=-25,
        )
        assert score.total == 0

    def test_score_clamped_to_100(self):
        score = ScoreBreakdown(
            official_domain=20, http_accessible=10,
            institution_name_match=15, campus_match=10,
            category_keywords=15, strong_category_evidence=15,
            ai_confidence=10, recency=5,
        )
        assert score.total == 100

    def test_low_score_rejected(self):
        score = calculate_score(
            is_official_domain=True, http_accessible=True,
        )
        assert score.total < 70
        assert score.decision == DecisionType.REJECTED


class TestScoringFromDual:
    def test_from_dual_uses_consensus(self):
        dual = DualValidationResult(
            consensus_confidence=0.92,
            both_relevant=True,
            categories_agree=True,
            institutions_agree=True,
            campuses_agree=True,
            both_confident=True,
            both_evidence_verified=True,
        )
        score = calculate_score_from_dual(
            dual,
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            is_recent=True,
        )
        # ai_confidence = int(0.92 * 10) = 9
        assert score.ai_confidence == 9
        assert score.total == 99

    def test_from_dual_low_consensus(self):
        dual = DualValidationResult(consensus_confidence=0.50)
        score = calculate_score_from_dual(
            dual,
            is_official_domain=True, http_accessible=True,
            institution_name_found=True, campus_match=True,
            category_keywords_found=True, strong_evidence=True,
            is_recent=True,
        )
        assert score.ai_confidence == 5
        assert score.total == 95
