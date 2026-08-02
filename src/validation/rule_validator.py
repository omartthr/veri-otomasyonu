"""Kural tabanlı doğrulama modülü.

Bir aday URL ve sayfa metni için kural tabanlı kontroller yapar:
- HTTP 200 erişilebilirlik
- Resmî domain eşleşmesi
- Kategoriye özel zorunlu içerik kanıtları
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

from src.domain_utils import is_official_domain, is_safe_url, is_homepage_only
from src.models import CandidateURL, ResearchCategory

logger = logging.getLogger(__name__)


# ─── Kategoriye özel zorunlu anahtar kelime desenleri ───

MANDATORY_PATTERNS: dict[ResearchCategory, list[str]] = {
    ResearchCategory.PROGRAM: [
        r"\b(program[s]?|degree[s]?|major[s]?|academic programs|areas of study|bachelor|master|phd|doctorate)\b",
        r"\b(bachelor|master|phd|doctorate|degree[s]?|major[s]?|undergraduate|graduate)\b",
    ],
    ResearchCategory.ADMISSION: [
        r"\b(admissions? requirements|application requirements|eligibility|transcript|diploma|gpa|prerequisite|deadline|required documents|steps to apply)\b",
    ],
    ResearchCategory.LANGUAGE: [
        r"\b(toefl|ielts|duolingo|pte(?: academic)?|english (?:language )?proficiency|language of instruction|medium of instruction|english-medium|language requirement[s]?|proficiency waiver|exemption)\b",
    ],
    ResearchCategory.TUITION: [
        r"\b(tuition|fees|cost of attendance|cost per credit|per semester|per year|mandatory fees|resident|non-resident|program fee|\$\s?\d+|\d+\s*usd)\b",
    ],
}

_INSTITUTION_STOP_WORDS = {
    "the", "of", "at", "and", "university", "college", "institute",
    "school", "system", "campus", "state",
}


def _normalize_for_match(value: str) -> str:
    """Metni aksan ve noktalama farklarından arındırarak eşleştirmeye hazırla."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _institution_name_matches(university_name: str, title: str, text: str) -> bool:
    """Başlık veya içerikte kurum adının ayırt edici bölümünü doğrula."""
    expected = _normalize_for_match(university_name)
    haystack = _normalize_for_match(f"{title} {text[:8000]}")
    if not expected or not haystack:
        return False
    if expected in haystack:
        return True

    significant = [
        token for token in expected.split()
        if token not in _INSTITUTION_STOP_WORDS and len(token) >= 3
    ]
    return bool(significant) and any(
        re.search(rf"\b{re.escape(token)}\b", haystack) for token in significant
    )

# Reddedilecek olumsuz desenler (blog, financial aid only vb.)
REJECTION_PATTERNS: dict[ResearchCategory, list[str]] = {
    ResearchCategory.PROGRAM: [
        r"\b(blog post|news article|press release)\b",
    ],
    ResearchCategory.LANGUAGE: [
        r"\b(department of english|english major|english literature|english department)\b",
    ],
    ResearchCategory.TUITION: [
        r"\b(only financial aid|scholarship news)\b",
    ],
}


def validate_rules(
    candidate: CandidateURL,
    university_name: str,
    official_domain: str,
) -> tuple[bool, dict[str, bool], Optional[str]]:
    """Aday URL için kural tabanlı doğrulama yap.

    Args:
        candidate: İndirilmiş aday URL
        university_name: Üniversite adı
        official_domain: Üniversitenin resmî domain adı

    Returns:
        (rule_passed, details_dict, rejection_reason) üçlüsü
    """
    details: dict[str, bool] = {}

    # 1. HTTP 200 kontrolü
    http_ok = candidate.http_status == 200
    details["http_200"] = http_ok
    if not http_ok:
        return False, details, f"HTTP hatası: status={candidate.http_status}"

    # 2. Güvenli URL kontrolü
    safe_ok = is_safe_url(candidate.url)
    details["safe_url"] = safe_ok
    if not safe_ok:
        return False, details, "Güvenlik kuralı: Tehlikeli URL"

    # 3. Resmî domain kontrolü
    domain_ok = is_official_domain(candidate.url, official_domain)
    details["official_domain"] = domain_ok
    if not domain_ok:
        return False, details, "URL resmî üniversite domainine ait değil"

    # Ana sayfa istenen bilgiyi doğrudan gösteren bir kaynak değildir.
    direct_source = not is_homepage_only(candidate.url)
    details["direct_source"] = direct_source
    if not direct_source:
        return False, details, "Üniversite ana sayfası doğrudan bilgi kaynağı değil"

    # 4. Sayfa metni kontrolü
    text = (candidate.extracted_text or "").lower()
    if not text:
        return False, details, "Sayfa metni boş veya çıkarılamadı"

    # 5. Kurum adı başlık veya içerik eşleşmesi
    institution_ok = _institution_name_matches(
        university_name,
        candidate.page_title or "",
        candidate.extracted_text or "",
    )
    details["institution_name"] = institution_ok
    if not institution_ok:
        return False, details, "Kurum adı sayfa başlığında veya içeriğinde doğrulanamadı"

    # 6. Kategoriye özel zorunlu kanıt deseni kontrolü
    patterns = MANDATORY_PATTERNS.get(candidate.category, [])
    evidence_found = True
    for pat in patterns:
        if not re.search(pat, text, re.IGNORECASE):
            evidence_found = False
            break

    details["mandatory_evidence"] = evidence_found
    if not evidence_found:
        return False, details, f"{candidate.category.value.upper()} için sayfada zorunlu kanıt desenleri bulunamadı"

    # 7. Olumsuz (reddedilecek) desen kontrolü
    neg_patterns = REJECTION_PATTERNS.get(candidate.category, [])
    for neg_pat in neg_patterns:
        if re.search(neg_pat, text, re.IGNORECASE):
            # Dil için: "department of english" var ama TOEFL/IELTS de varsa reddetme
            if candidate.category == ResearchCategory.LANGUAGE:
                has_test = bool(re.search(r"\b(toefl|ielts|duolingo|pte|english proficiency)\b", text, re.IGNORECASE))
                if not has_test:
                    return False, details, "Yalnızca İngilizce bölümü/bölüm sayfası — dil şartı belgesi değil"

    return True, details, None
