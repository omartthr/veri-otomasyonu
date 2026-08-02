"""Kanıt doğrulama testleri."""

from __future__ import annotations

import pytest

from src.models import AIValidationResponse
from src.validation.evidence_checker import (
    verify_evidence,
    _evidence_found_in_text,
    _normalize_text,
)


SAMPLE_PAGE_TEXT = """
Welcome to Test University

Academic Programs
We offer the following undergraduate and graduate programs:
- Bachelor of Science in Computer Science
- Master of Business Administration (MBA)
- Doctor of Philosophy in Mathematics

Admission Requirements
All applicants must submit the following documents:
- Official transcripts from all previously attended institutions
- Minimum GPA of 3.0 on a 4.0 scale
- Two letters of recommendation

English Language Requirements
International students must demonstrate English proficiency through:
- TOEFL: minimum score of 80 (internet-based)
- IELTS: minimum overall band score of 6.5
- Duolingo English Test: minimum score of 110

Tuition and Fees
Undergraduate tuition: $15,000 per semester
Graduate tuition: $18,500 per semester
Cost per credit hour: $750
"""


class TestNormalizeText:
    def test_lowercase(self):
        assert _normalize_text("Hello World") == "hello world"

    def test_whitespace(self):
        assert _normalize_text("  hello   world  ") == "hello world"

    def test_newlines(self):
        assert _normalize_text("hello\n\nworld") == "hello world"


class TestEvidenceFoundInText:
    def test_exact_match(self):
        assert _evidence_found_in_text(
            "Bachelor of Science in Computer Science",
            SAMPLE_PAGE_TEXT,
        )

    def test_case_insensitive(self):
        assert _evidence_found_in_text(
            "bachelor of science in computer science",
            SAMPLE_PAGE_TEXT,
        )

    def test_partial_word_match(self):
        """Kelime örtüşme oranı yeterli ise bulunur."""
        assert _evidence_found_in_text(
            "TOEFL minimum score of 80 internet-based",
            SAMPLE_PAGE_TEXT,
        )

    def test_fabricated_evidence(self):
        """Uydurma kanıt bulunmamalı."""
        assert not _evidence_found_in_text(
            "Harvard University offers advanced quantum computing research",
            SAMPLE_PAGE_TEXT,
        )

    def test_empty_evidence(self):
        assert not _evidence_found_in_text("", SAMPLE_PAGE_TEXT)

    def test_empty_text(self):
        assert not _evidence_found_in_text("Some evidence", "")

    def test_short_evidence_needs_exact(self):
        """3 kelimeden kısa kanıt için tam eşleşme gerekir."""
        # "MBA" tek kelime → exact match aranır
        assert not _evidence_found_in_text("XY", SAMPLE_PAGE_TEXT)


class TestVerifyEvidence:
    def test_all_evidence_found(self):
        response = AIValidationResponse(
            is_relevant=True,
            category="program",
            institution_match=True,
            evidence=[
                "Bachelor of Science in Computer Science",
                "Master of Business Administration",
            ],
            confidence=0.95,
        )
        result = verify_evidence(response, SAMPLE_PAGE_TEXT, "gemini")
        assert result.evidence_verified is True
        assert result.is_valid is True
        assert len(result.verified_evidence) == 2
        assert len(result.unverified_evidence) == 0

    def test_one_evidence_not_found(self):
        """Bir kanıt bulunamazsa sonuç geçersiz."""
        response = AIValidationResponse(
            is_relevant=True,
            category="program",
            institution_match=True,
            evidence=[
                "Bachelor of Science in Computer Science",
                "This is completely fabricated evidence that does not exist in the page",
            ],
            confidence=0.95,
        )
        result = verify_evidence(response, SAMPLE_PAGE_TEXT, "gemini")
        assert result.evidence_verified is False
        assert result.is_valid is False
        assert len(result.verified_evidence) == 1
        assert len(result.unverified_evidence) == 1
        assert "bulunamadı" in result.invalidation_reason

    def test_no_evidence_provided(self):
        """Kanıt sunulmamışsa geçersiz."""
        response = AIValidationResponse(
            is_relevant=True,
            category="program",
            institution_match=True,
            evidence=[],
            confidence=0.95,
        )
        result = verify_evidence(response, SAMPLE_PAGE_TEXT, "openai")
        assert result.is_valid is False
        assert "sunulmadı" in result.invalidation_reason

    def test_not_relevant_is_invalid(self):
        """is_relevant=False ise geçersiz."""
        response = AIValidationResponse(
            is_relevant=False,
            category="unknown",
            institution_match=False,
            evidence=["Bachelor of Science in Computer Science"],
            confidence=0.1,
        )
        result = verify_evidence(response, SAMPLE_PAGE_TEXT, "gemini")
        assert result.is_valid is False

    def test_provider_name_preserved(self):
        response = AIValidationResponse(
            is_relevant=True,
            category="tuition",
            institution_match=True,
            evidence=["Undergraduate tuition: $15,000 per semester"],
            confidence=0.92,
        )
        result = verify_evidence(response, SAMPLE_PAGE_TEXT, "openai")
        assert result.provider_name == "openai"
        assert result.is_valid is True
