"""Şehir & Yaşam Rehberi — Formül Motoru Testleri.

calculators.py'deki tüm matematiksel formülleri test eder.
"""

import pytest
from src.city_livability_pipeline.calculators import (
    calculate_aylik_toplam_yurtta,
    calculate_aylik_toplam_ev_arkadasli,
    calculate_aylik_toplam_tek_yasam,
    calculate_yillik_9ay,
    calculate_usd_karsiligi,
    calculate_maliyet_endeksi,
    classify_maliyet_bandi,
    calculate_yasanabilirlik_skoru,
    calculate_ogrenci_nufus_orani,
    calculate_il_ortalamasina_gore_kira_farki,
    calculate_kampus_maliyet_farki,
    calculate_yurt_kazanma_orani,
    compute_sehir_derived_fields,
    KISISEL_GIDER_AYLIK,
)


class TestAylikToplamYurtta:
    def test_basic(self):
        result = calculate_aylik_toplam_yurtta(
            kyk_yurt_ucreti=1500,
            aylik_yeme_icme=5000,
            ogrenci_aylik_abonman=600,
        )
        expected = 1500 + 5000 + 600 + KISISEL_GIDER_AYLIK
        assert result == expected

    def test_none_yurt(self):
        assert calculate_aylik_toplam_yurtta(None, 5000, 600) is None

    def test_none_yemek(self):
        assert calculate_aylik_toplam_yurtta(1500, None, 600) is None

    def test_none_abonman(self):
        result = calculate_aylik_toplam_yurtta(1500, 5000, None)
        assert result == 1500 + 5000 + 0 + KISISEL_GIDER_AYLIK


class TestAylikToplamEvArkadasli:
    def test_basic(self):
        result = calculate_aylik_toplam_ev_arkadasli(
            oda_basi_kira=4000,
            fatura_ortalamasi_kis=1200,
            fatura_ortalamasi_yaz=600,
            aidat=500,
            internet=300,
            aylik_yeme_icme=5000,
            ogrenci_aylik_abonman=600,
        )
        fatura_ort = (1200 + 600) / 2
        paylasilan = (fatura_ort + 500 + 300) / 2
        expected = 4000 + paylasilan + 5000 + 600 + KISISEL_GIDER_AYLIK
        assert result == expected

    def test_none_kira(self):
        assert calculate_aylik_toplam_ev_arkadasli(
            None, 1200, 600, 500, 300, 5000, 600
        ) is None


class TestAylikToplamTekYasam:
    def test_basic(self):
        result = calculate_aylik_toplam_tek_yasam(
            ortalama_kira_1_1=8000,
            fatura_ortalamasi_kis=1200,
            fatura_ortalamasi_yaz=600,
            aidat=500,
            internet=300,
            aylik_yeme_icme=5000,
            ogrenci_aylik_abonman=600,
        )
        fatura_ort = (1200 + 600) / 2
        expected = 8000 + fatura_ort + 500 + 300 + 5000 + 600 + KISISEL_GIDER_AYLIK
        assert result == expected


class TestYillikProjeksiyonlar:
    def test_9ay(self):
        assert calculate_yillik_9ay(10000) == 90000

    def test_9ay_none(self):
        assert calculate_yillik_9ay(None) is None

    def test_usd(self):
        result = calculate_usd_karsiligi(38500, kur=38.5)
        assert result == 1000.0

    def test_usd_none(self):
        assert calculate_usd_karsiligi(None) is None

    def test_usd_zero_kur(self):
        assert calculate_usd_karsiligi(100, kur=0) is None


class TestMaliyetEndeksi:
    def test_orta(self):
        result = calculate_maliyet_endeksi(10000, 10000)
        assert result == 100.0

    def test_ucuz(self):
        result = calculate_maliyet_endeksi(8000, 10000)
        assert result == 80.0

    def test_pahali(self):
        result = calculate_maliyet_endeksi(14000, 10000)
        assert result == 140.0

    def test_none_input(self):
        assert calculate_maliyet_endeksi(None, 10000) is None

    def test_zero_medyan(self):
        assert calculate_maliyet_endeksi(10000, 0) is None


class TestMaliyetBandi:
    def test_cok_ucuz(self):
        assert classify_maliyet_bandi(60) == "Çok Ucuz"

    def test_ucuz(self):
        assert classify_maliyet_bandi(80) == "Ucuz"

    def test_orta(self):
        assert classify_maliyet_bandi(100) == "Orta"

    def test_pahali(self):
        assert classify_maliyet_bandi(120) == "Pahalı"

    def test_cok_pahali(self):
        assert classify_maliyet_bandi(150) == "Çok Pahalı"

    def test_none(self):
        assert classify_maliyet_bandi(None) is None


class TestYasanabilirlikSkoru:
    def test_basic(self):
        result = calculate_yasanabilirlik_skoru(
            maliyet_endeksi=100,
            sosyal_hayat=4,
            guvenlik=4,
            ulasim_kalitesi=4,
            is_piyasasi=4,
        )
        assert result is not None
        assert 0 <= result <= 100

    def test_ucuz_sehir_yuksek_skor(self):
        ucuz = calculate_yasanabilirlik_skoru(60, 4, 4, 4, 4)
        pahali = calculate_yasanabilirlik_skoru(140, 4, 4, 4, 4)
        assert ucuz > pahali

    def test_none_endeks(self):
        assert calculate_yasanabilirlik_skoru(None, 4, 4, 4, 4) is None


class TestYardimciFonksiyonlar:
    def test_ogrenci_nufus_orani(self):
        result = calculate_ogrenci_nufus_orani(50000, 1000000)
        assert result == 5.0

    def test_ogrenci_nufus_none(self):
        assert calculate_ogrenci_nufus_orani(None, 1000000) is None

    def test_kira_farki(self):
        result = calculate_il_ortalamasina_gore_kira_farki(6000, 5000)
        assert result == 20.0

    def test_kampus_maliyet_farki(self):
        result = calculate_kampus_maliyet_farki(12000, 10000)
        assert result == 20.0

    def test_yurt_kazanma_orani(self):
        result = calculate_yurt_kazanma_orani(5000, 20000)
        assert result == 25.0


class TestComputeSehirDerived:
    def test_with_full_data(self):
        row = {
            "Nüfus": 1000000,
            "Yükseköğretim Öğrenci Sayısı": 50000,
            "KYK Yurt Ücreti (TL/ay)": 1500,
            "Aylık Yeme-İçme Toplamı (TL/ay)": 5000,
            "Öğrenci Aylık Abonman (TL/ay)": 600,
            "Oda Başı Kira - Ev Arkadaşlı (TL/ay)": 4000,
            "Ortalama Kira 1+1 Merkez (TL/ay)": 8000,
            "Fatura Ortalaması Kış (TL/ay)": 1200,
            "Fatura Ortalaması Yaz (TL/ay)": 600,
            "Aidat (TL/ay)": 500,
            "İnternet (TL/ay)": 300,
            "Güvenlik Algısı (1-5)": 4,
            "Sosyal Hayat & Gece Hayatı (1-5)": 3,
            "Toplu Taşıma Kalitesi (1-5)": 4,
            "Staj & İş Piyasası (1-5)": 3,
        }

        updates = compute_sehir_derived_fields(row, tr_medyan_maliyet=12000)
        assert "Öğrenci/Nüfus Oranı (%)" in updates
        assert updates["Öğrenci/Nüfus Oranı (%)"] == 5.0
        assert "Aylık Toplam - Yurtta (TL/ay)" in updates
        assert "Aylık Toplam - Ev Arkadaşlı (TL/ay)" in updates
        assert "Yıllık (9 Ay) Toplam - Yurtta (TL)" in updates
        assert "Kur (USD/TRY)" in updates

    def test_with_none_data(self):
        row = {"Nüfus": None}
        updates = compute_sehir_derived_fields(row)
        # Should not crash, just return minimal updates
        assert "Kur (USD/TRY)" in updates
