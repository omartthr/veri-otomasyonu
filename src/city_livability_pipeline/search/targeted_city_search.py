"""Şehir & Yaşam Rehberi — Hedefli Arama Sorgu Üretici ve Arayıcı.

Şehir, ilçe, kampüs ve üniversite sütunlarına özel arama motoru sorguları üretir
ve ilgili resmî/güvenilir sayfa URL'lerini keşfeder.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.search.web_searcher import search_web_for_domain

logger = logging.getLogger(__name__)


class TargetedCitySearch:
    """Şehir ve yaşam metrikleri için hedefli arama yöneticisi."""

    @staticmethod
    def build_city_queries(city_name: str, topic: str) -> list[str]:
        """İl bazında hedeflenmiş arama sorguları üret."""
        c = city_name.strip()
        queries = {
            "kira": [
                f'"{c}" kiralık daire ortalama kira endeksa 2026',
                f'"{c}" 1+1 kiralık ev fiyatları sahibinden 2026',
                f'"{c}" öğrenci evi oda kirası 2026',
            ],
            "ulasim": [
                f'"{c}" büyükşehir belediyesi öğrenci bilet tarifesi abonman 2026',
                f'"{c}" UKOME toplu taşıma öğrenci ücret tarifesi',
                f'"{c}" otobüs tramvay öğrenci kartı aylık abonman',
            ],
            "yemek_market": [
                f'"{c}" üniversitesi yemekhane öğün ücreti 2026',
                f'"{c}" esnaf lokantası öğün fiyatı ortalama',
                f'"{c}" öğrenci aylık yeme içme gideri maliyeti',
            ],
            "yurt": [
                f'"{c}" KYK yurtları kapasite ücreti 2026',
                f'"{c}" özel öğrenci yurtları fiyatları 2026',
            ],
            "fatura": [
                f'"{c}" ortalama ev faturaları doğalgaz elektrik su kış',
            ],
        }
        return queries.get(topic, [f'"{c}" {topic} 2026'])

    @staticmethod
    def build_district_queries(city_name: str, district_name: str, topic: str) -> list[str]:
        """İlçe bazında hedeflenmiş arama sorguları üret."""
        c = city_name.strip()
        d = district_name.strip()
        queries = {
            "kira": [
                f'"{c}" "{d}" kiralık daire ortalama kira endeksa',
                f'"{c}" "{d}" 1+1 kiralık ev fiyatları',
            ],
            "ogrenci_yasam": [
                f'"{c}" "{d}" öğrenci mahallesi yurtlar kafeler',
                f'"{c}" "{d}" merkeze ulaşım süresi dakika',
            ],
        }
        return queries.get(topic, [f'"{c}" "{d}" {topic}'])

    @staticmethod
    def build_campus_queries(uni_name: str, campus_name: str, topic: str) -> list[str]:
        """Kampüs bazında hedeflenmiş arama sorguları üret."""
        u = uni_name.strip()
        k = campus_name.strip()
        queries = {
            "ulasim_ring": [
                f'"{u}" "{k}" kampüs ring saatleri servis ulaşım',
                f'"{u}" "{k}" yerleşkesi otobüs hatları',
            ],
            "yemek_yurt": [
                f'"{u}" "{k}" yemekhane öğün ücreti',
                f'"{u}" "{k}" yerleşkesi öğrenci yurdu kapasite',
            ],
            "tesisler": [
                f'"{u}" "{k}" kütüphane çalışma saatleri 7/24',
                f'"{u}" "{k}" spor salonu mediko sağlık merkezi',
            ],
            "koordinat": [
                f'"{u}" "{k}" yerleşkesi adres mahalle iletişim',
            ],
        }
        return queries.get(topic, [f'"{u}" "{k}" {topic}'])

    @staticmethod
    def build_university_queries(uni_name: str, domain: Optional[str], topic: str) -> list[str]:
        """Üniversite resmî sayfaları için arama sorguları üret."""
        u = uni_name.strip()
        d_site = f"site:{domain} " if domain else ""
        queries = {
            "ucret_burs": [
                f'{d_site}"{u}" 2025 2026 öğrenim ücretleri harç',
                f'{d_site}"{u}" burs yönergesi başarı bursu barınma desteği',
            ],
            "yurt_yemek": [
                f'{d_site}"{u}" Sağlık Kültür ve Spor Daire Başkanlığı yemek ücreti',
                f'{d_site}"{u}" yurtlar müdürlüğü kapasite ücretleri',
            ],
            "hazirlik": [
                f'{d_site}"{u}" Yabancı Diller Yüksekokulu zorunlu hazırlık',
                f'{d_site}"{u}" İngilizce hazırlık programı muafiyet ücreti',
            ],
        }
        return queries.get(topic, [f'{d_site}"{u}" {topic}'])


async def search_city_aspect(
    city_name: str,
    topic: str,
    max_results: int = 4,
) -> list[str]:
    """Şehir konusu için arama motoru araması yap."""
    queries = TargetedCitySearch.build_city_queries(city_name, topic)
    found: set[str] = set()
    for q in queries[:2]:
        try:
            urls = await search_web_for_domain("gov.tr", q, max_results=max_results)
            for u in urls:
                found.add(u)
        except Exception as e:
            logger.debug("Şehir arama hatası (%s - %s): %s", city_name, topic, e)
    return list(found)[:max_results]
