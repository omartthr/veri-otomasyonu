"""Şehir & Yaşam Rehberi — Çıkarıcı Suite Testleri."""

import pytest
from src.city_livability_pipeline.extractors.price_and_tariff_extractor import PriceAndTariffExtractor
from src.city_livability_pipeline.extractors.rating_and_scale_extractor import RatingAndScaleExtractor
from src.city_livability_pipeline.extractors.boolean_flag_extractor import BooleanFlagExtractor
from src.city_livability_pipeline.extractors.campus_facilities_extractor import CampusFacilitiesExtractor
from src.city_livability_pipeline.extractors.geocoding_extractor import (
    calculate_haversine_distance_km,
    estimate_transit_time_minutes,
)


class TestPriceAndTariffExtractor:
    def test_extract_dining_meal_price(self):
        sample_html = "Üniversitemiz Sağlık Kültür ve Spor Daire Başkanlığı 2025-2026 dönemi öğrenci 1 öğün yemek ücreti 25,00 TL olarak belirlenmiştir."
        field = PriceAndTariffExtractor.extract_dining_meal_price(
            sample_html,
            source_url="https://sks.itu.edu.tr/yemek",
        )
        assert field.is_accepted
        assert field.value == 25.0
        assert "25,00 TL" in field.evidence

    def test_extract_student_transit_prices(self):
        sample_text = "UKOME kararıyla öğrenci tek biniş bilet ücreti 12,50 TL, öğrenci aylık abonman kart ücreti ise 282 TL olmuştur."
        ticket, sub = PriceAndTariffExtractor.extract_student_transit_prices(
            sample_text,
            source_url="https://iett.istanbul/tarife",
        )
        assert ticket.is_accepted
        assert ticket.value == 12.50
        assert sub.is_accepted
        assert sub.value == 282.0


class TestRatingAndScaleExtractor:
    def test_extract_numerical_scale(self):
        text = "Öğrencilerin şehir içi toplu taşıma kalitesi puanı: 4/5 olarak ölçülmüştür."
        field = RatingAndScaleExtractor.extract_scale_1_to_5(
            "Toplu Taşıma Kalitesi",
            text,
            source_url="https://anket.gov.tr/",
        )
        assert field.is_accepted
        assert field.value == 4

    def test_extract_qualitative_scale(self):
        text = "Kampüs çevresi akşam saatlerinde son derece güvenli ve aydınlıktır."
        field = RatingAndScaleExtractor.extract_scale_1_to_5(
            "Güvenlik",
            text,
            source_url="https://forum.edu.tr/",
        )
        assert field.is_accepted
        assert field.value == 4


class TestBooleanFlagExtractor:
    def test_extract_prep_school_mandatory(self):
        text = "Üniversitemize kayıt yaptıran tüm lisans öğrencileri için 1 yıl zorunlu İngilizce hazırlık sınıfı eğitimi verilmektedir."
        field = BooleanFlagExtractor.extract_prep_school_mandatory(
            text,
            source_url="https://ydyo.boun.edu.tr/",
        )
        assert field.is_accepted
        assert field.value == "Evet"

    def test_extract_library_24_7(self):
        text = "Merkez kütüphanemiz tüm öğrencilerimize 7/24 kesintisiz hizmet vermektedir."
        field = BooleanFlagExtractor.extract_library_24_7(
            text,
            source_url="https://kutuphane.metu.edu.tr/",
        )
        assert field.is_accepted
        assert field.value == "Evet"


class TestCampusFacilitiesExtractor:
    def test_extract_ring_shuttle(self):
        text = "Yerleşkelerimiz arasında her 15 dakikada bir ücretsiz ring seferleri düzenlenmektedir."
        var_mi, ucretli_mi = CampusFacilitiesExtractor.extract_ring_shuttle(
            text,
            source_url="https://ulasim.metu.edu.tr/",
        )
        assert var_mi.is_accepted
        assert var_mi.value == "Evet"
        assert ucretli_mi.is_accepted
        assert ucretli_mi.value == "Hayır"

    def test_extract_dorm_capacity(self):
        text = "Yerleşke içerisinde yer alan öğrenci yurtlarımızın toplam kapasitesi 4.500 yatak kapasitelidir."
        field = CampusFacilitiesExtractor.extract_dorm_capacity(
            text,
            source_url="https://yurt.boun.edu.tr/",
        )
        assert field.is_accepted
        assert field.value == 4500


class TestGeocodingCalculations:
    def test_haversine_ankara_istanbul(self):
        # Ankara: 39.9334, 32.8597 | İstanbul: 41.0082, 28.9784 (~350 km)
        dist = calculate_haversine_distance_km(39.9334, 32.8597, 41.0082, 28.9784)
        assert 340.0 <= dist <= 360.0

    def test_transit_time_estimation(self):
        # 10 km şehir içi mesafe -> ~29 dakika
        mins = estimate_transit_time_minutes(10.0, is_urban=True)
        assert 20 <= mins <= 35
