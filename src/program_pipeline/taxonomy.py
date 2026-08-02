"""Sayfa ve URL Taksonomisi — Sayfaları amaçlarına göre sınıflandırır.

Yalnızca PROGRAM_DETAIL sınıfındaki sayfalar Excel'de program satırı oluşturabilir.
PROGRAM_LIST sayfaları program adaylarını keşfetmek için kullanılır.
CATALOG, ADMISSION_POLICY, LANGUAGE_POLICY, TUITION_POLICY sayfaları veri çıkarmak için kullanılır.
"""

from __future__ import annotations

import enum
import re
from urllib.parse import urlparse


class PageTaxonomy(str, enum.Enum):
    PROGRAM_LIST = "PROGRAM_LIST"
    PROGRAM_DETAIL = "PROGRAM_DETAIL"
    ADMISSION_POLICY = "ADMISSION_POLICY"
    LANGUAGE_POLICY = "LANGUAGE_POLICY"
    TUITION_POLICY = "TUITION_POLICY"
    CATALOG = "CATALOG"
    BLOG_NEWS = "BLOG_NEWS"
    ARCHIVE = "ARCHIVE"
    OTHER = "OTHER"


_BAD_PATH_PATTERNS = re.compile(
    r"/(?:"
    r"news|blog|insights?|events?|calendar|author|authors|tag|category|archive|"
    r"wp-json|feed|podcasts?|articles?|press|announcements?|"
    r"contact|about|people|faculty|staff|directory|alumni|giving|donate|"
    r"admissions?|apply|application|register|registration|tuition|fees?|"
    r"financial-aid|policies|privacy|terms|resources?|library|bookstore|"
    r"search|login|portal|schedule|office-hours|licensure|accreditation|"
    r"content\.php"
    r")(?:/|$)",
    re.I,
)

_LIST_PATH_PATTERNS = re.compile(
    r"/(?:degree-programs?|academic-programs?|programs?|academics?|degrees?|majors?|areas-of-study)/?$",
    re.I,
)

_CATALOG_PATTERNS = re.compile(
    r"\b(catalog|catalogs|bulletin|handbook)\b",
    re.I,
)

_BLOG_PATTERNS = re.compile(
    r"/(?:news|blog|insights?|article|articles|press-release|events?)/",
    re.I,
)

_ARCHIVE_PATTERNS = re.compile(
    r"/(?:archive|archives|past-catalogs)/|\b20\d{2}[-_/]?20\d{2}\b",
    re.I,
)


def classify_page_taxonomy(
    url: str,
    title: str = "",
    text_content: str = "",
    is_pdf: bool = False,
) -> PageTaxonomy:
    """Sayfanın taksonomik türünü belirler.

    Args:
        url: Sayfa URL'si
        title: Sayfa başlığı
        text_content: Sayfa metni
        is_pdf: Sayfa PDF mi?

    Returns:
        PageTaxonomy sınıflandırması
    """
    path = urlparse(url).path or "/"
    url_lower = url.lower()
    title_lower = title.lower()

    if _BLOG_PATTERNS.search(path):
        return PageTaxonomy.BLOG_NEWS

    if _ARCHIVE_PATTERNS.search(path) or _ARCHIVE_PATTERNS.search(title_lower):
        return PageTaxonomy.ARCHIVE

    if is_pdf or url_lower.endswith(".pdf") or _CATALOG_PATTERNS.search(path) or _CATALOG_PATTERNS.search(title_lower):
        return PageTaxonomy.CATALOG

    if re.search(r"/(?:admission|admissions|apply|requirements|how-to-apply)/?", path, re.I):
        return PageTaxonomy.ADMISSION_POLICY

    if re.search(r"/(?:english-proficiency|toefl|ielts|language-requirements)/?", path, re.I):
        return PageTaxonomy.LANGUAGE_POLICY

    if re.search(r"/(?:tuition|fees|cost-of-attendance|financial-aid)/?", path, re.I):
        return PageTaxonomy.TUITION_POLICY

    if _LIST_PATH_PATTERNS.search(path) or re.search(r"^(?:all\s+programs|degree\s+programs|program\s+finder|academics)$", title_lower, re.I):
        return PageTaxonomy.PROGRAM_LIST

    if _BAD_PATH_PATTERNS.search(path):
        return PageTaxonomy.OTHER

    return PageTaxonomy.PROGRAM_DETAIL
