"""Şehir & Yaşam Rehberi — Sütun Aralık ve Tip Doğrulayıcı Testleri."""

import pytest
from src.city_livability_pipeline.validation.range_validators import (
    validate_scale_1_to_5,
    validate_percentage,
    validate_coordinates,
    validate_price,
    validate_boolean_flag,
    validate_categorical,
    validate_positive_int,
    TR_LAT_MIN,
    TR_LAT_MAX,
    TR_LON_MIN,
    TR_LON_MAX,
)


class TestValidateScale1to5:
    def test_valid_integers(self):
        for i in range(1, 6):
            assert validate_scale_1_to_5(i) == i

    def test_valid_strings(self):
        assert validate_scale_1_to_5("4") == 4
        assert validate_scale_1_to_5("3 (Orta)") == 3
        assert validate_scale_1_to_5("5/5") == 5

    def test_invalid_integers(self):
        assert validate_scale_1_to_5(0) is None
        assert validate_scale_1_to_5(6) is None
        assert validate_scale_1_to_5(-1) is None

    def test_invalid_types(self):
        assert validate_scale_1_to_5(None) is None
        assert validate_scale_1_to_5("bilinmiyor") is None


class TestValidatePercentage:
    def test_valid_floats(self):
        assert validate_percentage(25.5) == 25.5
        assert validate_percentage(0.0) == 0.0
        assert validate_percentage(100.0) == 100.0

    def test_valid_strings(self):
        assert validate_percentage("%45,5") == 45.5
        assert validate_percentage("12.3%") == 12.3

    def test_invalid_ranges(self):
        assert validate_percentage(-5) is None
        assert validate_percentage(105) is None
        assert validate_percentage(None) is None


class TestValidateCoordinates:
    def test_valid_turkey_coordinates(self):
        # İstanbul (41.0082, 28.9784)
        lat, lon = validate_coordinates(41.0082, 28.9784)
        assert lat == 41.0082
        assert lon == 28.9784

    def test_out_of_turkey_coordinates(self):
        # Londra (51.5074, -0.1278) -> Türkiye dışı
        lat, lon = validate_coordinates(51.5074, -0.1278)
        assert lat is None
        assert lon is None


class TestValidatePrice:
    def test_valid_dining_price(self):
        assert validate_price("25 TL", "yemekhane_ogun_ucreti") == 25.0
        assert validate_price(30, "yemekhane_ogun_ucreti") == 30.0

    def test_unrealistic_dining_price(self):
        # 1 TL yemek veya 1000 TL devlet yemekhanesi elenmeli
        assert validate_price(1.0, "yemekhane_ogun_ucreti") is None
        assert validate_price(1000.0, "yemekhane_ogun_ucreti") is None

    def test_valid_rent_price(self):
        assert validate_price("15.000 TL", "kira_1_1") == 15000.0
        assert validate_price(25000, "kira_2_1") == 25000.0


class TestValidateBooleanFlag:
    def test_positive(self):
        assert validate_boolean_flag("Evet") == "Evet"
        assert validate_boolean_flag("var") == "Evet"
        assert validate_boolean_flag(True) == "Evet"

    def test_negative(self):
        assert validate_boolean_flag("Hayır") == "Hayır"
        assert validate_boolean_flag("yok") == "Hayır"
        assert validate_boolean_flag(False) == "Hayır"

    def test_conditional(self):
        assert validate_boolean_flag("Koşullu") == "Koşullu"
        assert validate_boolean_flag("kısmen") == "Koşullu"


class TestValidatePositiveInt:
    def test_valid(self):
        assert validate_positive_int(15000) == 15000
        assert validate_positive_int("2.274.106") == 2274106

    def test_invalid(self):
        assert validate_positive_int(-10) is None
        assert validate_positive_int(None) is None
