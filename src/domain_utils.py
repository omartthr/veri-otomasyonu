"""Domain ve URL yardımcı fonksiyonları.

Resmî domain kontrolü, URL normalizasyonu, güvenlik doğrulaması
ve üçüncü taraf site tespiti işlemlerini içerir.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from urllib.parse import urlparse, urlunparse, urljoin

logger = logging.getLogger(__name__)

# ──────────────── Engellenen üçüncü taraf domainler ────────────────

BLOCKED_DOMAINS: set[str] = {
    "wikipedia.org",
    "en.wikipedia.org",
    "tr.wikipedia.org",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "tiktok.com",
    "studyportals.com",
    "scholarships.com",
    "topuniversities.com",
    "usnews.com",
    "niche.com",
    "collegedunia.com",
    "shiksha.com",
    "hotcoursesabroad.com",
    "mastersportal.com",
    "bachelorsportal.com",
    "phdportal.com",
    "universityguru.com",
    "4icu.org",
    "timeshighereducation.com",
    "reddit.com",
    "quora.com",
}

# Arama motoru domainleri — sonuç sayfası URL olarak kaydedilmez
SEARCH_ENGINE_DOMAINS: set[str] = {
    "google.com",
    "google.com.tr",
    "bing.com",
    "yahoo.com",
    "duckduckgo.com",
    "yandex.com",
    "baidu.com",
}

# Tehlikeli protokoller
DANGEROUS_SCHEMES: set[str] = {"file", "ftp", "data", "javascript", "vbscript"}


# ──────────────── Domain çıkarma ve normalizasyon ────────────────


def extract_domain(url: str) -> str:
    """URL'den domain adını çıkar ve normalize et.

    Örnek: "https://www.example.edu/page" → "example.edu"
    """
    if not url:
        return ""

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # www. önekini kaldır
        hostname = hostname.lower().strip()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname
    except Exception:
        return ""


def normalize_url(url: str) -> str:
    """URL'yi normalize et: şema ekle, fragment kaldır, trailing slash standardize et.

    Aynı sayfayı gösteren farklı URL varyantlarını birleştirmek için kullanılır.
    """
    if not url:
        return ""

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        path = parsed.path
        if not path:
            path = "/"
        elif not path.endswith("/"):
            last_segment = path.rsplit("/", 1)[-1]
            # PDF/XML gibi gerçek dosya URL'lerine yapay '/' ekleme.
            if not re.search(r"\.[a-zA-Z0-9]{1,10}$", last_segment):
                path += "/"
        # Fragment (#) kaldır
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            "",  # fragment kaldırıldı
        ))
        return normalized
    except Exception:
        return url


def is_same_domain(domain1: str, domain2: str) -> bool:
    """İki domainin aynı kuruluşa ait olup olmadığını kontrol et.

    Alt alan adları ve www varyasyonları dikkate alınır.
    Örnek: "admissions.example.edu" ve "example.edu" → True
    """
    d1 = extract_domain(domain1) if "/" in domain1 else domain1.lower().strip()
    d2 = extract_domain(domain2) if "/" in domain2 else domain2.lower().strip()

    if not d1 or not d2:
        return False

    # Tam eşleşme
    if d1 == d2:
        return True

    # Biri diğerinin alt alan adı mı?
    if d1.endswith("." + d2) or d2.endswith("." + d1):
        return True

    return False


def is_official_domain(url: str, official_website: str | list[str] | set[str]) -> bool:
    """URL'nin üniversitenin resmî alan adına ait olup olmadığını kontrol et.

    Args:
        url: Kontrol edilecek URL
        official_website: E sütunundaki resmî web sitesi veya resmî domainler kümesi/listesi

    Returns:
        URL resmî domain veya alt alan adına aitse True
    """
    if not url or not official_website:
        return False

    url_domain = extract_domain(url)
    if not url_domain:
        return False

    targets = official_website if isinstance(official_website, (list, set, tuple)) else [official_website]
    for target in targets:
        if not target:
            continue
        off_domain = extract_domain(target) if ("/" in target or "." in target) else target
        if off_domain and is_same_domain(url_domain, off_domain):
            return True

    return False


def is_blocked_domain(url: str) -> bool:
    """URL'nin engellenmiş üçüncü taraf domainlerden birine ait olup olmadığını kontrol et."""
    domain = extract_domain(url)
    if not domain:
        return True  # Domain çıkarılamıyorsa engelle

    for blocked in BLOCKED_DOMAINS:
        if domain == blocked or domain.endswith("." + blocked):
            return True

    return False


def is_search_engine(url: str) -> bool:
    """URL'nin bir arama motoru sonuç sayfası olup olmadığını kontrol et."""
    domain = extract_domain(url)
    if not domain:
        return False

    for se_domain in SEARCH_ENGINE_DOMAINS:
        if domain == se_domain or domain.endswith("." + se_domain):
            return True

    return False


def is_safe_url(url: str) -> bool:
    """URL'nin güvenli olup olmadığını kontrol et.

    Localhost, özel IP adresleri, file:// ve tehlikeli protokolleri engeller.
    """
    if not url:
        return False

    url = url.strip()

    # Önce ham URL'de tehlikeli şema kontrolü yap
    lower_url = url.lower()
    for dangerous in DANGEROUS_SCHEMES:
        if lower_url.startswith(dangerous + ":"):
            return False

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Yalnızca http ve https kabul et
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname or ""

    # Localhost kontrolü
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return False

    # Özel IP adresi kontrolü
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return False
    except ValueError:
        pass  # Hostname bir IP değil — sorun yok

    return True


def is_homepage_only(url: str) -> bool:
    """URL'nin yalnızca ana sayfa olup olmadığını kontrol et.

    Örnek: "https://example.edu/" veya "https://example.edu" → True
    """
    if not url:
        return False

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        return not path and not parsed.query
    except Exception:
        return False


def deduplicate_urls(urls: list[str]) -> list[str]:
    """URL listesini normalize ederek tekrarları kaldır.

    Sırayı korur; ilk görülen URL'yi tutar.
    """
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        normalized = normalize_url(url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(url)  # Orijinal URL'yi koru
    return result


def get_base_domain(domain: str) -> str:
    """Alt alan adını kaldırarak ana domain'i döndür.

    Örnek: "admissions.example.edu" → "example.edu"
    Not: Bu basit bir uygulama olup, TLD listesi kontrolü yapmaz.
    """
    if not domain:
        return ""

    parts = domain.lower().strip().split(".")
    if len(parts) <= 2:
        return domain.lower().strip()

    # .edu, .ac.uk gibi çift TLD'leri dikkate al
    common_double_tlds = {"ac.uk", "co.uk", "edu.tr", "edu.au", "ac.jp", "edu.cn"}
    if len(parts) >= 3:
        potential_double = f"{parts[-2]}.{parts[-1]}"
        if potential_double in common_double_tlds:
            return ".".join(parts[-3:])

    return ".".join(parts[-2:])
