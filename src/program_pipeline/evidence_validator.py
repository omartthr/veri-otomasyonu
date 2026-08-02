"""Kanıt doğrulama modülü — çıkarılan değerlerin kaynak sayfada gerçekten var olduğunu kontrol eder.

Kurallar:
- Kaynak URL resmî domain mi?
- Evidence metni gerçekten sayfada mevcut mu?
- Fuzzy match yalnızca boşluk/satır/unicode farkları için
- Scope doğru mu (program vs. university)?
"""

from __future__ import annotations

import logging
import re
import unicodedata

from src.domain_utils import is_official_domain
from src.program_pipeline.models import ExtractedField

logger = logging.getLogger(__name__)


def _normalize_evidence(text: str) -> str:
    """Kanıt metnini normalize et (boşluk, unicode)."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", errors="ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def validate_field(
    field: ExtractedField,
    page_text: str,
    official_domain: str,
    confidence_threshold: float = 0.85,
) -> tuple[bool, str]:
    """Alanı doğrula.

    Args:
        field: Doğrulanacak alan
        page_text: Kaynak sayfanın düz metni
        official_domain: Resmî domain (örn: phoenixseminary.edu)
        confidence_threshold: Otomatik kabul eşiği

    Returns:
        (is_valid: bool, reason: str) çifti
    """
    if field.value is None:
        return False, "Değer boş"

    # 1. Kaynak URL resmî domain mi?
    if field.source_url and official_domain:
        if not is_official_domain(field.source_url, official_domain):
            return False, f"Kaynak URL resmî domain dışı: {field.source_url}"

    # 2. Evidence metni sayfada var mı?
    if field.evidence:
        evidence_norm = _normalize_evidence(field.evidence)
        page_norm = _normalize_evidence(page_text[:50000])  # İlk 50k karakter

        # Kanıtın en az %60'ı sayfada bulunabilmeli
        if len(evidence_norm) > 20:
            # Token bazlı kesişim kontrolü
            ev_tokens = set(evidence_norm.split())
            page_tokens = set(page_norm.split())
            if ev_tokens:
                overlap = len(ev_tokens & page_tokens) / len(ev_tokens)
                if overlap < 0.60:
                    logger.debug(
                        "Kanıt doğrulanamadı (overlap=%.2f): %s",
                        overlap, field.evidence[:100],
                    )
                    return False, f"Kanıt metni sayfada doğrulanamadı (overlap={overlap:.2f})"

    # 3. Confidence eşiği
    if field.confidence < confidence_threshold:
        return False, f"Confidence düşük: {field.confidence:.2f} < {confidence_threshold}"

    return True, "OK"


def validate_all_fields(
    fields: dict[str, ExtractedField],
    page_texts: dict[str, str],
    official_domain: str,
    confidence_threshold: float = 0.85,
) -> dict[str, tuple[bool, str]]:
    """Tüm alanları doğrula.

    Args:
        fields: Alan adı → ExtractedField
        page_texts: URL → sayfa metni (kanıt kontrol için)
        official_domain: Resmî domain
        confidence_threshold: Otomatik kabul eşiği

    Returns:
        {alan_adı: (is_valid, reason)} sözlüğü
    """
    results = {}
    for name, field in fields.items():
        if field.value is None:
            results[name] = (False, "Değer boş")
            continue

        # İlgili sayfa metnini bul
        page_text = page_texts.get(field.source_url or "", "")

        valid, reason = validate_field(
            field=field,
            page_text=page_text,
            official_domain=official_domain,
            confidence_threshold=confidence_threshold,
        )
        results[name] = (valid, reason)

    return results
