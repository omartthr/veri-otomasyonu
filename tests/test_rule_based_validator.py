"""Anahtarsız kural tabanlı doğrulayıcı testleri."""

from src.models import CandidateURL, DecisionType, ResearchCategory
from src.validation.rule_based_validator import _detect_content_year, evaluate_rule_based_candidate


def test_language_page_is_accepted_with_official_evidence():
    text = (
        "Example University English language proficiency requirements. "
        "International applicants must submit TOEFL iBT 80 or IELTS 6.5. "
        "These requirements apply for the 2026-2027 academic year."
    )
    candidate = CandidateURL(
        url="https://example.edu/admissions/english-proficiency/",
        category=ResearchCategory.LANGUAGE,
        http_status=200,
        page_title="English Proficiency | Example University",
        extracted_text=text,
    )
    result = evaluate_rule_based_candidate(candidate, "Example University", "example.edu")
    assert result.decision == DecisionType.ACCEPTED
    assert result.content_year == 2027
    assert result.rule_evidence


def test_tuition_page_without_amount_or_rate_is_not_accepted():
    candidate = CandidateURL(
        url="https://example.edu/tuition/",
        category=ResearchCategory.TUITION,
        http_status=200,
        page_title="Tuition | Example University",
        extracted_text="Example University tuition information is available from our office.",
    )
    result = evaluate_rule_based_candidate(candidate, "Example University", "example.edu")
    assert result.decision != DecisionType.ACCEPTED


def test_wrong_domain_is_rejected_before_scoring():
    candidate = CandidateURL(
        url="https://thirdparty.com/example-university-toefl/",
        category=ResearchCategory.LANGUAGE,
        http_status=200,
        page_title="Example University TOEFL",
        extracted_text="Example University English proficiency TOEFL IELTS requirements.",
    )
    result = evaluate_rule_based_candidate(candidate, "Example University", "example.edu")
    assert result.decision == DecisionType.REJECTED
    assert result.rule_passed is False


def test_visa_form_ds_2019_is_not_treated_as_content_year():
    text = "See the academic catalog for I-20 or DS-2019 visa documentation requirements."
    assert _detect_content_year(text) is None
