"""Her kategori için geniş ve birbirini tamamlayan arama sorguları üretir."""

from __future__ import annotations

from src.domain_utils import extract_domain
from src.models import ResearchCategory

# Kategori bazında arama terimleri
SEARCH_TERMS: dict[ResearchCategory, list[str]] = {
    ResearchCategory.PROGRAM: [
        "programs",
        "degree",
        "academics",
        "academic programs",
        "areas of study",
        "majors",
        "undergraduate programs",
        "graduate programs",
    ],
    ResearchCategory.ADMISSION: [
        "admissions",
        "admission requirements",
        "entry requirements",
        "how to apply",
        "application requirements",
        "required documents",
        "eligibility transcript GPA",
        "international admission requirements",
    ],
    ResearchCategory.LANGUAGE: [
        "English proficiency",
        "English language requirements",
        "TOEFL",
        "IELTS",
        "Duolingo",
        "PTE",
        "minimum score proof of proficiency",
        "foreign language graduation requirement",
    ],
    ResearchCategory.TUITION: [
        "tuition",
        "tuition and fees",
        "cost of attendance",
        "program cost",
        "cost per credit",
        "mandatory fees",
        "tuition schedule",
        "resident non-resident",
    ],
}


def build_search_queries(
    university_name: str,
    official_domain: str,
    category: ResearchCategory,
) -> list[str]:
    """Belirtilen kategori için arama sorguları üret.

    4 tür sorgu:
    1. site:resmi-domain hedef terimler
    2. Üniversite adı + hedef terimler
    3. site:resmi-domain filetype:pdf hedef terimler
    4. Üniversite adı + academic catalog + hedef terimler
    """
    terms = SEARCH_TERMS[category]
    queries: list[str] = []
    official_host = extract_domain(official_domain)

    primary_terms = " ".join(terms[:3])
    evidence_terms = " ".join(terms[3:6])

    if official_host:
        queries.append(f"site:{official_host} {primary_terms}")
        queries.append(f"site:{official_host} {evidence_terms}")
        queries.append(
            f"site:{official_host} (catalog OR handbook OR bulletin) {terms[0]}"
        )
        queries.append(f"site:{official_host} filetype:pdf {primary_terms}")
        queries.append(
            f"site:{official_host} filetype:pdf (catalog OR handbook) {evidence_terms}"
        )

    queries.append(f'"{university_name}" {primary_terms}')
    queries.append(f'"{university_name}" academic catalog {evidence_terms}')

    return queries
