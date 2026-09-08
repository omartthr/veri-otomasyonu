"""Şehir & Yaşam Rehberi — Coğrafi Koordinat ve Mesafe Hesaplayıcı.

Enlem/Boylam koordinatlarını doğrular; Haversine formülüyle ilçe/merkez
mesafesini (km) ve tahmini ulaşım süresini (dakika) deterministik olarak hesaplar.
"""

from __future__ import annotations

import math
from typing import Optional

from src.city_livability_pipeline.extractors.base_livability_extractor import ExtractedLivabilityField
from src.city_livability_pipeline.validation.hard_quality_gates import HardQualityGates
from src.city_livability_pipeline.validation.range_validators import validate_coordinates


def calculate_haversine_distance_km(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """İki koordinat arasındaki kuş uçuşu mesafeyi (km) Haversine formülüyle hesapla."""
    R = 6371.0  # Dünya yarıçapı (km)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def estimate_transit_time_minutes(distance_km: float, is_urban: bool = True) -> int:
    """Mesafeye göre toplu taşıma / sürüş süresini (dakika) tahmin et.

    Şehir içi ortalama hız: 25 km/saat + 5 dk durak payı
    Şehirler arası / dışı hız: 50 km/saat
    """
    if distance_km <= 0:
        return 5
    speed_kmh = 25.0 if is_urban else 50.0
    transit_mins = (distance_km / speed_kmh) * 60.0
    buffer_mins = 5.0 if is_urban else 10.0
    return max(5, int(round(transit_mins + buffer_mins)))


class GeocodingExtractor:
    """Geocoding ve koordinat yöneticisi."""

    @classmethod
    def validate_and_extract_coords(
        cls,
        lat: Any,
        lon: Any,
        source_url: Optional[str] = None,
    ) -> tuple[Optional[float], Optional[float]]:
        """Koordinatları doğrula ve döndür."""
        valid_lat, valid_lon = validate_coordinates(lat, lon)
        return valid_lat, valid_lon
