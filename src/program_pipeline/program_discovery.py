"""Program keşif motoru — üniversite sitesindeki program sayfalarını bulur.

Mevcut altyapıyı (PageFetcher, SourceSearcher, sitemap, deep crawl) kullanır.
Haber/blog/personel/etkinlik gibi sayfaları filtreler.
Aynı resmî domain veya doğrulanmış resmî alt-domainle sınırlı.
Canonical URL kontrolü ve tracking parametresi temizleme dahildir.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from src.config import get_settings
from src.domain_utils import (
    extract_domain,
    is_official_domain,
    is_safe_url,
    normalize_url,
    deduplicate_urls,
)
from src.fetch.page_fetcher import PageFetcher
from src.program_pipeline.content_sections import extract_html_sections
from src.program_pipeline.program_quality import looks_like_program_link
from src.search.site_discovery import (
    discover_sitemap_urls,
    discover_homepage_links,
    deep_crawl_official_site,
)
from src.search.web_searcher import search_web_for_domain
from src.search.query_builder import build_search_queries
from src.models import ResearchCategory

logger = logging.getLogger(__name__)

# Program URL'si olduğunu gösteren kalıplar
_PROGRAM_URL_PATTERNS = [
    re.compile(r"/(program|degree|major|academic|study|school|graduate|undergraduate|"
               r"masters?|bachelors?|doctoral|phd|courses?|curriculum|catalog|division)/", re.I),
    re.compile(r"/(m\.div|mdiv|d\.min|dmin|thm|th\.m|m\.th|mts|mbs|dpts)/", re.I),
]

# Program sayfası başlık kalıpları
_PROGRAM_TITLE_PATTERNS = re.compile(
    r"\b(program|degree|major|study|curriculum|course|certificate|diploma|"
    r"master|bachelor|doctoral|doctor|phd|associate)\b",
    re.I,
)

# Filtrele — bu URL'ler program sayfası değil
_NOISE_URL_PATTERNS = re.compile(
    r"/(?:"
    r"courses?|insights?|blog|news|articles?|events?|calendar|press|release|announcements?|"
    r"faculty|staff|directory|people|contact|about|team|history|"
    r"alumni|donate|giving|athletics|sport|career-services|"
    r"job|employment|hr|human-resources|"
    r"library|bookstore|parking|campus-map|visit|tour|"
    r"login|sign-in|myaccount|portal|webmail|"
    r"search|author|authors|tag|category|archives?|catalogs?|catalog|feed|rss|wp-json|"
    r"podcasts?|sitemap\.xml|register|registration|policies|policy|resources?|"
    r"schedule|office-hours|licensure|accreditation|content\.php"
    r")(?:/|$)"
    r"|\.pdf$",
    re.I,
)

# Tracking parametreleri (URL'den temizlenecek)
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "referrer",
    "_ga", "mc_cid", "mc_eid",
}


def _strip_tracking_params(url: str) -> str:
    """URL'den tracking parametrelerini temizle."""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=False)
        cleaned_qs = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
        new_query = urlencode(cleaned_qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query, fragment=""))
    except Exception:
        return url


def _is_program_url(url: str, title: str = "") -> bool:
    """URL'nin program sayfasına ait olup olmadığını kontrol et."""
    if _NOISE_URL_PATTERNS.search(url):
        return False

    return looks_like_program_link(url, title)


async def discover_program_pages(
    official_domain: str,
    known_program_url: Optional[str] = None,
    university_name: str = "",
    fetcher: Optional[PageFetcher] = None,
    max_pages: int = 60,
    max_depth: int = 3,
) -> list[str]:
    """Üniversite sitesindeki program sayfalarını keşfet.

    Args:
        official_domain: Üniversitenin resmî domain'i (örn: phoenixseminary.edu)
        known_program_url: URL kaynak Excel'den gelen bilinen URL (sadece tohum sayfa)
        university_name: Üniversite adı (arama sorguları için)
        fetcher: Mevcut PageFetcher örneği (None ise yeni oluşturulur)
        max_pages: Sitede gezilecek maksimum sayfa
        max_depth: Maksimum bağlantı derinliği

    Returns:
        Program sayfası URL'leri listesi (resmî domain, tekilleştirilmiş)
    """
    if not official_domain:
        return []

    settings = get_settings()
    fetcher = fetcher or PageFetcher()
    candidates: list[str] = []

    # 1. Sitemap'ten program URL'leri
    try:
        sitemap_urls = await discover_sitemap_urls(official_domain, ResearchCategory.PROGRAM)
        candidates.extend(sitemap_urls)
    except Exception as e:
        logger.debug("Sitemap hata (%s): %s", official_domain, e)

    # 2. Ana sayfa bağlantıları
    try:
        homepage_links = await discover_homepage_links(official_domain, ResearchCategory.PROGRAM)
        candidates.extend(homepage_links)
    except Exception as e:
        logger.debug("Homepage links hata (%s): %s", official_domain, e)

    # 3. Web araması
    if university_name:
        try:
            queries = build_search_queries(university_name, official_domain, ResearchCategory.PROGRAM)
            search_tasks = [
                search_web_for_domain(official_domain, q)
                for q in queries[:2]
            ]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            for group in search_results:
                if isinstance(group, list):
                    candidates.extend(group)
        except Exception as e:
            logger.debug("Web arama hata (%s): %s", official_domain, e)

    # 4. Derin tarama
    try:
        deep_urls = await deep_crawl_official_site(
            official_domain=official_domain,
            category=ResearchCategory.PROGRAM,
            seed_urls=candidates[:10],
            max_pages=max_pages,
            max_depth=max_depth,
            concurrency=settings.program_domain_concurrency,
            max_candidates=150,
        )
        candidates.extend(deep_urls)
    except Exception as e:
        logger.debug("Derin tarama hata (%s): %s", official_domain, e)

    # 5. Filtrele: resmî domain, tracking parametrelerini temizle ve yalnızca
    # güçlü tekil program adaylarını tut. Bilinen program listesi URL'si keşif
    # tohumu olarak kalabilir; listenin kendisi program satırı yapılmaz.
    cleaned: list[str] = []
    for url in candidates:
        url = _strip_tracking_params(url)
        url = normalize_url(url)
        if not is_safe_url(url):
            continue
        if not is_official_domain(url, official_domain):
            continue
        if _NOISE_URL_PATTERNS.search(url):
            continue
        if not _is_program_url(url):
            continue
        cleaned.append(url)

    # 6. Tekilleştir ve sırala
    seen: set[str] = set()
    result: list[str] = []

    for url in cleaned:
        if url in seen:
            continue
        seen.add(url)
        result.append(url)

    # Program URL kalıbı olanları öne al
    result.sort(key=lambda u: (0 if any(p.search(u) for p in _PROGRAM_URL_PATTERNS) else 1))

    logger.info(
        "%s: %d program sayfası adayı keşfedildi.",
        official_domain, len(result),
    )

    return result[:settings.program_max_programs_per_uni]


async def fetch_and_discover_programs(
    program_url: str,
    fetcher: PageFetcher,
    official_domain: str,
) -> list[str]:
    """Bir program listesi sayfasından bireysel program URL'lerini çıkar.

    Ana programlar listesi sayfasını indirip içindeki program link'lerini bulur.
    Her link resmî domain'de ve program URL kalıbına uygun olmalı.
    """
    try:
        result = await fetcher.fetch_candidate(program_url, ResearchCategory.PROGRAM)
        raw_html = getattr(result, "raw_html", None) or getattr(result, "extracted_text", None)
        if not raw_html:
            return []

        sections = extract_html_sections(raw_html, program_url)
        found_urls: list[str] = []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#"):
                continue

            # Göreli URL'yi mutlak yap
            from urllib.parse import urljoin
            abs_url = urljoin(program_url, href)
            abs_url = _strip_tracking_params(abs_url)
            abs_url = normalize_url(abs_url)

            if not is_safe_url(abs_url):
                continue
            if not is_official_domain(abs_url, official_domain):
                continue
            if _NOISE_URL_PATTERNS.search(abs_url):
                continue

            title = a.get_text(strip=True)
            if _is_program_url(abs_url, title):
                found_urls.append(abs_url)

        return deduplicate_urls(found_urls)

    except Exception as e:
        logger.warning("Program URL çıkarma hatası (%s): %s", program_url, e)
        return []
