"""Şehir & Yaşam Rehberi — OpenStreetMap Geocoding ve Mesafe Sağlayıcısı.

Üniversite kampüsleri ve ilçe merkezleri için koordinat çözümlemesi
ve merkez mesafesi (km/dk) hesaplaması yapar.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Optional

import httpx

from src.city_livability_pipeline.extractors.geocoding_extractor import (
    calculate_haversine_distance_km,
    estimate_transit_time_minutes,
)

logger = logging.getLogger(__name__)

# İl Merkez Koordinatları (Örnek Ana İller)
CITY_CENTER_COORDINATES: dict[str, tuple[float, float]] = {
    "01": (37.0000, 35.3213),  # Adana
    "06": (39.9334, 32.8597),  # Ankara
    "07": (36.8969, 30.7133),  # Antalya
    "16": (40.1885, 29.0610),  # Bursa
    "26": (39.7767, 30.5206),  # Eskişehir
    "34": (41.0082, 28.9784),  # İstanbul
    "35": (38.4237, 27.1428),  # İzmir
    "38": (38.7312, 35.4787),  # Kayseri
    "42": (37.8746, 32.4932),  # Konya
    "55": (41.2867, 36.3300),  # Samsun
}


class OpenStreetMapProvider:
    """Geocoding ve mesafe yöneticisi."""
    
    _geocode_cache: dict[str, dict] = {}
    
    @classmethod
    async def geocode_location(cls, query: str) -> dict:
        """Nominatim üzerinden lokasyon araması yapar.
        
        Returns:
            {"lat": float, "lon": float, "mahalle": str, "ilce": str} veya boş dict
        """
        query = query.strip().lower()
        if query in cls._geocode_cache:
            return cls._geocode_cache[query]
            
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "limit": 1
        }
        headers = {
            "User-Agent": "CityLivabilityBot/1.0 (test@example.com)"
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        res = data[0]
                        addr = res.get("address", {})
                        mahalle = addr.get("suburb") or addr.get("neighbourhood") or addr.get("village") or ""
                        ilce = addr.get("town") or addr.get("county") or addr.get("district") or ""
                        
                        result = {
                            "lat": float(res["lat"]),
                            "lon": float(res["lon"]),
                            "mahalle": mahalle,
                            "ilce": ilce,
                        }
                        cls._geocode_cache[query] = result
                        # Nominatim rate limit kuralı: saniyede max 1 istek.
                        await asyncio.sleep(1.1)
                        return result
        except Exception as e:
            logger.debug("Geocoding hatası (%s): %s", query, e)
            
        cls._geocode_cache[query] = {}
        await asyncio.sleep(1.1)
        return {}
        
    @classmethod
    def get_distance_to_city_center(
        cls,
        sehir_id: str,
        campus_lat: Optional[float],
        campus_lon: Optional[float],
    ) -> tuple[Optional[float], Optional[int]]:
        """Kampüs ile il merkezi arasındaki mesafe (km) ve tahmini süreyi (dk) döndür."""
        if campus_lat is None or campus_lon is None:
            return None, None

        center_coords = CITY_CENTER_COORDINATES.get(str(sehir_id).strip())
        if not center_coords:
            # Genel varsayılan merkez (39.0, 35.0)
            return None, None

        c_lat, c_lon = center_coords
        dist_km = calculate_haversine_distance_km(campus_lat, campus_lon, c_lat, c_lon)
        transit_dk = estimate_transit_time_minutes(dist_km, is_urban=dist_km < 30.0)

        return dist_km, transit_dk
