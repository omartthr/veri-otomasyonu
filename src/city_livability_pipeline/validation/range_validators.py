"""Şehir & Yaşam Rehberi — Sütun Bazlı Aralık ve Tip Doğrulayıcıları.

Her sütun için matematiksel, coğrafi ve kategorik sınırları denetler.
Kural dışı veya mantıksız değerlerin Excel'e girmesini engeller.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Union

# ─────────────────── Coğrafi Sınırlar (Türkiye & KKTC) ───────────────────
TR_LAT_MIN = 35.0
TR_LAT_MAX = 42.5
TR_LON_MIN = 25.5
TR_LON_MAX = 45.0

# ─────────────────── Fiyat Mantık Aralıkları (TL) ───────────────────
PRICE_RANGES: dict[str, tuple[float, float]] = {
    "yemekhane_ogun_ucreti": (5.0, 300.0),
    "esnaf_lokantasi_ogun": (30.0, 600.0),
    "fast_food_menu": (50.0, 600.0),
    "cay": (3.0, 100.0),
    "kahve": (10.0, 300.0),
    "ogrenci_tek_bilet": (2.0, 80.0),
    "ogrenci_aylik_abonman": (50.0, 1500.0),
    "kyk_yurt_ucreti": (345.0, 2500.0),
    "ozel_yurt_ucreti": (2000.0, 50000.0),
    "apart_studyo_ucreti": (2000.0, 40000.0),
    "kira_1_1": (1500.0, 120000.0),
    "kira_2_1": (2000.0, 150000.0),
    "kira_3_1": (3000.0, 200000.0),
    "oda_basi_kira": (1000.0, 60000.0),
    "aidat": (50.0, 15000.0),
    "fatura": (100.0, 15000.0),
    "internet": (100.0, 2000.0),
    "market_sepet": (1000.0, 25000.0),
    "yeme_icme_toplam": (2000.0, 40000.0),
    "otobus_bileti": (50.0, 3000.0),
    "ogrenim_ucreti_yillik": (10000.0, 2500000.0),
    "hazirlik_ucreti": (10000.0, 2000000.0),
    "basari_bursu_aylik": (500.0, 50000.0),
}

# ─────────────────── Kategorik Geçerli Değer Kümeleri ───────────────────
VALID_BOOLEAN_FLAGS = {"Evet", "Hayır", "Koşullu"}
VALID_IKLIM_TIPLERI = {"Akdeniz", "Karadeniz", "Karasal", "Geçiş", "Yarıkurak"}
VALID_ILCE_TIPLERI = {"Merkez", "Üniversite İlçesi", "Çevre", "Kırsal"}
VALID_KAMPUS_TIPLERI = {"Ana Yerleşke", "Şehir İçi", "Şehir Dışı", "MYO Yerleşkesi"}
VALID_MALIYET_BANDI = {"Çok Ucuz", "Ucuz", "Orta", "Pahalı", "Çok Pahalı"}
VALID_KAYNAK_TURLERI = {"resmi", "ilan", "tahmin", "türev"}
VALID_CONFIDENCE = {"Yüksek", "Orta", "Düşük"}


# ─────────────────── Doğrulama Fonksiyonları ───────────────────

def validate_scale_1_to_5(value: Any) -> Optional[int]:
    """1-5 arası tam sayı puanını doğrula.

    Geçerli: 1, 2, 3, 4, 5 (veya "1", "2" vb.)
    Geçersiz ise None döner.
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            # "4 (İyi)" veya "3/5" gibi metinlerden sayı ayıkla
            match = re.search(r"\b([1-5])\b", value.strip())
            if match:
                return int(match.group(1))
            return None
        val_int = int(round(float(value)))
        if 1 <= val_int <= 5:
            return val_int
        return None
    except (ValueError, TypeError):
        return None


def validate_percentage(value: Any) -> Optional[float]:
    """Yüzdelik değeri (0.0 - 100.0) doğrula."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace("%", "").replace(",", ".").strip()
            val_float = float(cleaned)
        else:
            val_float = float(value)
        if 0.0 <= val_float <= 100.0:
            return round(val_float, 2)
        return None
    except (ValueError, TypeError):
        return None


def validate_coordinates(lat: Any, lon: Any) -> tuple[Optional[float], Optional[float]]:
    """Enlem ve Boylam koordinatlarını Türkiye + KKTC kutusu içinde doğrula."""
    valid_lat: Optional[float] = None
    valid_lon: Optional[float] = None

    if lat is not None:
        try:
            val = float(str(lat).replace(",", ".").strip())
            if TR_LAT_MIN <= val <= TR_LAT_MAX:
                valid_lat = round(val, 6)
        except (ValueError, TypeError):
            pass

    if lon is not None:
        try:
            val = float(str(lon).replace(",", ".").strip())
            if TR_LON_MIN <= val <= TR_LON_MAX:
                valid_lon = round(val, 6)
        except (ValueError, TypeError):
            pass

    return valid_lat, valid_lon


def validate_price(value: Any, price_category: str) -> Optional[float]:
    """Fiyat değerini belirtilen kategorinin mantık sınırları içinde doğrula."""
    if value is None:
        return None
    bounds = PRICE_RANGES.get(price_category)
    if not bounds:
        bounds = (0.0, 10_000_000.0)

    min_p, max_p = bounds
    try:
        if isinstance(value, str):
            # "15.000 TL", "250,50 TL" gibi metinleri sayıya dönüştür
            cleaned = re.sub(r"[^\d,\.]", "", value.strip())
            # Türkiye formatı: 15.000,00 veya 15000.00 veya 15.000
            if "," in cleaned and "." in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "." in cleaned and "," not in cleaned:
                parts = cleaned.split(".")
                if all(len(p) == 3 for p in parts[1:]):
                    cleaned = "".join(parts)
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            val_float = float(cleaned)
        else:
            val_float = float(value)

        if min_p <= val_float <= max_p:
            return round(val_float, 2)
        return None
    except (ValueError, TypeError):
        return None


def validate_boolean_flag(value: Any) -> Optional[str]:
    """Evet / Hayır / Koşullu bayrağını standartlaştır."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "Evet" if value else "Hayır"

    v = str(value).strip().lower()
    if v in {"evet", "var", "true", "1", "yes", "mevcut"}:
        return "Evet"
    elif v in {"hayır", "hayir", "yok", "false", "0", "no", "mevcut değil"}:
        return "Hayır"
    elif v in {"koşullu", "kosullu", "kısmen", "conditional", "bölüme göre"}:
        return "Koşullu"
    return None


def validate_categorical(value: Any, valid_set: set[str]) -> Optional[str]:
    """Kategorik metin alanını geçerli küme içinde doğrula (büyük/küçük harf duyarsız)."""
    if value is None:
        return None
    v_norm = str(value).strip().lower()
    for valid_item in valid_set:
        if v_norm == valid_item.lower():
            return valid_item
    return None


def validate_positive_int(value: Any, max_val: int = 100_000_000) -> Optional[int]:
    """Pozitif tam sayı doğrulaması (Nüfus, Öğrenci Sayısı, Rakım vb.)."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            cleaned = re.sub(r"[^\d]", "", value.strip())
            val_int = int(cleaned)
        else:
            val_int = int(round(float(value)))
        if 0 <= val_int <= max_val:
            return val_int
        return None
    except (ValueError, TypeError):
        return None
