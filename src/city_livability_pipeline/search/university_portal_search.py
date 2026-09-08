"""Şehir & Yaşam Rehberi — Üniversite Resmî Portal Arayıcısı.

Üniversite domain'i üzerinde SKS (Sağlık Kültür Spor), Yurtlar, Kütüphane,
Burs ve Yabancı Diller (YDYO) sayfalarını doğrudan keşfeder.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.domain_utils import extract_domain, is_official_domain, is_safe_url
from src.search.web_searcher import search_web_for_domain

logger = logging.getLogger(__name__)

PORTAL_KEYWORDS = {
    "yemekhane": ["sks yemek", "yemekhane", "günlük yemek listesi", "öğün ücreti"],
    "yurt": ["yurtlar müdürlüğü", "öğrenci yurdu kapasite", "yurt ücretleri"],
    "kutuphane": ["kütüphane ve dokümantasyon", "çalışma saatleri", "7/24 kütüphane"],
    "burs": ["burs yönergesi", "başarı bursu", "barınma bursu", "ihtiyaç bursu"],
    "hazirlik": ["yabancı diller yüksekokulu", "zorunlu hazırlık", "hazırlık muafiyet"],
    "ulasim_ring": ["kampüs ulaşım", "ring servis saatleri", "yerleşke ulaşım"],
}


async def discover_university_portal_url(
    official_website: str,
    portal_type: str,
) -> list[str]:
    """Üniversite resmî sitesi üzerinde hedef portalların URL'lerini keşfet."""
    domain = extract_domain(official_website)
    if not domain:
        return []

    keywords = PORTAL_KEYWORDS.get(portal_type, [portal_type])
    query = f"site:{domain} " + " OR ".join(f'"{kw}"' for kw in keywords[:2])

    try:
        found_urls = await search_web_for_domain(domain, query, max_results=5)
        valid = [
            u for u in found_urls
            if is_safe_url(u) and is_official_domain(u, domain)
        ]
        return valid[:3]
    except Exception as e:
        logger.debug("Üniversite portal keşif hatası (%s - %s): %s", domain, portal_type, e)
        return []
