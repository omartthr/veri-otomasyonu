"""Şehir & Yaşam Rehberi — Belediye Ulaşım ve Bilet Tarifesi Arayıcısı.

Büyükşehir ve il belediyelerinin resmî toplu taşıma, UKOME kararları
ve öğrenci bilet tarifesi sayfalarını keşfeder.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.search.web_searcher import search_web_for_domain

logger = logging.getLogger(__name__)

# Bilinen Büyükşehir Ulaşım Kurumları
METRO_TRANSIT_DOMAINS = {
    "İstanbul": ["iett.istanbul", "metro.istanbul", "istanbulkart.istanbul"],
    "Ankara": ["ego.gov.tr", "ankaray.com.tr"],
    "İzmir": ["eshot.gov.tr", "izmirmetro.com.tr", "izban.com.tr"],
    "Bursa": ["burulas.com.tr"],
    "Antalya": ["antalyaulasim.com.tr"],
    "Eskişehir": ["estram.com.tr"],
    "Konya": ["atus.konya.bel.tr"],
    "Kayseri": ["kayseriulasim.com"],
    "Adana": ["adana.bel.tr"],
    "Gaziantep": ["gaziulas.com.tr"],
    "Kocaeli": ["ulasimpark.com.tr"],
    "Samsun": ["samulas.com.tr"],
}


async def discover_transit_tariff_urls(
    city_name: str,
) -> list[str]:
    """İl için resmî toplu taşıma öğrenci bilet ve abonman sayfalarını keşfet."""
    known_domains = METRO_TRANSIT_DOMAINS.get(city_name, [])
    found: list[str] = []

    # 1. Bilinen domain araması
    for domain in known_domains:
        try:
            urls = await search_web_for_domain(
                domain,
                f"site:{domain} öğrenci bilet fiyatları aylık abonman ücret tarifesi",
                max_results=3,
            )
            found.extend(urls)
        except Exception as e:
            logger.debug("Ulaşım domain arama hatası (%s): %s", domain, e)

    # 2. Genel UKOME / Belediye araması
    if not found:
        query = f'"{city_name}" büyükşehir belediyesi UKOME öğrenci bilet tarifesi abonman'
        try:
            urls = await search_web_for_domain("bel.tr", query, max_results=3)
            found.extend(urls)
        except Exception as e:
            logger.debug("Belediye arama hatası (%s): %s", city_name, e)

    return found[:3]
