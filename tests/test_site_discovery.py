"""Anahtarsız site keşfi sıralama testleri."""

from src.models import ResearchCategory
from src.search.site_discovery import (
    extract_crawl_links,
    rank_candidate_urls,
    url_relevance_score,
)


def test_language_urls_rank_above_homepage_and_news():
    urls = [
        "https://example.edu/",
        "https://example.edu/news/english-club/",
        "https://example.edu/international/english-proficiency/",
        "https://example.edu/admissions/",
    ]
    ranked = rank_candidate_urls(urls, ResearchCategory.LANGUAGE, limit=4)
    assert ranked[0] == "https://example.edu/international/english-proficiency/"


def test_pdf_catalog_receives_priority_bonus():
    pdf_score = url_relevance_score(
        "https://example.edu/catalog/2026-academic-catalog.pdf",
        ResearchCategory.PROGRAM,
    )
    homepage_score = url_relevance_score("https://example.edu/", ResearchCategory.PROGRAM)
    assert pdf_score > homepage_score


def test_candidate_limit_is_enforced():
    urls = [f"https://example.edu/programs/{index}/" for index in range(20)]
    assert len(rank_candidate_urls(urls, ResearchCategory.PROGRAM, limit=8)) == 8


def test_direct_admission_requirements_rank_above_apply_and_aid_pages():
    urls = [
        "https://example.edu/admissions/apply-now/",
        "https://example.edu/admissions/financial-aid/",
        "https://example.edu/admissions/undergraduate-application-requirements/",
    ]
    ranked = rank_candidate_urls(urls, ResearchCategory.ADMISSION)
    assert ranked[0].endswith("/undergraduate-application-requirements/")


def test_images_and_scripts_are_not_candidates():
    urls = [
        "https://example.edu/english-proficiency/",
        "https://example.edu/assets/toefl.jpg",
        "https://example.edu/assets/admissions.js",
    ]
    ranked = rank_candidate_urls(urls, ResearchCategory.LANGUAGE)
    assert ranked == ["https://example.edu/english-proficiency/"]


def test_deep_crawl_link_extraction_keeps_only_official_documents():
    html = """
    <html><body>
      <a href="/admissions/international/english-proficiency">English requirements</a>
      <a href="/catalog/2026-2027-catalog.pdf">Academic catalog PDF</a>
      <a href="https://other.edu/english-proficiency">Other university</a>
      <a href="/assets/logo.png">Logo</a>
      <a href="mailto:info@example.edu">Email</a>
    </body></html>
    """
    links = extract_crawl_links(
        html,
        "https://example.edu/international/",
        "https://example.edu",
        ResearchCategory.LANGUAGE,
    )
    urls = [url for _, url in links]
    assert "https://example.edu/admissions/international/english-proficiency/" in urls
    assert "https://example.edu/catalog/2026-2027-catalog.pdf" in urls
    assert not any("other.edu" in url for url in urls)
    assert not any(url.endswith(".png") for url in urls)
