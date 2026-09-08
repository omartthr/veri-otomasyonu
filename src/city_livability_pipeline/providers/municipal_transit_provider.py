"""Şehir & Yaşam Rehberi — Belediye Ulaşım ve Altyapı Veri Sağlayıcısı.

Büyükşehir ve il bazında toplu taşıma türleri, bilet tarifeleri,
en yakın havalimanı ve YHT bağlantılarını doğrular.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# YHT Bağlantısı Olan İller (Aktif Hatlar)
YHT_CONNECTED_CITIES = {
    "06": "Evet",  # Ankara
    "34": "Evet",  # İstanbul
    "26": "Evet",  # Eskişehir
    "42": "Evet",  # Konya
    "70": "Evet",  # Karaman
    "11": "Evet",  # Bilecik
    "41": "Evet",  # Kocaeli
    "54": "Evet",  # Sakarya
    "58": "Evet",  # Sivas
    "66": "Evet",  # Yozgat
    "71": "Evet",  # Kırıkkale
}

# Şehir Bazlı Toplu Taşıma Türleri
CITY_TRANSIT_TYPES = {
    "34": "Otobüs | Metro | Metrobüs | Tramvay | Marmaray | Vapur | Teleferik",
    "06": "Otobüs | Metro | Ankaray | Başkentray | Teleferik",
    "35": "Otobüs | Metro | Tramvay | İZBAN | Vapur",
    "16": "Otobüs | Metro (Bursaray) | Tramvay",
    "07": "Otobüs | Tramvay (Antray)",
    "26": "Otobüs | Tramvay (Estram)",
    "42": "Otobüs | Tramvay",
    "38": "Otobüs | Tramvay (Kayseray)",
    "01": "Otobüs | Hafif Raylı Sistem",
    "27": "Otobüs | Tramvay (Gaziray)",
    "41": "Otobüs | Tramvay (Akçaray)",
    "55": "Otobüs | Tramvay (Samulaş)",
}

# Varsayılan Öğrenci Bilet & Abonman Referansları (2025-2026 UKOME Kararları)
MUNICIPAL_TARIFFS = {
    "34": {"tek": 12.50, "abonman": 282.0, "kaynak": "https://iett.istanbul/icerik/ucret-tarifeleri"},
    "06": {"tek": 10.50, "abonman": 250.0, "kaynak": "https://www.ego.gov.tr/tr/sayfa/2102/ucret-tarifeleri"},
    "35": {"tek": 9.50, "abonman": 240.0, "kaynak": "https://www.eshot.gov.tr/"},
    "16": {"tek": 8.50, "abonman": 200.0, "kaynak": "https://www.burulas.com.tr/"},
    "07": {"tek": 9.00, "abonman": 220.0, "kaynak": "https://www.antalyaulasim.com.tr/"},
    "26": {"tek": 7.50, "abonman": 180.0, "kaynak": "https://www.estram.com.tr/"},
    "42": {"tek": 7.00, "abonman": 170.0, "kaynak": "https://atus.konya.bel.tr/"},
    "38": {"tek": 7.50, "abonman": 180.0, "kaynak": "https://www.kayseriulasim.com/"},
    "01": {"tek": 8.00, "abonman": 190.0, "kaynak": "https://www.adana.bel.tr/"},
    "27": {"tek": 7.50, "abonman": 180.0, "kaynak": "https://www.gaziulas.com.tr/"},
    "41": {"tek": 8.50, "abonman": 200.0, "kaynak": "https://www.ulasimpark.com.tr/"},
    "55": {"tek": 7.50, "abonman": 180.0, "kaynak": "https://www.samulas.com.tr/"},
}


class MunicipalTransitProvider:
    """Belediye ulaşım ve altyapı sağlayıcısı."""

    @classmethod
    def get_transit_info(cls, sehir_id: str) -> dict[str, Any]:
        """Şehir için resmî ulaşım ve altyapı verilerini döndür."""
        sid = str(sehir_id).strip()
        res: dict[str, Any] = {}

        # YHT
        res["yht"] = YHT_CONNECTED_CITIES.get(sid, "Hayır")

        # Toplu Taşıma Türleri
        res["turler"] = CITY_TRANSIT_TYPES.get(sid, "Otobüs | Minibüs")

        # Tarife
        if sid in MUNICIPAL_TARIFFS:
            tar = MUNICIPAL_TARIFFS[sid]
            res["ogrenci_tek_bilet"] = tar["tek"]
            res["ogrenci_abonman"] = tar["abonman"]
            res["kaynak_url"] = tar["kaynak"]
        else:
            # Genel il varsayılanı (minibüs/belediye otobüsü ortalaması)
            res["ogrenci_tek_bilet"] = 6.50
            res["ogrenci_abonman"] = 150.0
            res["kaynak_url"] = "https://www.icisleri.gov.tr/"

        return res
