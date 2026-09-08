"""Şehir & Yaşam Rehberi — Pydantic veri modelleri.

Her Excel sayfasının satır yapısını temsil eden modeller,
kanıt/kaynak takibi ve denetim alanları.

Kural tabanlı, AI/LLM bağımlılığı yoktur.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ─────────────────── Ortak Denetim Alanları ───────────────────

class AuditFields(BaseModel):
    """Her satırda yer alan kaynak/denetim meta verileri."""

    kaynak_turu: Optional[str] = Field(
        None,
        description="Satırdaki verinin baskın kaynak türü (resmi / ilan / tahmin)",
    )
    veri_tarihi: Optional[str] = Field(
        None,
        description="Verinin toplandığı gün (YYYY-AA-GG)",
    )
    source_urls: Optional[str] = Field(
        None,
        description="Kullanılan tüm URL'ler, ' | ' ile ayrılır",
    )
    source_notes: Optional[str] = Field(
        None,
        description="Serbest not: varsayım, yöntem, tereddüt",
    )
    confidence: Optional[str] = Field(
        None,
        description="Resmi kaynak=Yüksek, ilan medyanı=Orta, tahmin=Düşük",
    )
    needs_review: Optional[str] = Field(
        None,
        description="Şüphe varsa Evet; ikinci göz bakacak",
    )


# ─────────────────── Şehirler Sayfası Modeli ───────────────────

class SehirRow(BaseModel):
    """Sehirler sayfasındaki tek bir il/şehir satırı (87 satır x 80 sütun)."""

    # Önceden dolu alanlar
    sehir_id: str = ""
    il_adi: str = ""
    ulke: str = "Türkiye"
    bolge: str = ""
    buyuksehir_mi: str = ""

    # Demografi
    nufus: Optional[int] = None
    yuksekogretim_ogrenci_sayisi: Optional[int] = None
    ogrenci_nufus_orani: Optional[float] = None
    universite_sayisi: Optional[int] = None

    # Coğrafya
    denize_kiyi_var_mi: Optional[str] = None
    rakim: Optional[int] = None

    # Kira & Barınma
    ortalama_kira_1_1_merkez: Optional[float] = None
    ortalama_kira_1_1_merkez_disi: Optional[float] = None
    ortalama_kira_2_1: Optional[float] = None
    ortalama_kira_3_1: Optional[float] = None
    oda_basi_kira_ev_arkadasli: Optional[float] = None
    depozito_kira_kati: Optional[float] = None
    emlakci_komisyonu_kira_kati: Optional[float] = None
    aidat: Optional[float] = None
    fatura_ortalamasi_kis: Optional[float] = None
    fatura_ortalamasi_yaz: Optional[float] = None
    internet: Optional[float] = None
    kyk_yurt_ucreti: Optional[float] = None
    kyk_yurt_kazanma_zorlugu: Optional[int] = None
    ozel_yurt_ucreti_min: Optional[float] = None
    ozel_yurt_ucreti_ortalama: Optional[float] = None
    apart_studyo_ucreti: Optional[float] = None
    ev_bulma_zorlugu: Optional[int] = None
    eylul_sezon_zammi_var_mi: Optional[str] = None

    # Yeme-İçme
    universite_yemekhanesi_ogun: Optional[float] = None
    esnaf_lokantasi_ogun: Optional[float] = None
    fast_food_menu: Optional[float] = None
    cay: Optional[float] = None
    kahve: Optional[float] = None
    market_aylik_sepet_tek_kisi: Optional[float] = None
    aylik_yeme_icme_toplami: Optional[float] = None

    # Ulaşım
    ogrenci_tek_bilet: Optional[float] = None
    ogrenci_aylik_abonman: Optional[float] = None
    toplu_tasima_turleri: Optional[str] = None
    toplu_tasima_kalitesi: Optional[int] = None
    en_yakin_havalimani: Optional[str] = None
    havalimani_mesafesi: Optional[float] = None
    yht_baglantisi_var_mi: Optional[str] = None
    istanbula_otobus_bileti: Optional[float] = None
    ankaraya_otobus_bileti: Optional[float] = None

    # Türetilmiş Maliyet Toplamları
    aylik_toplam_yurtta: Optional[float] = None
    aylik_toplam_ev_arkadasli: Optional[float] = None
    aylik_toplam_tek_yasam: Optional[float] = None
    yillik_9ay_toplam_yurtta: Optional[float] = None
    yillik_9ay_toplam_ev_arkadasli: Optional[float] = None
    yillik_9ay_toplam_tek_yasam: Optional[float] = None
    aylik_toplam_ev_arkadasli_usd: Optional[float] = None
    yillik_toplam_ev_arkadasli_usd: Optional[float] = None
    fiyat_referans_ayi: Optional[str] = None
    kur_usd_try: Optional[float] = None
    tr_ortalamasina_gore_maliyet_endeksi: Optional[float] = None
    maliyet_bandi: Optional[str] = None

    # Sosyal & Güvenlik
    guvenlik_algisi: Optional[int] = None
    yasam_tarzi_serbestligi: Optional[int] = None
    sosyal_hayat_gece_hayati: Optional[int] = None
    kultur_sanat_etkinligi: Optional[int] = None
    ogrenci_sehri_karakteri: Optional[int] = None
    doga_acik_hava: Optional[int] = None

    # İklim & Çevre
    iklim_tipi: Optional[str] = None
    ortalama_kis_sicakligi: Optional[float] = None
    ortalama_yaz_sicakligi: Optional[float] = None
    hava_kalitesi_pm25: Optional[float] = None
    deprem_risk_bolgesi: Optional[int] = None

    # Sağlık & İş
    saglik_erisimi: Optional[int] = None
    sehir_universite_hastanesi_var_mi: Optional[str] = None
    parttime_is_bulma_kolayligi: Optional[int] = None
    staj_is_piyasasi: Optional[int] = None

    # Türetilmiş Skorlar
    ogrenci_yasanabilirlik_skoru: Optional[float] = None
    sehir_ozeti: Optional[str] = None

    # Denetim
    audit: AuditFields = Field(default_factory=AuditFields)


# ─────────────────── İlçeler Sayfası Modeli ───────────────────

class IlceRow(BaseModel):
    """Ilceler sayfasındaki tek bir ilçe satırı (659 satır x 19 sütun)."""

    ilce_id: str = ""
    sehir_id: str = ""
    ilce_adi: str = ""

    ilce_tipi: Optional[str] = None
    ortalama_kira_1_1: Optional[float] = None
    oda_basi_kira: Optional[float] = None
    ogrenci_yogunlugu: Optional[int] = None
    sehir_merkezine_sure: Optional[int] = None
    guvenlik: Optional[int] = None
    yasam_tarzi_serbestligi: Optional[int] = None
    market_avm_erisimi: Optional[int] = None
    ogrenci_mahallesi_mi: Optional[str] = None
    il_ortalamasina_gore_kira_farki: Optional[float] = None

    audit: AuditFields = Field(default_factory=AuditFields)


# ─────────────────── Kampüsler Sayfası Modeli ───────────────────

class KampusRow(BaseModel):
    """Kampusler sayfasındaki tek bir kampüs satırı (846 satır x 46 sütun)."""

    kampus_id: str = ""
    universite_id: str = ""
    kampus_adi: Optional[str] = None
    sehir_id: Optional[str] = None
    ilce_id: Optional[str] = None
    mahalle: Optional[str] = None
    enlem: Optional[float] = None
    boylam: Optional[float] = None
    kampus_tipi: Optional[str] = None

    # Ulaşım
    sehir_merkezine_mesafe_km: Optional[float] = None
    sehir_merkezine_sure_dk: Optional[int] = None
    kampuse_toplu_tasima_var_mi: Optional[str] = None
    hat_sayisi: Optional[int] = None
    metro_tramvay_duragi_var_mi: Optional[str] = None
    ring_servisi_var_mi: Optional[str] = None
    ring_ucretli_mi: Optional[str] = None
    kampuse_aylik_ulasim_maliyeti: Optional[float] = None

    # Çevre
    kampus_cevresi_karakteri: Optional[str] = None
    yakinda_kiralik_ev_var_mi: Optional[str] = None
    kampus_yakini_oda_basi_kira: Optional[float] = None
    kampus_yakini_ogun_fiyati: Optional[float] = None
    kampus_yakini_market_var_mi: Optional[str] = None
    kampus_cevresi_sosyal_doku: Optional[int] = None
    aksam_guvenlik: Optional[int] = None

    # Kampüs İçi
    kampus_ici_yurt_var_mi: Optional[str] = None
    kampus_yurt_kapasitesi: Optional[int] = None
    kampus_yurt_ucreti: Optional[float] = None
    yemekhane_ogun_ucreti: Optional[float] = None
    yemekhane_kalite: Optional[int] = None
    kampus_alani_m2: Optional[float] = None
    kutuphane_7_24_mi: Optional[str] = None
    spor_tesisi: Optional[str] = None
    saglik_merkezi_var_mi: Optional[str] = None
    kampus_ici_kafe_market_sayisi: Optional[int] = None
    wifi_kalitesi: Optional[int] = None

    bu_kampusteki_fakulteler: Optional[str] = None

    # Türetilmiş
    kampus_aylik_yasam_maliyeti_yurtta: Optional[float] = None
    kampus_aylik_yasam_maliyeti_ev_arkadasli: Optional[float] = None
    il_ortalamasina_gore_maliyet_farki: Optional[float] = None
    kampus_ogrenci_uygunluk_skoru: Optional[float] = None

    audit: AuditFields = Field(default_factory=AuditFields)


# ─────────────────── Üniversiteler Sayfası Modeli ───────────────────

class UniversiteRow(BaseModel):
    """Universiteler sayfasındaki tek bir üniversite satırı (229 satır x 35 sütun)."""

    # Önceden dolu
    universite_id: str = ""
    yok_kodu: Optional[float] = None
    universite_adi: str = ""
    tur: str = ""
    kurulus_yili: Optional[int] = None
    ana_il_sehir_id: Optional[str] = None
    ana_il_adi: Optional[str] = None
    ana_ilce: Optional[str] = None
    kampus_sayisi: Optional[int] = None
    web_sitesi: Optional[str] = None

    # Doldurulacaklar
    ogrenci_sayisi: Optional[int] = None
    uluslararasi_ogrenci_orani: Optional[float] = None
    yillik_ogrenim_ucreti: Optional[float] = None
    ucret_yil: Optional[str] = None
    burslu_kontenjan_orani: Optional[float] = None
    burs_100_var_mi: Optional[str] = None
    burs_75_var_mi: Optional[str] = None
    burs_50_var_mi: Optional[str] = None
    burs_25_var_mi: Optional[str] = None
    basari_bursu: Optional[float] = None
    ihtiyac_bursu_var_mi: Optional[str] = None
    barinma_destegi_var_mi: Optional[str] = None
    toplam_yurt_kapasitesi: Optional[int] = None
    yurt_kazanma_orani: Optional[float] = None
    yurt_ucret_araligi: Optional[str] = None
    yemekhane_ogun_ucreti: Optional[float] = None
    ogrenciye_yemek_destegi_var_mi: Optional[str] = None
    zorunlu_ingilizce_hazirlik_mi: Optional[str] = None
    hazirlik_ucreti: Optional[float] = None

    audit: AuditFields = Field(default_factory=AuditFields)


# ─────────────────── Pipeline Sonuç Modeli ───────────────────

class SheetProcessorResult(BaseModel):
    """Tek bir sayfa işlemcisinin çalışma sonucu."""

    sheet_name: str
    total_rows: int = 0
    cells_filled: int = 0
    cells_empty: int = 0
    needs_review_count: int = 0
    errors: list[dict] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "error"] = "pending"


class LivabilityPipelineResult(BaseModel):
    """Tüm pipeline'ın toplam sonucu."""

    sheet_results: dict[str, SheetProcessorResult] = Field(default_factory=dict)
    output_path: Optional[str] = None
    total_cells_filled: int = 0
    total_errors: int = 0
