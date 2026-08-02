"""Anahtarsız resmî site keşfi: sitemap ve ana sayfa bağlantıları."""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.domain_utils import (
    deduplicate_urls,
    is_homepage_only,
    is_official_domain,
    is_safe_url,
    normalize_url,
)
from src.fetch.page_fetcher import _fetch_with_browser, _fetch_with_curl, _looks_like_challenge
from src.models import ResearchCategory

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

URL_HINTS: dict[ResearchCategory, tuple[str, ...]] = {
    ResearchCategory.PROGRAM: (
        "program", "degree", "major", "academics", "areas-of-study", "catalog",
    ),
    ResearchCategory.ADMISSION: (
        "admission", "apply", "application", "requirements", "international", "catalog",
    ),
    ResearchCategory.LANGUAGE: (
        "english", "proficiency", "toefl", "ielts", "duolingo", "international", "admission", "catalog",
    ),
    ResearchCategory.TUITION: (
        "tuition", "fees", "cost", "attendance", "bursar", "financial", "catalog",
    ),
}

URL_PENALTIES: dict[ResearchCategory, tuple[str, ...]] = {
    ResearchCategory.PROGRAM: (
        "news", "event", "blog", "course-only",
    ),
    ResearchCategory.ADMISSION: (
        "apply-now", "application-login", "login", "portal", "financial-aid",
        "scholarship", "student-visa", "pre-arrival",
    ),
    ResearchCategory.LANGUAGE: (
        "english-language-center", "writing-center", "esl-support", "english-major",
    ),
    ResearchCategory.TUITION: (
        "financial-aid", "scholarship", "fafsa", "payment-portal",
        "net-price-calculator",
    ),
}

_NON_DOCUMENT_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".mp3", ".mp4", ".mov", ".avi", ".zip", ".css", ".js",
}

_CRAWL_ROUTE_HINTS = (
    "academic", "admission", "international", "student", "program", "degree",
    "catalog", "bulletin", "handbook", "policy", "requirement", "tuition",
    "fee", "cost", "bursar", "registrar", "graduate", "undergraduate",
)


def extract_crawl_links(
    html: bytes | str,
    page_url: str,
    official_domain: str,
    category: ResearchCategory,
) -> list[tuple[int, str]]:
    """Bir sayfadaki güvenli resmî bağlantıları kategori puanıyla çıkar."""
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, int] = {}
    for anchor in soup.find_all("a", href=True):
        raw_href = anchor.get("href", "").strip()
        if not raw_href or raw_href.startswith(("#", "mailto:", "tel:")):
            continue
        url = normalize_url(urljoin(page_url, raw_href))
        if not is_safe_url(url) or not is_official_domain(url, official_domain):
            continue
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in _NON_DOCUMENT_EXTENSIONS):
            continue
        link_text = anchor.get_text(" ", strip=True)
        score = url_relevance_score(url, category, link_text)
        found[url] = max(found.get(url, -999), score)
    return sorted(
        ((score, url) for url, score in found.items()),
        key=lambda item: (-item[0], item[1]),
    )


async def deep_crawl_official_site(
    official_domain: str,
    category: ResearchCategory,
    seed_urls: list[str] | None = None,
    *,
    max_pages: int = 40,
    max_depth: int = 3,
    concurrency: int = 6,
    max_candidates: int = 30,
) -> list[str]:
    """Resmî domain içinde kategori odaklı, sınırlı ve katmanlı tarama yap.

    Her şeyi körlemesine indirmek yerine kategori/katalog yollarını önceliklendirir.
    Yalnızca gerçekten bir sayfada veya arama/sitemap sonucunda görülen URL'leri
    döndürür; URL yolu üretmez.
    """
    if not official_domain or max_pages <= 0 or max_depth < 0:
        return []

    base_url = normalize_url(official_domain)
    seeds = deduplicate_urls([base_url, *(seed_urls or [])])
    frontier: list[tuple[str, int]] = [(url, 0) for url in seeds]
    seen: set[str] = set()
    candidates: list[str] = [
        url for url in seeds
        if not is_homepage_only(url) and url_relevance_score(url, category) > 0
    ]
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async with httpx.AsyncClient(
        timeout=12.0,
        follow_redirects=True,
        headers=HEADERS,
    ) as client:

        async def fetch_html(url: str) -> tuple[str, int, str, bytes] | None:
            if urlparse(url).path.lower().endswith(".pdf"):
                return None
            async with semaphore:
                try:
                    response = await client.get(url)
                    status = response.status_code
                    final_url = normalize_url(str(response.url))
                    content_type = response.headers.get("content-type", "").lower()
                    content = response.content
                    if status in (403, 429):
                        fallback = await _fetch_with_curl(
                            url, 12, 5, 5 * 1024 * 1024
                        )
                        if fallback:
                            status, final_url, content_type, content = fallback
                    if (
                        status != 200
                        or not is_official_domain(final_url, official_domain)
                        or "html" not in content_type
                        or _looks_like_challenge(content)
                    ):
                        return None
                    return final_url, status, content_type, content
                except Exception:
                    return None

        while frontier and len(seen) < max_pages:
            # En alakalı yolları önce tara; aynı derinlikte gereksiz dalları buda.
            frontier.sort(
                key=lambda item: (
                    item[1],
                    -url_relevance_score(item[0], category),
                    item[0],
                )
            )
            batch: list[tuple[str, int]] = []
            while frontier and len(batch) < max(1, concurrency):
                url, depth = frontier.pop(0)
                if url in seen or depth > max_depth:
                    continue
                seen.add(url)
                batch.append((url, depth))
                if len(seen) >= max_pages:
                    break
            if not batch:
                continue

            fetched = await asyncio.gather(
                *(fetch_html(url) for url, _ in batch),
                return_exceptions=True,
            )
            for (_, depth), page in zip(batch, fetched):
                if not page or isinstance(page, Exception):
                    continue
                final_url, _, _, content = page
                for score, linked_url in extract_crawl_links(
                    content, final_url, official_domain, category
                ):
                    if score > 0:
                        candidates.append(linked_url)
                    if depth >= max_depth or linked_url in seen:
                        continue
                    route_text = linked_url.lower()
                    if score > 0 or any(hint in route_text for hint in _CRAWL_ROUTE_HINTS):
                        frontier.append((linked_url, depth + 1))

    result = rank_candidate_urls(candidates, category, limit=max_candidates)
    logger.info(
        "Derin tarama tamamlandı: %s | kategori=%s | taranan=%d | aday=%d",
        official_domain,
        category.value,
        len(seen),
        len(result),
    )
    return result


def url_relevance_score(url: str, category: ResearchCategory, link_text: str = "") -> int:
    """URL yolu ve bağlantı metnine göre ucuz, deterministik öncelik puanı."""
    value = f"{url} {link_text}".lower()
    score = sum(3 for hint in URL_HINTS[category] if hint in value)
    if url.lower().endswith(".pdf"):
        score += 2
    if any(term in value for term in ("catalog", "handbook", "bulletin")):
        score += 2
    path = urlparse(url).path.strip("/")
    if path:
        score += 1
    if any(term in value for term in ("news", "event", "blog", "calendar")):
        score -= 4
    score -= sum(5 for term in URL_PENALTIES[category] if term in value)
    return score


def rank_candidate_urls(
    urls: list[str],
    category: ResearchCategory,
    limit: int = 12,
) -> list[str]:
    """Aday sayısını sınırlayıp kategori açısından güçlü URL'leri öne al."""
    unique = [
        url for url in deduplicate_urls(urls)
        if not any(urlparse(url).path.lower().endswith(ext) for ext in _NON_DOCUMENT_EXTENSIONS)
    ]
    ranked = sorted(
        enumerate(unique),
        key=lambda item: (-url_relevance_score(item[1], category), item[0]),
    )
    return [url for _, url in ranked[:limit]]


async def discover_homepage_links(
    official_domain: str,
    category: ResearchCategory,
    limit: int = 15,
) -> list[str]:
    """Resmî ana sayfadaki kategoriyle ilgili gerçek bağlantıları çıkar."""
    base_url = normalize_url(official_domain)
    found: list[tuple[int, str]] = []
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=HEADERS) as client:
            response = await client.get(base_url)
        status = response.status_code
        final_base = str(response.url)
        content = response.content
        if status in (403, 429):
            curl_result = await _fetch_with_curl(base_url, 12, 5, 5 * 1024 * 1024)
            if curl_result:
                status, final_base, _, content = curl_result
        if status in (403, 429) or _looks_like_challenge(content):
            browser_result = await _fetch_with_browser(base_url, 15, 5 * 1024 * 1024)
            if browser_result:
                status, final_base, _, content = browser_result
        if status != 200 or _looks_like_challenge(content):
            return []
        soup = BeautifulSoup(content, "lxml")
        for anchor in soup.find_all("a", href=True):
            url = normalize_url(urljoin(final_base, anchor.get("href", "")))
            text = anchor.get_text(" ", strip=True)
            if not is_safe_url(url) or not is_official_domain(url, official_domain):
                continue
            score = url_relevance_score(url, category, text)
            if score > 0:
                found.append((score, url))
    except Exception as exc:
        logger.info("Ana sayfa bağlantı keşfi başarısız (%s): %s", official_domain, exc)
        return []

    found.sort(key=lambda item: item[0], reverse=True)
    return deduplicate_urls([url for _, url in found])[:limit]


async def discover_sitemap_urls(
    official_domain: str,
    category: ResearchCategory,
    limit: int = 30,
) -> list[str]:
    """robots.txt ve sitemap dosyalarından kategoriyle ilgili resmî URL'leri bul."""
    base_url = normalize_url(official_domain)
    sitemap_queue = [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
    ]
    found: list[str] = []
    inspected: set[str] = set()

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=HEADERS) as client:
            try:
                robots = await client.get(urljoin(base_url, "/robots.txt"))
                robots_status = robots.status_code
                robots_content = robots.content
                if robots_status in (403, 429):
                    curl_result = await _fetch_with_curl(
                        urljoin(base_url, "/robots.txt"), 12, 5, 2 * 1024 * 1024
                    )
                    if curl_result:
                        robots_status, _, _, robots_content = curl_result
                if robots_status == 200:
                    sitemap_queue.extend(
                        match.strip()
                        for match in re.findall(
                            r"(?im)^\s*Sitemap:\s*(\S+)",
                            robots_content.decode("utf-8", errors="replace"),
                        )
                    )
            except Exception:
                pass

            while sitemap_queue and len(inspected) < 10 and len(found) < limit * 3:
                sitemap_url = normalize_url(sitemap_queue.pop(0))
                if sitemap_url in inspected or not is_official_domain(sitemap_url, official_domain):
                    continue
                inspected.add(sitemap_url)
                try:
                    response = await client.get(sitemap_url)
                    status = response.status_code
                    content = response.content
                    if status in (403, 429):
                        curl_result = await _fetch_with_curl(
                            sitemap_url, 12, 5, 8 * 1024 * 1024
                        )
                        if curl_result:
                            status, _, _, content = curl_result
                    if status != 200 or not content:
                        continue
                    root = ET.fromstring(content)
                except Exception:
                    continue

                locations = [
                    (node.text or "").strip()
                    for node in root.iter()
                    if node.tag.lower().endswith("loc") and (node.text or "").strip()
                ]
                is_index = root.tag.lower().endswith("sitemapindex")
                if is_index:
                    for location in locations:
                        if len(sitemap_queue) < 20 and is_official_domain(location, official_domain):
                            sitemap_queue.append(location)
                    continue

                for location in locations:
                    url = normalize_url(location)
                    if (
                        is_safe_url(url)
                        and is_official_domain(url, official_domain)
                        and url_relevance_score(url, category) > 0
                    ):
                        found.append(url)
    except Exception as exc:
        logger.info("Sitemap keşfi başarısız (%s): %s", official_domain, exc)

    return rank_candidate_urls(found, category, limit=limit)
