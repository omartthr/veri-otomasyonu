"""Anahtarsız arama keşfi — DuckDuckGo, Bing ve opsiyonel Google fallback.

Üniversitenin resmî domaini için doğrudan arama motoru araması yapar:
`site:domain.edu category_keywords`
Bulunan GERÇEK canlı linkleri ayıklar.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, unquote

import httpx
from bs4 import BeautifulSoup

from src.domain_utils import extract_domain, is_official_domain, is_safe_url, normalize_url

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
}


async def search_web_for_domain(
    official_domain: str,
    query_text: str,
    max_results: int = 10,
) -> list[str]:
    """Arama motoru sorgusu çalıştır ve domain üzerindeki gerçek canlı URL'leri bul."""
    domain = extract_domain(official_domain)
    if not domain:
        return []

    found_urls: set[str] = set()
    scoped_query = query_text if "site:" in query_text.lower() else f"site:{domain} {query_text}"

    # 1. DuckDuckGo HTML Arama
    ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(scoped_query)}"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=HEADERS) as client:
            resp = await client.get(ddg_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    # DDG yönlendirme URL'lerini çöz: /l/?uddg=https%3A%2F%2F...
                    if "/l/?" in href and "uddg=" in href:
                        match = re.search(r"uddg=([^&]+)", href)
                        if match:
                            href = unquote(match.group(1))

                    norm = normalize_url(href)
                    if (
                        is_safe_url(norm)
                        and is_official_domain(norm, official_domain)
                    ):
                        found_urls.add(norm)
    except Exception as e:
        logger.warning(f"DuckDuckGo araması uyarısı ({official_domain}): {e}")

    # 2. Bing HTML Arama Fallback
    if len(found_urls) < 3:
        bing_url = f"https://www.bing.com/search?q={quote_plus(scoped_query)}"
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=HEADERS) as client:
                resp = await client.get(bing_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        norm = normalize_url(href)
                        if (
                            is_safe_url(norm)
                            and is_official_domain(norm, official_domain)
                        ):
                            found_urls.add(norm)
        except Exception as e:
            logger.warning(f"Bing araması uyarısı ({official_domain}): {e}")

    # 3. Google HTML fallback — anahtarsız kullanım engellenirse sessizce atlanır.
    if len(found_urls) < 3:
        google_url = f"https://www.google.com/search?q={quote_plus(scoped_query)}&num=10&filter=0"
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=HEADERS) as client:
                resp = await client.get(google_url)
                if resp.status_code == 200 and "unusual traffic" not in resp.text.lower():
                    soup = BeautifulSoup(resp.text, "lxml")
                    for anchor in soup.find_all("a", href=True):
                        href = anchor["href"]
                        if href.startswith("/url?"):
                            match = re.search(r"[?&]q=([^&]+)", href)
                            if match:
                                href = unquote(match.group(1))
                        norm = normalize_url(href)
                        if is_safe_url(norm) and is_official_domain(norm, official_domain):
                            found_urls.add(norm)
        except Exception as e:
            logger.info(f"Google fallback kullanılamadı ({official_domain}): {e}")

    logger.info(f"Gerçek web araması ({domain} - '{query_text}'): {len(found_urls)} URL bulundu.")
    return list(found_urls)[:max_results]
