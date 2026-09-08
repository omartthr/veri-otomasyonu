"""Şehir & Yaşam Rehberi — Canlı Web Tarama ve Araştırma Motoru.

İl, ilçe, kampüs ve üniversite sayfalarında asenkron canlı tarama yaparak
gerçek fiyat, yemekhane, ulaşım ve yurt verilerini kanıt alıntılarıyla ayıklar.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

import httpx
from bs4 import BeautifulSoup

from src.city_livability_pipeline.extractors.boolean_flag_extractor import BooleanFlagExtractor
from src.city_livability_pipeline.extractors.price_and_tariff_extractor import PriceAndTariffExtractor
from src.city_livability_pipeline.extractors.rating_and_scale_extractor import RatingAndScaleExtractor
from src.city_livability_pipeline.search.targeted_city_search import search_city_aspect

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def fetch_page_text(url: str, timeout: float = 8.0) -> tuple[str, str]:
    """Bir URL'yi asenkron indir ve görünür metni ayıkla (Proxy/Bot koruması aşarak)."""
    try:
        from curl_cffi import requests as curl_requests
        async with curl_requests.AsyncSession(impersonate="chrome110", timeout=timeout, verify=False) as client:
            resp = await client.get(url, allow_redirects=True, headers=HEADERS)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                for s in soup(["script", "style", "nav", "footer"]):
                    s.extract()
                text = " ".join(soup.get_text(separator=" ").split())
                return url, text[:15000]
    except ImportError:
        logger.error("curl_cffi yüklü değil! 'pip install curl-cffi' çalıştırın.")
    except Exception as e:
        logger.debug("Canlı sayfa çekme hatası (%s): %s", url, e)
    return url, ""


class LiveCityCrawler:
    """Canlı web tarama ve bilgi çıkarma motoru."""

    def __init__(self, event_callback: Optional[Callable[[str], None]] = None):
        self.event_callback = event_callback

    def _emit(self, msg: str):
        if self.event_callback:
            self.event_callback(msg)

    async def crawl_city_live_data(self, il_adi: str) -> dict[str, Any]:
        """Bir şehir için canlı web araştırması yap ve bulunan alanları döndür."""
        results: dict[str, Any] = {}
        self._emit(f"🔍 [{il_adi}] Canlı belediye UKOME ve üniversite SKS portalları taranıyor...")

        # 1. Ulaşım ve bilet araması
        ulasim_urls = await search_city_aspect(il_adi, "ulasim", max_results=2)
        for u in ulasim_urls:
            url, text = await fetch_page_text(u)
            if text:
                ticket, sub = PriceAndTariffExtractor.extract_student_transit_prices(text, source_url=url)
                if ticket.is_accepted and "ogrenci_tek_bilet" not in results:
                    results["ogrenci_tek_bilet"] = (ticket.value, ticket.evidence, url)
                    self._emit(f"🎫 [{il_adi}] Öğrenci bilet tarifesi bulundu: {ticket.value} TL ({url})")
                if sub.is_accepted and "ogrenci_aylik_abonman" not in results:
                    results["ogrenci_aylik_abonman"] = (sub.value, sub.evidence, url)
                    self._emit(f"💳 [{il_adi}] Öğrenci aylık abonman bulundu: {sub.value} TL ({url})")

        # 2. Yemekhane ve gıda araması
        yemek_urls = await search_city_aspect(il_adi, "yemek_market", max_results=2)
        for u in yemek_urls:
            url, text = await fetch_page_text(u)
            if text:
                meal = PriceAndTariffExtractor.extract_dining_meal_price(text, source_url=url)
                if meal.is_accepted and "universite_yemekhanesi_ogun" not in results:
                    results["universite_yemekhanesi_ogun"] = (meal.value, meal.evidence, url)
                    self._emit(f"🍲 [{il_adi}] Üniversite yemekhane öğün ücreti bulundu: {meal.value} TL ({url})")

        # 3. Yurt araması
        yurt_urls = await search_city_aspect(il_adi, "yurt", max_results=2)
        for u in yurt_urls:
            url, text = await fetch_page_text(u)
            if text:
                dorm = PriceAndTariffExtractor.extract_kyk_dorm_fee(text, source_url=url)
                if dorm.is_accepted and "kyk_yurt_ucreti" not in results:
                    results["kyk_yurt_ucreti"] = (dorm.value, dorm.evidence, url)
                    self._emit(f"🏢 [{il_adi}] KYK yurt ücreti bulundu: {dorm.value} TL ({url})")

        return results
