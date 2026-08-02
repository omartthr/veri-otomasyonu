"""Manuel kontrol kararlarının model ve Excel akışına aktarım testleri."""

from src.manual_review import approve_manual_url, reject_manual_url
from src.models import (
    AuditRecord,
    CandidateResult,
    CandidateURL,
    DecisionType,
    ResearchCategory,
    RowStatus,
    UniversityResearchResult,
)


def _manual_result() -> UniversityResearchResult:
    category = ResearchCategory.LANGUAGE
    return UniversityResearchResult(
        row_number=2,
        university_name="Example University",
        best_results={
            category: CandidateResult(
                candidate=CandidateURL(
                    url="https://example.edu/language-candidate",
                    category=category,
                ),
                decision=DecisionType.MANUAL_REVIEW,
            )
        },
        audit_records={category: AuditRecord(target_type=category.value)},
        status=RowStatus.MANUAL_REVIEW,
    )


def test_manual_approval_becomes_accepted_and_audited():
    result = _manual_result()
    category = ResearchCategory.LANGUAGE

    approved = approve_manual_url(
        result,
        category,
        "https://example.edu/english-requirements",
    )

    candidate = result.best_results[category]
    assert approved == "https://example.edu/english-requirements/"
    assert candidate is not None
    assert candidate.decision == DecisionType.ACCEPTED
    assert candidate.manually_approved is True
    assert result.status == RowStatus.COMPLETED
    assert result.audit_records[category].selected_url == approved
    assert "kullanıcı tarafından onaylandı" in result.audit_records[category].decision_reason


def test_manual_rejection_remains_manual_review_row():
    result = _manual_result()
    category = ResearchCategory.LANGUAGE

    reject_manual_url(result, category)

    candidate = result.best_results[category]
    assert candidate is not None
    assert candidate.decision == DecisionType.REJECTED
    assert candidate.manually_approved is False
    assert result.status == RowStatus.MANUAL_REVIEW


import pytest
from src.manual_review import bot_verify_manual_results


@pytest.mark.asyncio
async def test_bot_verify_manual_results():
    result = _manual_result()

    cand = result.best_results[ResearchCategory.LANGUAGE].candidate
    cand.http_status = 200
    cand.page_title = "English Language Proficiency Requirements | Example University"
    cand.extracted_text = (
        "Example University English Language Proficiency Requirements. "
        "Applicants must submit TOEFL 80 or IELTS 6.5 minimum score for admission. "
        "Proof of proficiency is a required document."
    )

    updated_results, stats = await bot_verify_manual_results([result])

    assert stats["checked_universities"] == 1
    assert stats["verified_fields"] >= 1
    assert updated_results[0].status == RowStatus.COMPLETED
    assert updated_results[0].best_results[ResearchCategory.LANGUAGE].decision == DecisionType.ACCEPTED

