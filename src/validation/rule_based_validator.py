"""API anahtarı gerektirmeyen deterministik aday doğrulama motoru."""

from __future__ import annotations

import re
from datetime import datetime

from src.config import get_settings
from src.domain_utils import is_homepage_only
from src.models import CandidateResult, CandidateURL, DecisionType, ResearchCategory
from src.validation.rule_validator import validate_rules
from src.validation.scoring import calculate_score

_EVIDENCE_TERMS: dict[ResearchCategory, tuple[str, ...]] = {
    ResearchCategory.PROGRAM: (
        "academic programs", "degree programs", "areas of study", "majors", "bachelor", "master", "doctoral",
    ),
    ResearchCategory.ADMISSION: (
        "admission requirements", "application requirements", "eligibility", "transcript", "diploma", "gpa", "deadline",
    ),
    ResearchCategory.LANGUAGE: (
        "english language proficiency", "english proficiency", "toefl", "ielts",
        "duolingo", "pte", "foreign language requirement", "language requirement",
        "minimum score", "proof of proficiency", "graduation requirement",
    ),
    ResearchCategory.TUITION: (
        "tuition and fees", "tuition", "cost of attendance", "cost per credit", "mandatory fees", "non-resident", "resident",
    ),
}


def _extract_evidence(text: str, category: ResearchCategory, limit: int = 3) -> list[str]:
    """Hedef ifadelerin çevresindeki birebir metin kesitlerini çıkar."""
    lower_text = text.lower()
    evidence: list[str] = []
    for term in _EVIDENCE_TERMS[category]:
        index = lower_text.find(term)
        if index < 0:
            continue
        start = max(0, index - 100)
        end = min(len(text), index + len(term) + 180)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip(" -–—:;,.\n\t")
        if snippet and snippet not in evidence:
            evidence.append(snippet)
        if len(evidence) >= limit:
            break
    return evidence


def _detect_content_year(text: str) -> int | None:
    """Metindeki makul takvim/akademik yıllardan en güncelini seç."""
    current_year = datetime.now().year
    contextual_years: set[int] = set()
    for first, second in re.findall(r"\b(20\d{2})\s*[-–/]\s*(20\d{2}|\d{2})\b", text):
        contextual_years.add(int(first))
        contextual_years.add(int(second) if len(second) == 4 else int(first[:2] + second))
    for match in re.finditer(
        r"(?i)(?:academic year|catalog|bulletin|tuition|fees)[^0-9]{0,50}(20\d{2})",
        text,
    ):
        year_start = match.start(1)
        if text[max(0, year_start - 3):year_start].lower() in {"ds-", "i-"}:
            continue
        contextual_years.add(int(match.group(1)))
    contextual_years = {
        year for year in contextual_years if 2000 <= year <= current_year + 2
    }
    if contextual_years:
        return max(contextual_years)

    years: set[int] = set()
    for match in re.finditer(r"\b(20\d{2})\b", text):
        year_start = match.start(1)
        if text[max(0, year_start - 3):year_start].lower() in {"ds-", "i-"}:
            continue
        value = int(match.group(1))
        if 2000 <= value <= current_year + 2:
            years.add(value)
    return max(years) if years else None


def _detect_scope(text: str) -> str:
    lower = text.lower()
    has_undergrad = bool(re.search(r"\b(undergraduate|bachelor)\b", lower))
    has_grad = bool(re.search(r"\b(graduate|master|doctoral|phd)\b", lower))
    if any(term in lower for term in ("this program", "program-specific", "department requirement")):
        return "program"
    if has_undergrad and has_grad:
        return "mixed"
    return "institution"


def _strong_category_evidence(text: str, category: ResearchCategory) -> bool:
    """Tek kelime eşleşmesi yerine kategoriye özgü birleşik kanıt şartları."""
    lower = text.lower()
    if category == ResearchCategory.PROGRAM:
        program_hits = len(re.findall(r"\b(program|degree|major)s?\b", lower))
        levels = len(set(re.findall(r"\b(bachelor|master|doctoral|doctorate|phd|associate)\b", lower)))
        return program_hits >= 3 and (levels >= 2 or len(text) >= 800)

    if category == ResearchCategory.ADMISSION:
        has_context = bool(re.search(r"\b(admissions?|application) requirements?\b", lower))
        support = sum(
            bool(re.search(pattern, lower))
            for pattern in (
                r"\btranscripts?\b", r"\b(diploma|degree certificate)\b", r"\bgpa\b",
                r"\bdeadlines?\b", r"\brequired documents?\b", r"\beligibility\b",
            )
        )
        return has_context and support >= 2

    if category == ResearchCategory.LANGUAGE:
        has_context = bool(
            re.search(
                r"\benglish (?:language )?proficiency\b|\b(?:foreign )?language requirements?\b",
                lower,
            )
        )
        support = sum(
            bool(re.search(rf"\b{term}\b", lower))
            for term in ("toefl", "ielts", "duolingo", "pte", "cambridge", "itep")
        )
        obligation = bool(
            re.search(
                r"\b(required|requirement|must|minimum score|proof of proficiency|"
                r"admission requirement|graduation requirement)\b",
                lower,
            )
        )
        return has_context and obligation and support >= 1

    if category == ResearchCategory.TUITION:
        has_context = bool(re.search(r"\btuition\b|\bcost of attendance\b|\bmandatory fees?\b", lower))
        has_amount = bool(re.search(r"\$\s?\d[\d,]*(?:\.\d{2})?|\b\d[\d,]*\s*(?:usd|dollars?)\b", lower))
        return has_context and has_amount

    return False


def evaluate_rule_based_candidate(
    candidate: CandidateURL,
    university_name: str,
    official_domain: str,
) -> CandidateResult:
    """Adayı yalnızca indirilen gerçek içerik ve katı kod kurallarıyla değerlendir."""
    rule_passed, details, rejection_reason = validate_rules(
        candidate=candidate,
        university_name=university_name,
        official_domain=official_domain,
    )
    if not rule_passed:
        return CandidateResult(
            candidate=candidate,
            rule_passed=False,
            rule_details=details,
            decision=DecisionType.REJECTED,
            rejection_reason=rejection_reason or "Kurallı doğrulama başarısız.",
        )

    text = candidate.extracted_text or ""
    evidence = _extract_evidence(text, candidate.category)
    strong = _strong_category_evidence(text, candidate.category)
    content_year = _detect_content_year(text)
    current_year = datetime.now().year
    is_recent = bool(content_year and content_year >= current_year - 1)
    is_old = bool(content_year and content_year < current_year - 2)
    scope = _detect_scope(text)
    details["strong_category_evidence"] = strong
    details["recent_content"] = is_recent
    details["not_old"] = not is_old

    score = calculate_score(
        is_official_domain=details.get("official_domain", False),
        http_accessible=details.get("http_200", False),
        institution_name_found=details.get("institution_name", False),
        campus_match=True,
        category_keywords_found=details.get("mandatory_evidence", False),
        strong_evidence=strong,
        ai_confidence=0.0,
        is_recent=is_recent,
        is_old_catalog=is_old,
        is_homepage_only=is_homepage_only(candidate.url),
    )

    accept_threshold = get_settings().rule_accept_threshold
    if strong and evidence and score.total >= accept_threshold:
        decision = DecisionType.ACCEPTED
        reason = None
    elif score.total >= 65:
        decision = DecisionType.MANUAL_REVIEW
        reason = f"Kural puanı={score.total}; güçlü içerik kanıtı veya kabul eşiği ({accept_threshold}) sağlanmadı."
    else:
        decision = DecisionType.REJECTED
        reason = f"Kural puanı={score.total}; kabul koşulları sağlanmadı."

    return CandidateResult(
        candidate=candidate,
        rule_passed=True,
        rule_details=details,
        rule_evidence=evidence,
        content_year=content_year,
        scope=scope,
        score=score,
        decision=decision,
        rejection_reason=reason,
    )
