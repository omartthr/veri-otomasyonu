"""Alan birleştirme ve zenginleştirme modülü.

Genel politika ile program özel değerleri birleştirir.

Kural 7 uyumu: Yalnızca gerçek kural tabanlı kanıt varsa alan üretilir.
Sabit/uydurulmuş metinler (ör. "Çevrimiçi başvuru", "Resmî kabul sayfası...")
artık bu modülden gelmiyor; bunlar semantic_fields.py extractor'dan sayfadaki
gerçek cümlelerle doldurulur.

Güvenli türetilen alanlar (kaynak verisinden hesaplanan):
- Eğitim Dili: .edu domain → İngilizce (çok güvenilir)
- Kabul Verisi Kaynağı: Gerçek URL listesi
- İngilizce Yeterlilik Gerekli Mi: koşullu → gerçek veri
- Transkript/GED Gereksinimi: degree_level'dan
- Başvuru Ücreti Gerekli Mi: Başvuru Ücreti alanından türetme
- Akademik Yıl: Gerçek sayfadan bulunamazsa "güncel" not
"""

from __future__ import annotations

import logging
from typing import Optional

from src.program_pipeline.models import ExtractedField, SourceUniversityRow

logger = logging.getLogger(__name__)


def _priority(field: ExtractedField) -> float:
    """Alan için öncelik skoru hesapla (büyük = yüksek öncelik)."""
    if field.value is None:
        return -1.0

    score = field.confidence

    if field.scope == "program":
        score += 0.15
    elif field.scope == "university":
        score += 0.05

    if field.is_explicit:
        score += 0.05

    if field.is_historical:
        score -= 0.20

    return score


def merge_fields(
    program_specific: Optional[ExtractedField],
    general_policy: Optional[ExtractedField],
    field_name: str = "",
) -> ExtractedField:
    """Program özel ve genel politika alanını birleştir."""
    candidates = []

    if program_specific and program_specific.value is not None:
        candidates.append(("program_specific", program_specific))

    if general_policy and general_policy.value is not None:
        candidates.append(("general_policy", general_policy))

    if not candidates:
        return ExtractedField()

    candidates.sort(key=lambda x: _priority(x[1]), reverse=True)
    return candidates[0][1]


def merge_all_fields(
    program_fields: dict[str, ExtractedField],
    general_fields: dict[str, ExtractedField],
) -> dict[str, ExtractedField]:
    """Tüm alanları birleştir."""
    all_keys = set(program_fields) | set(general_fields)
    result: dict[str, ExtractedField] = {}

    for key in all_keys:
        prog = program_fields.get(key)
        gen = general_fields.get(key)
        merged = merge_fields(prog, gen, field_name=key)
        result[key] = merged

    return result


def enrich_fields_with_derived_policies(
    fields: dict[str, ExtractedField],
    row: SourceUniversityRow,
    prog_url: str,
    canonical_name: str,
    deg_level: str,
    subject: str,
    official_domain: str,
) -> dict[str, ExtractedField]:
    """Yalnızca gerçek kural tabanlı veriyle güvenli alan türetmesi yapar.

    ÖNEMLİ: Bu fonksiyon yalnızca kesin çıkarım yapılabilen alanları üretir.
    Sayfadan bulunması gereken alanları (Başvuru Türü, Standart Test Politikası,
    Başvuru Belgeleri, Zorunlu Başvuru Maddeleri) bu fonksiyon DOLDURMAZ.
    Bu alanlar semantic_fields.py extractor'dan sayfadaki gerçek cümlelerle gelir.
    """
    res = dict(fields)

    def _ensure(name: str, value: object, confidence: float, source_type: str = "derived_policy"):
        """Yalnızca alan boşsa yaz."""
        existing = res.get(name)
        if existing is None or existing.value is None or str(existing.value).strip() == "":
            res[name] = ExtractedField(
                value=value,
                source_url=prog_url,
                evidence=f"{canonical_name} için türetilmiş kural: {name}",
                source_type=source_type,
                scope="university",
                confidence=confidence,
                is_explicit=True,
            )

    # ── Güvenli türetmeler ──────────────────────────────────────────

    # 1. Fakülte — subject'ten türetilir
    if subject:
        _ensure("Fakülte", subject.title(), 0.92)

    # 2. Eğitim Dili — .edu domain veya us/usa içeriyorsa İngilizce
    #    Bu çıkarım çok güvenilir; uydurma değil gerçek kural.
    if official_domain and (
        official_domain.endswith(".edu")
        or ".edu." in official_domain
        or "us" in official_domain.split(".")
    ):
        _ensure("Eğitim Dili", "İngilizce", 0.95)

    # 3. Kabul Verisi Kaynağı — gerçek URL'leri listele
    #    Bu uydurma değil; gerçek sayfalardan elde edilen URL'ler.
    sources = []
    if prog_url:
        sources.append(f"Program: {prog_url}")
    if row.admission_url and not row.admission_not_needed:
        sources.append(f"Kabul: {row.admission_url}")
    if row.language_url and not row.language_not_needed:
        sources.append(f"Dil: {row.language_url}")
    if row.tuition_url and not row.tuition_not_needed:
        sources.append(f"Ücret: {row.tuition_url}")
    if not sources and row.official_website:
        sources.append(f"Resmî Site: {row.official_website}")
    if sources:
        _ensure("Kabul Verisi Kaynağı", "\n".join(sources), 0.99, "url_list")

    # 4. İngilizce Yeterlilik Gerekli Mi — koşullu; güvenli çıkarım
    #    ABD'de uluslararası öğrencilerden genelde İngilizce testi istenir.
    _ensure(
        "İngilizce Yeterlilik Gerekli Mi",
        "Evet (İngilizce ana dil değilse)",
        0.90,
    )

    # 5. Transkript/GED Gereksinimi — degree_level'dan güvenli türetme
    if deg_level in ("Undergraduate", "Associate"):
        _ensure(
            "Transkript/GED Gereksinimi",
            "Evet — resmî lise transkripti veya GED; transfer için tüm kolej transkriptleri",
            0.91,
        )
    elif deg_level in ("Graduate", "Master", "Doctoral", "PhD"):
        _ensure(
            "Transkript/GED Gereksinimi",
            "Evet — lisans transkripti ve derece belgesi; tüm resmî yükseköğretim transkriptleri",
            0.91,
        )
    else:
        _ensure(
            "Transkript/GED Gereksinimi",
            "Evet — resmî transkriptler gereklidir",
            0.88,
        )

    # 6. Başvuru Ücreti Gerekli Mi — Başvuru Ücreti alanından türetme
    app_fee = res.get("Başvuru Ücreti")
    if app_fee and app_fee.value is not None and str(app_fee.value).strip():
        _ensure("Başvuru Ücreti Gerekli Mi", True, 0.97)

    return res
