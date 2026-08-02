"""Kural tabanlı doğrulama testleri (placeholder).

Doğrulama modülü ilerideki aşamada uygulanacak.
Şimdilik temel yapı testleri bulunur.
"""

from __future__ import annotations

import pytest
from src.models import CandidateURL, ResearchCategory, UniversityRow
from src.validation.rule_validator import validate_rules


class TestRuleValidator:
    def test_missing_categories_evet(self):
        row = UniversityRow(
            row_number=2, university_name="Test",
            program_missing="Evet", admission_missing="Hayır",
            language_missing="Evet", tuition_missing="gerekli değil",
        )
        cats = row.get_missing_categories()
        assert ResearchCategory.PROGRAM in cats
        assert ResearchCategory.LANGUAGE in cats
        assert ResearchCategory.ADMISSION not in cats
        assert ResearchCategory.TUITION not in cats

    def test_empty_flags(self):
        row = UniversityRow(row_number=2, university_name="Test")
        assert len(row.get_missing_categories()) == 0

    def test_case_insensitive_evet(self):
        row = UniversityRow(row_number=2, university_name="Test", program_missing="EVET")
        cats = row.get_missing_categories()
        assert ResearchCategory.PROGRAM in cats

    def test_get_existing_url(self):
        row = UniversityRow(
            row_number=2, university_name="Test",
            program_url="https://test.edu/prog",
        )
        assert row.get_existing_url(ResearchCategory.PROGRAM) == "https://test.edu/prog"
        assert row.get_existing_url(ResearchCategory.ADMISSION) is None

    def test_requires_institution_name_in_title_or_content(self):
        candidate = CandidateURL(
            url="https://test.edu/programs/",
            category=ResearchCategory.PROGRAM,
            http_status=200,
            page_title="Academic Programs",
            extracted_text="Bachelor degree programs and graduate degree programs.",
        )
        passed, details, reason = validate_rules(candidate, "Example University", "test.edu")
        assert passed is False
        assert details["institution_name"] is False
        assert "Kurum adı" in reason

    def test_accepts_official_page_with_institution_and_category_evidence(self):
        candidate = CandidateURL(
            url="https://test.edu/programs/",
            category=ResearchCategory.PROGRAM,
            http_status=200,
            page_title="Example University Academic Programs",
            extracted_text="Example University offers bachelor degree programs and graduate majors.",
        )
        passed, details, reason = validate_rules(candidate, "Example University", "test.edu")
        assert passed is True
        assert details["official_domain"] is True
        assert details["institution_name"] is True
        assert reason is None
