"""Şehir & Yaşam Rehberi — 8 Katı Kalite Kapısı Testleri."""

import pytest
from src.city_livability_pipeline.validation.hard_quality_gates import HardQualityGates
from src.city_livability_pipeline.validation.evidence_verifier import (
    get_domain_authority_score,
    verify_evidence_contains_value,
    format_cell_comment,
)


class TestDomainAuthorityGate:
    def test_gov_tr_authority(self):
        assert get_domain_authority_score("https://data.tuik.gov.tr/Bulten/Index") == 1.0
        assert get_domain_authority_score("https://deprem.afad.gov.tr/") == 1.0

    def test_edu_tr_authority(self):
        assert get_domain_authority_score("https://sks.itu.edu.tr/yemek-bursu") == 0.95
        assert get_domain_authority_score("https://www.boun.edu.tr/yurtlar") == 0.95

    def test_transit_domains_authority(self):
        assert get_domain_authority_score("https://iett.istanbul/ucretler") >= 0.85

    def test_generic_web(self):
        assert get_domain_authority_score("https://randomblog.com/post") == 0.50


class TestEvidenceVerification:
    def test_contains_value_exact(self):
        assert verify_evidence_contains_value(25.0, "Öğrenci 1 öğün yemek ücreti 25 TL olarak belirlendi.")

    def test_contains_formatted_number(self):
        assert verify_evidence_contains_value(15000, "Ortalama kira bedeli 15.000 TL civarındadır.")

    def test_does_not_contain(self):
        assert not verify_evidence_contains_value(90.0, "Yemekhane ücreti 25 TL'dir.")


class TestHardQualityGates:
    def test_high_confidence_accepted(self):
        dec = HardQualityGates.evaluate_field(
            field_name="Yemekhane Öğün Ücreti (TL)",
            raw_value=25.0,
            source_url="https://sks.metu.edu.tr/yemek-ucretleri",
            evidence_text="2025-2026 akademik yılı öğrenci öğün ücreti 25 TL'dir.",
            price_category="yemekhane_ogun_ucreti",
        )
        assert dec.accepted
        assert dec.final_value == 25.0
        assert dec.confidence >= 0.85
        assert dec.confidence_level == "Yüksek"
        assert not dec.needs_review

    def test_unrealistic_price_rejected(self):
        dec = HardQualityGates.evaluate_field(
            field_name="Yemekhane Öğün Ücreti (TL)",
            raw_value=2500.0,  # 2500 TL tek öğün olamaz
            source_url="https://sks.metu.edu.tr/yemek-ucretleri",
            evidence_text="Yemek ücreti 2500 TL",
            price_category="yemekhane_ogun_ucreti",
        )
        assert not dec.accepted
        assert dec.final_value is None
        assert dec.needs_review

    def test_zero_hallucination_empty_input(self):
        dec = HardQualityGates.evaluate_field(
            field_name="Yemekhane Öğün Ücreti (TL)",
            raw_value=None,
        )
        assert not dec.accepted
        assert dec.final_value is None
        assert not dec.needs_review  # Boş veri hata değil, tertemiz None olmalı


class TestCellCommentFormatting:
    def test_format_comment(self):
        comment = format_cell_comment(
            source_url="https://iett.istanbul/",
            evidence="Öğrenci tek biniş 12,50 TL",
            rule_info="UKOME Tarife Kararı",
        )
        assert "https://iett.istanbul/" in comment
        assert "12,50 TL" in comment
        assert "UKOME" in comment
