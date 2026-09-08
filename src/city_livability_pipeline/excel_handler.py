"""Şehir & Yaşam Rehberi — Excel okuma/yazma motoru.

turkey_city_livability_review.xlsx dosyasını openpyxl ile okur/yazar.
Hücre stilleri, renkler ve formüller korunur.

Kurallar:
- Orijinal dosyaya dokunma, kopyala ve üzerinde çalış
- Stil kopyalama: _copy_row_style ile referans satırdan
- Atomik yazma: geçici dosyaya yaz, sonra taşı
- Boş hücre = None (asla N/A, null, — yazma)
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from copy import copy
from pathlib import Path
from typing import Any, Optional

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

logger = logging.getLogger(__name__)


# ─────────────────── Sütun Haritaları ───────────────────

# Her sayfa için Excel sütun başlığı → model alan adı eşleştirmesi
# AlanRehberi sayfasından alınmış resmi başlıklar kullanılır.

SEHIRLER_COLUMNS: dict[str, str] = {
    "Şehir ID": "sehir_id",
    "İl Adı": "il_adi",
    "Ülke": "ulke",
    "Bölge": "bolge",
    "Büyükşehir Mi": "buyuksehir_mi",
    "Nüfus": "nufus",
    "Yükseköğretim Öğrenci Sayısı": "yuksekogretim_ogrenci_sayisi",
    "Öğrenci/Nüfus Oranı (%)": "ogrenci_nufus_orani",
    "Üniversite Sayısı": "universite_sayisi",
    "Denize Kıyı Var Mı": "denize_kiyi_var_mi",
    "Rakım (m)": "rakim",
    "Ortalama Kira 1+1 Merkez (TL/ay)": "ortalama_kira_1_1_merkez",
    "Ortalama Kira 1+1 Merkez Dışı (TL/ay)": "ortalama_kira_1_1_merkez_disi",
    "Ortalama Kira 2+1 (TL/ay)": "ortalama_kira_2_1",
    "Ortalama Kira 3+1 (TL/ay)": "ortalama_kira_3_1",
    "Oda Başı Kira - Ev Arkadaşlı (TL/ay)": "oda_basi_kira_ev_arkadasli",
    "Depozito (Kira Katı)": "depozito_kira_kati",
    "Emlakçı Komisyonu (Kira Katı)": "emlakci_komisyonu_kira_kati",
    "Aidat (TL/ay)": "aidat",
    "Fatura Ortalaması Kış (TL/ay)": "fatura_ortalamasi_kis",
    "Fatura Ortalaması Yaz (TL/ay)": "fatura_ortalamasi_yaz",
    "İnternet (TL/ay)": "internet",
    "KYK Yurt Ücreti (TL/ay)": "kyk_yurt_ucreti",
    "KYK Yurt Kazanma Zorluğu (1-5)": "kyk_yurt_kazanma_zorlugu",
    "Özel Yurt Ücreti Min (TL/ay)": "ozel_yurt_ucreti_min",
    "Özel Yurt Ücreti Ortalama (TL/ay)": "ozel_yurt_ucreti_ortalama",
    "Apart/Stüdyo Ücreti (TL/ay)": "apart_studyo_ucreti",
    "Ev Bulma Zorluğu (1-5)": "ev_bulma_zorlugu",
    "Eylül Sezon Zammı Var Mı": "eylul_sezon_zammi_var_mi",
    "Üniversite Yemekhanesi Öğün (TL)": "universite_yemekhanesi_ogun",
    "Esnaf Lokantası Öğün (TL)": "esnaf_lokantasi_ogun",
    "Fast Food Menü (TL)": "fast_food_menu",
    "Çay (TL)": "cay",
    "Kahve (TL)": "kahve",
    "Market Aylık Sepet - Tek Kişi (TL/ay)": "market_aylik_sepet_tek_kisi",
    "Aylık Yeme-İçme Toplamı (TL/ay)": "aylik_yeme_icme_toplami",
    "Öğrenci Tek Bilet (TL)": "ogrenci_tek_bilet",
    "Öğrenci Aylık Abonman (TL/ay)": "ogrenci_aylik_abonman",
    "Toplu Taşıma Türleri": "toplu_tasima_turleri",
    "Toplu Taşıma Kalitesi (1-5)": "toplu_tasima_kalitesi",
    "En Yakın Havalimanı": "en_yakin_havalimani",
    "Havalimanı Mesafesi (km)": "havalimani_mesafesi",
    "YHT Bağlantısı Var Mı": "yht_baglantisi_var_mi",
    "İstanbul'a Otobüs Bileti (TL)": "istanbula_otobus_bileti",
    "Ankara'ya Otobüs Bileti (TL)": "ankaraya_otobus_bileti",
    "Aylık Toplam - Yurtta (TL/ay)": "aylik_toplam_yurtta",
    "Aylık Toplam - Ev Arkadaşlı (TL/ay)": "aylik_toplam_ev_arkadasli",
    "Aylık Toplam - Tek Yaşam (TL/ay)": "aylik_toplam_tek_yasam",
    "Yıllık (9 Ay) Toplam - Yurtta (TL)": "yillik_9ay_toplam_yurtta",
    "Yıllık (9 Ay) Toplam - Ev Arkadaşlı (TL)": "yillik_9ay_toplam_ev_arkadasli",
    "Yıllık (9 Ay) Toplam - Tek Yaşam (TL)": "yillik_9ay_toplam_tek_yasam",
    "Aylık Toplam - Ev Arkadaşlı (USD/ay)": "aylik_toplam_ev_arkadasli_usd",
    "Yıllık Toplam - Ev Arkadaşlı (USD)": "yillik_toplam_ev_arkadasli_usd",
    "Fiyat Referans Ayı": "fiyat_referans_ayi",
    "Kur (USD/TRY)": "kur_usd_try",
    "TR Ortalamasına Göre Maliyet Endeksi (TR=100)": "tr_ortalamasina_gore_maliyet_endeksi",
    "Maliyet Bandı": "maliyet_bandi",
    "Güvenlik Algısı (1-5)": "guvenlik_algisi",
    "Yaşam Tarzı Serbestliği (1-5)": "yasam_tarzi_serbestligi",
    "Sosyal Hayat & Gece Hayatı (1-5)": "sosyal_hayat_gece_hayati",
    "Kültür-Sanat Etkinliği (1-5)": "kultur_sanat_etkinligi",
    "Öğrenci Şehri Karakteri (1-5)": "ogrenci_sehri_karakteri",
    "Doğa & Açık Hava (1-5)": "doga_acik_hava",
    "İklim Tipi": "iklim_tipi",
    "Ortalama Kış Sıcaklığı (°C)": "ortalama_kis_sicakligi",
    "Ortalama Yaz Sıcaklığı (°C)": "ortalama_yaz_sicakligi",
    "Hava Kalitesi PM2.5 (ug/m3)": "hava_kalitesi_pm25",
    "Deprem Risk Bölgesi (1-5)": "deprem_risk_bolgesi",
    "Sağlık Erişimi (1-5)": "saglik_erisimi",
    "Şehir/Üniversite Hastanesi Var Mı": "sehir_universite_hastanesi_var_mi",
    "Part-time İş Bulma Kolaylığı (1-5)": "parttime_is_bulma_kolayligi",
    "Staj & İş Piyasası (1-5)": "staj_is_piyasasi",
    "Öğrenci Yaşanabilirlik Skoru (0-100)": "ogrenci_yasanabilirlik_skoru",
    "Şehir Özeti (metin)": "sehir_ozeti",
    "Kaynak Türü": "audit.kaynak_turu",
    "Veri Tarihi": "audit.veri_tarihi",
    "_source_urls": "audit.source_urls",
    "_source_notes": "audit.source_notes",
    "_confidence": "audit.confidence",
    "_needs_review": "audit.needs_review",
}

ILCELER_COLUMNS: dict[str, str] = {
    "İlçe ID": "ilce_id",
    "Şehir ID": "sehir_id",
    "İlçe Adı": "ilce_adi",
    "İlçe Tipi": "ilce_tipi",
    "Ortalama Kira 1+1 (TL/ay)": "ortalama_kira_1_1",
    "Oda Başı Kira (TL/ay)": "oda_basi_kira",
    "Öğrenci Yoğunluğu (1-5)": "ogrenci_yogunlugu",
    "Şehir Merkezine Süre (dk)": "sehir_merkezine_sure",
    "Güvenlik (1-5)": "guvenlik",
    "Yaşam Tarzı Serbestliği (1-5)": "yasam_tarzi_serbestligi",
    "Market/AVM Erişimi (1-5)": "market_avm_erisimi",
    "Öğrenci Mahallesi Mi": "ogrenci_mahallesi_mi",
    "İl Ortalamasına Göre Kira Farkı (%)": "il_ortalamasina_gore_kira_farki",
    "Kaynak Türü": "audit.kaynak_turu",
    "Veri Tarihi": "audit.veri_tarihi",
    "_source_urls": "audit.source_urls",
    "_source_notes": "audit.source_notes",
    "_confidence": "audit.confidence",
    "_needs_review": "audit.needs_review",
}

KAMPUSLER_COLUMNS: dict[str, str] = {
    "Kampüs ID": "kampus_id",
    "Üniversite ID": "universite_id",
    "Kampüs Adı": "kampus_adi",
    "Şehir ID": "sehir_id",
    "İlçe ID": "ilce_id",
    "Mahalle": "mahalle",
    "Enlem": "enlem",
    "Boylam": "boylam",
    "Kampüs Tipi": "kampus_tipi",
    "Şehir Merkezine Mesafe (km)": "sehir_merkezine_mesafe_km",
    "Şehir Merkezine Süre (dk)": "sehir_merkezine_sure_dk",
    "Kampüse Toplu Taşıma Var Mı": "kampuse_toplu_tasima_var_mi",
    "Hat Sayısı": "hat_sayisi",
    "Metro/Tramvay Durağı Var Mı": "metro_tramvay_duragi_var_mi",
    "Ring Servisi Var Mı": "ring_servisi_var_mi",
    "Ring Ücretli Mi": "ring_ucretli_mi",
    "Kampüse Aylık Ulaşım Maliyeti (TL/ay)": "kampuse_aylik_ulasim_maliyeti",
    "Kampüs Çevresi Karakteri": "kampus_cevresi_karakteri",
    "Yakında Kiralık Ev Var Mı": "yakinda_kiralik_ev_var_mi",
    "Kampüs Yakını Oda Başı Kira (TL/ay)": "kampus_yakini_oda_basi_kira",
    "Kampüs Yakını Öğün Fiyatı (TL)": "kampus_yakini_ogun_fiyati",
    "Kampüs Yakını Market Var Mı": "kampus_yakini_market_var_mi",
    "Kampüs Çevresi Sosyal Doku (1-5)": "kampus_cevresi_sosyal_doku",
    "Akşam Güvenlik (1-5)": "aksam_guvenlik",
    "Kampüs İçi Yurt Var Mı": "kampus_ici_yurt_var_mi",
    "Kampüs Yurt Kapasitesi": "kampus_yurt_kapasitesi",
    "Kampüs Yurt Ücreti (TL/ay)": "kampus_yurt_ucreti",
    "Yemekhane Öğün Ücreti (TL)": "yemekhane_ogun_ucreti",
    "Yemekhane Kalite (1-5)": "yemekhane_kalite",
    "Kampüs Alanı (m2)": "kampus_alani_m2",
    "Kütüphane 7/24 Mi": "kutuphane_7_24_mi",
    "Spor Tesisi": "spor_tesisi",
    "Sağlık Merkezi Var Mı": "saglik_merkezi_var_mi",
    "Kampüs İçi Kafe/Market Sayısı": "kampus_ici_kafe_market_sayisi",
    "Wi-Fi Kalitesi (1-5)": "wifi_kalitesi",
    "Bu Kampüsteki Fakülteler": "bu_kampusteki_fakulteler",
    "Kampüs Aylık Yaşam Maliyeti - Yurtta (TL/ay)": "kampus_aylik_yasam_maliyeti_yurtta",
    "Kampüs Aylık Yaşam Maliyeti - Ev Arkadaşlı (TL/ay)": "kampus_aylik_yasam_maliyeti_ev_arkadasli",
    "İl Ortalamasına Göre Maliyet Farkı (%)": "il_ortalamasina_gore_maliyet_farki",
    "Kampüs Öğrenci Uygunluk Skoru (0-100)": "kampus_ogrenci_uygunluk_skoru",
    "Kaynak Türü": "audit.kaynak_turu",
    "Veri Tarihi": "audit.veri_tarihi",
    "_source_urls": "audit.source_urls",
    "_source_notes": "audit.source_notes",
    "_confidence": "audit.confidence",
    "_needs_review": "audit.needs_review",
}

UNIVERSITELER_COLUMNS: dict[str, str] = {
    "Üniversite ID": "universite_id",
    "YÖK Kodu": "yok_kodu",
    "Üniversite Adı": "universite_adi",
    "Tür": "tur",
    "Kuruluş Yılı": "kurulus_yili",
    "Ana İl (Şehir ID)": "ana_il_sehir_id",
    "Ana İl Adı": "ana_il_adi",
    "Ana İlçe": "ana_ilce",
    "Kampüs Sayısı": "kampus_sayisi",
    "Web Sitesi": "web_sitesi",
    "Öğrenci Sayısı": "ogrenci_sayisi",
    "Uluslararası Öğrenci Oranı (%)": "uluslararasi_ogrenci_orani",
    "Yıllık Öğrenim Ücreti (TL)": "yillik_ogrenim_ucreti",
    "Ücret Yıl": "ucret_yil",
    "Burslu Kontenjan Oranı (%)": "burslu_kontenjan_orani",
    "%100 Burs Var Mı": "burs_100_var_mi",
    "%75 Burs Var Mı": "burs_75_var_mi",
    "%50 Burs Var Mı": "burs_50_var_mi",
    "%25 Burs Var Mı": "burs_25_var_mi",
    "Başarı Bursu (TL/ay)": "basari_bursu",
    "İhtiyaç Bursu Var Mı": "ihtiyac_bursu_var_mi",
    "Barınma Desteği Var Mı": "barinma_destegi_var_mi",
    "Toplam Yurt Kapasitesi": "toplam_yurt_kapasitesi",
    "Yurt Kazanma Oranı (%)": "yurt_kazanma_orani",
    "Yurt Ücret Aralığı (TL/ay)": "yurt_ucret_araligi",
    "Yemekhane Öğün Ücreti (TL)": "yemekhane_ogun_ucreti",
    "Öğrenciye Yemek Desteği Var Mı": "ogrenciye_yemek_destegi_var_mi",
    "Zorunlu İngilizce Hazırlık Mı": "zorunlu_ingilizce_hazirlik_mi",
    "Hazırlık Ücreti (TL)": "hazirlik_ucreti",
    "Kaynak Türü": "audit.kaynak_turu",
    "Veri Tarihi": "audit.veri_tarihi",
    "_source_urls": "audit.source_urls",
    "_source_notes": "audit.source_notes",
    "_confidence": "audit.confidence",
    "_needs_review": "audit.needs_review",
}

# Tüm sayfa haritalarını birleştir
SHEET_COLUMN_MAPS: dict[str, dict[str, str]] = {
    "Sehirler": SEHIRLER_COLUMNS,
    "Ilceler": ILCELER_COLUMNS,
    "Kampusler": KAMPUSLER_COLUMNS,
    "Universiteler": UNIVERSITELER_COLUMNS,
}

# Boş hücre sentinel değerleri
_EMPTY_SENTINEL = {None, "null", "none", "n/a", "na", "—", "-", ""}


# ─────────────────── Okuma ───────────────────

def _normalize_header(text: str) -> str:
    """Başlık metnini karşılaştırma için normalize et."""
    return str(text).strip()


def _detect_header_map(
    ws: Worksheet,
) -> tuple[dict[str, int], int]:
    """Sayfa başlıklarını tarayarak başlık → sütun numarası (1-tabanlı) haritası ve başlık satırı indeksini döndür.

    Returns:
        ({"Şehir ID": 1, "İl Adı": 2, ...}, header_row_index)
    """
    header_map: dict[str, int] = {}
    max_col = ws.max_column or 1
    
    # Başlıkların olduğu satırı bulmak için ilk 20 satıra bakıyoruz
    header_row = 1
    for row_idx in range(1, 21):
        cell_val = ws.cell(row=row_idx, column=1).value
        # 'ID' geçen bir kolon genelde ilk kolondur (Şehir ID, İlçe ID, Kampüs ID, Üniversite ID)
        if cell_val and "ID" in str(cell_val):
            header_row = row_idx
            break

    for col in range(1, max_col + 1):
        cell_val = ws.cell(row=header_row, column=col).value
        if cell_val is not None:
            header_map[_normalize_header(str(cell_val))] = col
    return header_map, header_row


def read_livability_sheet(
    file_path: Path | str,
    sheet_name: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Belirtilen sayfayı okuyarak satır listesi ve başlık haritası döndür.

    Args:
        file_path: .xlsx dosya yolu
        sheet_name: Okunacak sayfa adı

    Returns:
        (rows, header_map) çifti.
        rows: [{"Şehir ID": "01", "İl Adı": "Adana", ...}, ...]
        header_map: {"Şehir ID": 1, "İl Adı": 2, ...}

    Raises:
        FileNotFoundError: Dosya bulunamazsa
        ValueError: Sayfa bulunamazsa
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Excel dosyası bulunamadı: {file_path}")

    logger.info("Livability Excel okunuyor: %s [%s]", file_path.name, sheet_name)

    wb = load_workbook(file_path, data_only=True)

    if sheet_name not in wb.sheetnames:
        wb.close()
        raise ValueError(
            f"'{sheet_name}' sayfası bulunamadı. Mevcut: {wb.sheetnames}"
        )

    ws = wb[sheet_name]
    header_map, header_row = _detect_header_map(ws)

    if not header_map:
        wb.close()
        raise ValueError(f"'{sheet_name}' sayfasında başlık satırı bulunamadı.")

    # Ters harita: sütun numarası → başlık adı
    col_to_header = {v: k for k, v in header_map.items()}

    rows: list[dict[str, Any]] = []

    for row_idx in range(header_row + 1, (ws.max_row or header_row) + 1):
        row_data: dict[str, Any] = {"_row_number": row_idx}
        has_data = False

        for col_num, header_name in col_to_header.items():
            cell_val = ws.cell(row=row_idx, column=col_num).value
            row_data[header_name] = cell_val
            if cell_val is not None:
                has_data = True

        if has_data:
            rows.append(row_data)

    wb.close()
    logger.info(
        "%d satır okundu [%s]: %d sütun.",
        len(rows), sheet_name, len(header_map),
    )
    return rows, header_map


def read_all_sheets(
    file_path: Path | str,
) -> dict[str, tuple[list[dict[str, Any]], dict[str, int]]]:
    """Tüm veri sayfalarını oku.

    Returns:
        {"Sehirler": (rows, header_map), "Ilceler": ..., ...}
    """
    result = {}
    for sheet_name in SHEET_COLUMN_MAPS:
        try:
            result[sheet_name] = read_livability_sheet(file_path, sheet_name)
        except ValueError as e:
            logger.warning("Sayfa okunamadı: %s — %s", sheet_name, e)
    return result


# ─────────────────── Yazma ───────────────────

def _copy_cell_style(
    src_cell,
    tgt_cell,
) -> None:
    """Tek bir hücrenin stilini kopyala."""
    if src_cell.has_style:
        tgt_cell.font = copy(src_cell.font)
        tgt_cell.border = copy(src_cell.border)
        tgt_cell.fill = copy(src_cell.fill)
        tgt_cell.number_format = src_cell.number_format
        tgt_cell.protection = copy(src_cell.protection)
        tgt_cell.alignment = copy(src_cell.alignment)


def write_livability_sheet(
    input_path: Path | str,
    output_path: Path | str,
    sheet_name: str,
    updates: dict[int, dict[str, Any]],
) -> Path:
    """Belirtilen sayfaya güncellemeleri yaz.

    Stil ve formülleri koruyarak atomik yazma yapar.

    Args:
        input_path: Kaynak .xlsx dosya yolu
        output_path: Çıktı .xlsx dosya yolu
        sheet_name: Yazılacak sayfa adı
        updates: {satır_numarası: {"Sütun Başlığı": değer, ...}} formatında güncellemeler

    Returns:
        Yazılan dosyanın yolu

    Raises:
        FileNotFoundError: Kaynak dosya bulunamazsa
        ValueError: Sayfa bulunamazsa
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Kaynak dosya bulunamadı: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomik yazma: önce geçici dosyaya
    with tempfile.NamedTemporaryFile(
        suffix=".xlsx", delete=False, dir=output_path.parent
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Kaynak dosyayı kopyala
        shutil.copy2(input_path, tmp_path)

        # Formülleri koruyarak aç
        wb = load_workbook(tmp_path, data_only=False)

        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"'{sheet_name}' sayfası bulunamadı. Mevcut: {wb.sheetnames}"
            )

        ws = wb[sheet_name]
        header_map, header_row = _detect_header_map(ws)

        cells_written = 0
        cells_skipped = 0

        for row_num, row_updates in updates.items():
            for col_header, value in row_updates.items():
                col_num = header_map.get(col_header)
                if col_num is None:
                    logger.warning(
                        "Sütun bulunamadı: '%s' [%s satır %d]",
                        col_header, sheet_name, row_num,
                    )
                    cells_skipped += 1
                    continue

                cell = ws.cell(row=row_num, column=col_num)

                # Mevcut formüllere dokunma
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    logger.debug(
                        "Formül korundu: %s [%s:%d:%d]",
                        cell.value, sheet_name, row_num, col_num,
                    )
                    cells_skipped += 1
                    continue

                # Boş sentinel kontrolü
                comment_text = None
                if isinstance(value, tuple) and len(value) == 2:
                    value, comment_text = value

                if value is not None and str(value).strip().lower() in _EMPTY_SENTINEL:
                    value = None

                cell.value = value
                if value is not None:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                    if comment_text:
                        try:
                            cell.comment = Comment(str(comment_text)[:500], "Üniversite Veri Botu")
                        except Exception:
                            pass
                cells_written += 1

        wb.save(tmp_path)
        wb.close()

        # Atomik taşıma
        shutil.move(str(tmp_path), str(output_path))

        logger.info(
            "Excel yazıldı: %s [%s] — %d hücre güncellendi, %d atlandı.",
            output_path.name, sheet_name, cells_written, cells_skipped,
        )
        return output_path

    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def write_multiple_sheets(
    input_path: Path | str,
    output_path: Path | str,
    all_updates: dict[str, dict[int, dict[str, Any]]],
) -> Path:
    """Birden fazla sayfaya aynı anda güncelleme yaz.

    Args:
        input_path: Kaynak .xlsx dosya yolu
        output_path: Çıktı .xlsx dosya yolu
        all_updates: {"Sehirler": {2: {"Nüfus": 5000000, ...}, ...}, "Ilceler": ...}

    Returns:
        Yazılan dosyanın yolu
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Kaynak dosya bulunamadı: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        suffix=".xlsx", delete=False, dir=output_path.parent
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        shutil.copy2(input_path, tmp_path)
        wb = load_workbook(tmp_path, data_only=False)

        total_written = 0

        for sheet_name, updates in all_updates.items():
            if sheet_name not in wb.sheetnames:
                logger.warning("Sayfa bulunamadı, atlanıyor: %s", sheet_name)
                continue

            ws = wb[sheet_name]
            header_map = _detect_header_map(ws)

            for row_num, row_updates in updates.items():
                for col_header, value in row_updates.items():
                    col_num = header_map.get(col_header)
                    if col_num is None:
                        continue

                    cell = ws.cell(row=row_num, column=col_num)

                    # Formülleri koru
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        continue

                    comment_text = None
                    if isinstance(value, tuple) and len(value) == 2:
                        value, comment_text = value

                    if value is not None and str(value).strip().lower() in _EMPTY_SENTINEL:
                        value = None

                    cell.value = value
                    if value is not None:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
                        if comment_text:
                            try:
                                cell.comment = Comment(str(comment_text)[:500], "Üniversite Veri Botu")
                            except Exception:
                                pass
                    total_written += 1

        wb.save(tmp_path)
        wb.close()

        shutil.move(str(tmp_path), str(output_path))

        logger.info(
            "Çoklu sayfa yazıldı: %s — toplam %d hücre.",
            output_path.name, total_written,
        )
        return output_path

    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def get_output_filename(
    input_path: Path | str,
    output_dir: Path | str,
    suffix: str = "_livability_doldurulmus",
) -> Path:
    """Çıktı dosya adını oluştur (çakışma olmadan)."""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    base = output_dir / f"{stem}{suffix}.xlsx"

    if not base.exists():
        return base

    for i in range(2, 10_000):
        candidate = output_dir / f"{stem}{suffix}_{i}.xlsx"
        if not candidate.exists():
            return candidate

    raise FileExistsError("Çıktı dosyası oluşturulamadı.")
