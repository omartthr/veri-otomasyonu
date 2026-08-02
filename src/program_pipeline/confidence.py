"""Confidence skorlama modülü — alan düzeyinde güven puanı.

Confidence seviyeleri:
  0.95–1.00 → Resmî program sayfası, açık değer, kanıt doğrulanmış
  0.90–0.94 → Güncel resmî katalog/genel politika, açık alan
  0.85–0.89 → Başka resmî sayfa, güçlü kapsam doğrulaması
  0.75–0.84 → Eski ama çalışan resmî kaynak
  0.00–0.74 → Manuel inceleme kuyruğu

Eşik varsayılanı: 0.85 (config'den ayarlanabilir)
"""

from __future__ import annotations

from src.program_pipeline.models import ExtractedField


def classify_confidence(field: ExtractedField, threshold: float = 0.85) -> str:
    """Confidence seviyesini sınıflandır.

    Returns:
        "auto_write" | "needs_review" | "skip"
    """
    if field.value is None:
        return "skip"

    if field.confidence >= threshold:
        return "auto_write"

    if field.confidence >= 0.60:
        return "needs_review"

    return "skip"


def adjust_confidence(
    field: ExtractedField,
    is_official_domain: bool = True,
    domain_validated: bool = True,
    evidence_verified: bool = True,
    is_recent_content: bool = True,
    is_program_scope: bool = False,
) -> ExtractedField:
    """Ek doğrulama sonuçlarına göre confidence'ı ayarla.

    Args:
        field: Ayarlanacak alan
        is_official_domain: URL resmî domainde mi?
        domain_validated: Domain DNS/HTTP olarak erişilebilir mi?
        evidence_verified: Kanıt metni sayfada bulundu mu?
        is_recent_content: İçerik güncel mi (son 2 yıl)?
        is_program_scope: Program kapsamında mı (university > program)?

    Returns:
        Güncellenmiş confidence ile yeni ExtractedField
    """
    score = field.confidence

    # Domain doğrulama
    if not is_official_domain:
        score -= 0.30
    elif not domain_validated:
        score -= 0.10

    # Kanıt doğrulama
    if not evidence_verified:
        score -= 0.15

    # İçerik tazeliği
    if not is_recent_content:
        score -= 0.10

    # Kapsam bonusu
    if is_program_scope:
        score += 0.05

    # 0.0–1.0 arası sınırla
    score = max(0.0, min(1.0, score))

    updated = field.model_copy()
    updated.confidence = round(score, 4)
    return updated
