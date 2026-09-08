"""Şehir & Yaşam Rehberi — Formül & Türetilmiş Değer Motoru.

AlanRehberi ve Kapsam sayfalarında tanımlanan matematiksel kuralları
deterministik olarak hesaplar.

Tüm formüller saf Python, harici API gerektirmez.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────── Kişisel Gider Sabiti ───────────────────

# Kapsam sayfasından: "Kişisel harcama, telefon, giyim, sosyal vs."
# Sabit değer olarak varsayılan aylık kişisel gider (TL/ay)
KISISEL_GIDER_AYLIK = 2500.0

# Varsayılan USD/TRY kuru (güncellenebilir)
DEFAULT_USD_TRY = 38.5


# ─────────────────── Aylık Toplam Hesaplamaları ───────────────────

def calculate_aylik_toplam_yurtta(
    kyk_yurt_ucreti: Optional[float],
    aylik_yeme_icme: Optional[float],
    ogrenci_aylik_abonman: Optional[float],
    kisisel_gider: float = KISISEL_GIDER_AYLIK,
) -> Optional[float]:
    """Aylık Toplam - Yurtta (TL/ay).

    = Yurt Ücreti + Aylık Yeme-İçme + Ulaşım Abonmanı + Kişisel Gider
    """
    if kyk_yurt_ucreti is None or aylik_yeme_icme is None:
        return None

    abonman = ogrenci_aylik_abonman or 0.0
    return kyk_yurt_ucreti + aylik_yeme_icme + abonman + kisisel_gider


def calculate_aylik_toplam_ev_arkadasli(
    oda_basi_kira: Optional[float],
    fatura_ortalamasi_kis: Optional[float],
    fatura_ortalamasi_yaz: Optional[float],
    aidat: Optional[float],
    internet: Optional[float],
    aylik_yeme_icme: Optional[float],
    ogrenci_aylik_abonman: Optional[float],
    kisisel_gider: float = KISISEL_GIDER_AYLIK,
) -> Optional[float]:
    """Aylık Toplam - Ev Arkadaşlı (TL/ay).

    = Oda Başı Kira + (Faturalar + Aidat + İnternet) / 2 + Yeme-İçme + Abonman + Kişisel
    """
    if oda_basi_kira is None or aylik_yeme_icme is None:
        return None

    # Yıllık ortalama fatura
    fatura_kis = fatura_ortalamasi_kis or 0.0
    fatura_yaz = fatura_ortalamasi_yaz or 0.0
    fatura_ort = (fatura_kis + fatura_yaz) / 2.0

    aidat_val = aidat or 0.0
    internet_val = internet or 0.0
    abonman = ogrenci_aylik_abonman or 0.0

    # Ev arkadaşlı: fatura, aidat, internet 2'ye bölünür
    paylasilan = (fatura_ort + aidat_val + internet_val) / 2.0

    return oda_basi_kira + paylasilan + aylik_yeme_icme + abonman + kisisel_gider


def calculate_aylik_toplam_tek_yasam(
    ortalama_kira_1_1: Optional[float],
    fatura_ortalamasi_kis: Optional[float],
    fatura_ortalamasi_yaz: Optional[float],
    aidat: Optional[float],
    internet: Optional[float],
    aylik_yeme_icme: Optional[float],
    ogrenci_aylik_abonman: Optional[float],
    kisisel_gider: float = KISISEL_GIDER_AYLIK,
) -> Optional[float]:
    """Aylık Toplam - Tek Yaşam (TL/ay).

    = 1+1 Kira + Faturalar + Aidat + İnternet + Yeme-İçme + Abonman + Kişisel
    """
    if ortalama_kira_1_1 is None or aylik_yeme_icme is None:
        return None

    fatura_kis = fatura_ortalamasi_kis or 0.0
    fatura_yaz = fatura_ortalamasi_yaz or 0.0
    fatura_ort = (fatura_kis + fatura_yaz) / 2.0

    aidat_val = aidat or 0.0
    internet_val = internet or 0.0
    abonman = ogrenci_aylik_abonman or 0.0

    return (
        ortalama_kira_1_1
        + fatura_ort
        + aidat_val
        + internet_val
        + aylik_yeme_icme
        + abonman
        + kisisel_gider
    )


# ─────────────────── Yıllık Projeksiyonlar ───────────────────

def calculate_yillik_9ay(aylik_toplam: Optional[float]) -> Optional[float]:
    """Yıllık (9 Ay) Toplam (TL) = Aylık × 9."""
    if aylik_toplam is None:
        return None
    return aylik_toplam * 9.0


def calculate_usd_karsiligi(
    toplam_tl: Optional[float],
    kur: float = DEFAULT_USD_TRY,
) -> Optional[float]:
    """USD karşılığı = Toplam TL / USD-TRY Kuru."""
    if toplam_tl is None or kur <= 0:
        return None
    return round(toplam_tl / kur, 2)


# ─────────────────── Maliyet Endeksi ve Bant ───────────────────

def calculate_maliyet_endeksi(
    sehir_ev_arkadasli: Optional[float],
    tr_medyan: float,
) -> Optional[float]:
    """TR Ortalamasına Göre Maliyet Endeksi (TR=100).

    = (Şehir Ev Arkadaşlı Maliyeti / TR Medyan Maliyeti) × 100
    """
    if sehir_ev_arkadasli is None or tr_medyan <= 0:
        return None
    return round((sehir_ev_arkadasli / tr_medyan) * 100, 1)


def classify_maliyet_bandi(endeks: Optional[float]) -> Optional[str]:
    """Maliyet Bandı sınıflandırması.

    < 70: Çok Ucuz
    70 - 90: Ucuz
    90 - 110: Orta
    110 - 135: Pahalı
    > 135: Çok Pahalı
    """
    if endeks is None:
        return None

    if endeks < 70:
        return "Çok Ucuz"
    elif endeks < 90:
        return "Ucuz"
    elif endeks < 110:
        return "Orta"
    elif endeks < 135:
        return "Pahalı"
    else:
        return "Çok Pahalı"


# ─────────────────── Yaşanabilirlik Skoru ───────────────────

def calculate_yasanabilirlik_skoru(
    maliyet_endeksi: Optional[float],
    sosyal_hayat: Optional[int],
    guvenlik: Optional[int],
    ulasim_kalitesi: Optional[int],
    is_piyasasi: Optional[int],
) -> Optional[float]:
    """Öğrenci Yaşanabilirlik Skoru (0-100).

    Ağırlıklar:
        Maliyet Uygunluğu: %35
        Sosyal Hayat: %20
        Güvenlik: %15
        Ulaşım: %15
        İş/Staj: %15

    Formül:
        (100 - maliyet_endeks_puan) × 0.35
        + sosyal × 4 × 0.20
        + güvenlik × 20 × 0.15
        + ulaşım × 20 × 0.15
        + iş_piyasası × 20 × 0.15
    """
    if maliyet_endeksi is None:
        return None

    # Maliyet uygunluğu puanı: endeks düşükse puan yüksek
    # Endeks 100 = TR ortalaması, 50 = çok ucuz, 150 = çok pahalı
    # max(0, min(100, 100 - (endeks - 50)))
    maliyet_puan = max(0, min(100, 100 - (maliyet_endeksi - 50)))

    sosyal_puan = (sosyal_hayat or 3) * 20  # 1-5 → 20-100
    guvenlik_puan = (guvenlik or 3) * 20
    ulasim_puan = (ulasim_kalitesi or 3) * 20
    is_puan = (is_piyasasi or 3) * 20

    skor = (
        maliyet_puan * 0.35
        + sosyal_puan * 0.20
        + guvenlik_puan * 0.15
        + ulasim_puan * 0.15
        + is_puan * 0.15
    )

    return round(max(0, min(100, skor)), 1)


# ─────────────────── Yardımcı Türetme Fonksiyonları ───────────────────

def calculate_ogrenci_nufus_orani(
    ogrenci_sayisi: Optional[int],
    nufus: Optional[int],
) -> Optional[float]:
    """Öğrenci/Nüfus Oranı (%)."""
    if ogrenci_sayisi is None or nufus is None or nufus == 0:
        return None
    return round((ogrenci_sayisi / nufus) * 100, 2)


def calculate_il_ortalamasina_gore_kira_farki(
    ilce_kira: Optional[float],
    il_ortalama_kira: Optional[float],
) -> Optional[float]:
    """İl Ortalamasına Göre Kira Farkı (%).

    = ((İlçe Kira - İl Ortalama) / İl Ortalama) × 100
    """
    if ilce_kira is None or il_ortalama_kira is None or il_ortalama_kira == 0:
        return None
    return round(((ilce_kira - il_ortalama_kira) / il_ortalama_kira) * 100, 1)


def calculate_kampus_maliyet_farki(
    kampus_maliyeti: Optional[float],
    il_ortalama_maliyeti: Optional[float],
) -> Optional[float]:
    """İl Ortalamasına Göre Kampüs Maliyet Farkı (%).

    = ((Kampüs Maliyeti - İl Ortalama) / İl Ortalama) × 100
    """
    if kampus_maliyeti is None or il_ortalama_maliyeti is None or il_ortalama_maliyeti == 0:
        return None
    return round(((kampus_maliyeti - il_ortalama_maliyeti) / il_ortalama_maliyeti) * 100, 1)


def calculate_yurt_kazanma_orani(
    yurt_kapasitesi: Optional[int],
    ogrenci_sayisi: Optional[int],
) -> Optional[float]:
    """Yurt Kazanma Oranı (%) = Yurt Kapasitesi / Öğrenci Sayısı × 100."""
    if yurt_kapasitesi is None or ogrenci_sayisi is None or ogrenci_sayisi == 0:
        return None
    return round((yurt_kapasitesi / ogrenci_sayisi) * 100, 1)


# ─────────────────── Toplu Hesaplama (Şehir Satırı) ───────────────────

def compute_sehir_derived_fields(
    row: dict,
    tr_medyan_maliyet: Optional[float] = None,
    kur: float = DEFAULT_USD_TRY,
) -> dict:
    """Bir şehir satırının tüm türetilmiş alanlarını hesapla.

    Args:
        row: Excel satırından okunan ham sözlük
        tr_medyan_maliyet: TR ortalaması ev arkadaşlı maliyet (tüm satırlardan hesaplanır)
        kur: USD/TRY kuru

    Returns:
        Güncellenmesi gereken alanların sözlüğü
    """
    updates: dict[str, object] = {}

    # Öğrenci/Nüfus Oranı
    oran = calculate_ogrenci_nufus_orani(
        row.get("Yükseköğretim Öğrenci Sayısı"),
        row.get("Nüfus"),
    )
    if oran is not None:
        updates["Öğrenci/Nüfus Oranı (%)"] = oran

    # Aylık Toplam - Yurtta
    yurtta = calculate_aylik_toplam_yurtta(
        row.get("KYK Yurt Ücreti (TL/ay)"),
        row.get("Aylık Yeme-İçme Toplamı (TL/ay)"),
        row.get("Öğrenci Aylık Abonman (TL/ay)"),
    )
    if yurtta is not None:
        updates["Aylık Toplam - Yurtta (TL/ay)"] = round(yurtta)

    # Aylık Toplam - Ev Arkadaşlı
    # Kira: merkez dışı 1+1 veya genel 1+1 merkez kullanılır
    kira_merkez = row.get("Ortalama Kira 1+1 Merkez (TL/ay)")
    kira_merkez_disi = row.get("Ortalama Kira 1+1 Merkez Dışı (TL/ay)")

    ev_arkadasli = calculate_aylik_toplam_ev_arkadasli(
        row.get("Oda Başı Kira - Ev Arkadaşlı (TL/ay)"),
        row.get("Fatura Ortalaması Kış (TL/ay)"),
        row.get("Fatura Ortalaması Yaz (TL/ay)"),
        row.get("Aidat (TL/ay)"),
        row.get("İnternet (TL/ay)"),
        row.get("Aylık Yeme-İçme Toplamı (TL/ay)"),
        row.get("Öğrenci Aylık Abonman (TL/ay)"),
    )
    if ev_arkadasli is not None:
        updates["Aylık Toplam - Ev Arkadaşlı (TL/ay)"] = round(ev_arkadasli)

    # Aylık Toplam - Tek Yaşam
    tek_yasam = calculate_aylik_toplam_tek_yasam(
        kira_merkez or kira_merkez_disi,
        row.get("Fatura Ortalaması Kış (TL/ay)"),
        row.get("Fatura Ortalaması Yaz (TL/ay)"),
        row.get("Aidat (TL/ay)"),
        row.get("İnternet (TL/ay)"),
        row.get("Aylık Yeme-İçme Toplamı (TL/ay)"),
        row.get("Öğrenci Aylık Abonman (TL/ay)"),
    )
    if tek_yasam is not None:
        updates["Aylık Toplam - Tek Yaşam (TL/ay)"] = round(tek_yasam)

    # Yıllık (9 Ay) Toplamlar
    for aylik_key, yillik_key in [
        ("Aylık Toplam - Yurtta (TL/ay)", "Yıllık (9 Ay) Toplam - Yurtta (TL)"),
        ("Aylık Toplam - Ev Arkadaşlı (TL/ay)", "Yıllık (9 Ay) Toplam - Ev Arkadaşlı (TL)"),
        ("Aylık Toplam - Tek Yaşam (TL/ay)", "Yıllık (9 Ay) Toplam - Tek Yaşam (TL)"),
    ]:
        aylik_val = updates.get(aylik_key) or row.get(aylik_key)
        yillik = calculate_yillik_9ay(aylik_val)
        if yillik is not None:
            updates[yillik_key] = round(yillik)

    # USD dönüşüm
    ev_arkadasli_final = updates.get("Aylık Toplam - Ev Arkadaşlı (TL/ay)") or row.get("Aylık Toplam - Ev Arkadaşlı (TL/ay)")
    if ev_arkadasli_final is not None:
        updates["Aylık Toplam - Ev Arkadaşlı (USD/ay)"] = calculate_usd_karsiligi(ev_arkadasli_final, kur)
        updates["Yıllık Toplam - Ev Arkadaşlı (USD)"] = calculate_usd_karsiligi(
            calculate_yillik_9ay(ev_arkadasli_final), kur
        )

    updates["Kur (USD/TRY)"] = kur

    # Maliyet Endeksi
    if tr_medyan_maliyet is not None and ev_arkadasli_final is not None:
        endeks = calculate_maliyet_endeksi(ev_arkadasli_final, tr_medyan_maliyet)
        if endeks is not None:
            updates["TR Ortalamasına Göre Maliyet Endeksi (TR=100)"] = endeks
            updates["Maliyet Bandı"] = classify_maliyet_bandi(endeks)

    # Yaşanabilirlik Skoru
    endeks_val = updates.get("TR Ortalamasına Göre Maliyet Endeksi (TR=100)") or row.get("TR Ortalamasına Göre Maliyet Endeksi (TR=100)")
    skor = calculate_yasanabilirlik_skoru(
        endeks_val,
        row.get("Sosyal Hayat & Gece Hayatı (1-5)"),
        row.get("Güvenlik Algısı (1-5)"),
        row.get("Toplu Taşıma Kalitesi (1-5)"),
        row.get("Staj & İş Piyasası (1-5)"),
    )
    if skor is not None:
        updates["Öğrenci Yaşanabilirlik Skoru (0-100)"] = skor

    return updates
