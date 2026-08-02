"""Kanıt cümle doğrulama modülü.

AI modellerinin ürettiği kanıt cümlelerinin gerçekten indirilen
sayfa metninde bulunup bulunmadığını kontrol eder.

Bulunmayan kanıt varsa model sonucu geçersiz kabul edilir.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from src.models import AIValidationResponse, ProviderValidationResult

logger = logging.getLogger(__name__)

# Kanıt eşleştirme için minimum benzerlik eşiği
_MIN_OVERLAP_RATIO = 0.75


def _normalize_text(text: str) -> str:
    """Metin karşılaştırması için normalize et.

    Büyük/küçük harf, fazla boşluk ve noktalama farklılıklarını görmezden gelir.
    """
    text = text.lower()
    # Noktalama karakterlerini kaldır (kelime örtüşme karşılaştırması için)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def _evidence_found_in_text(evidence: str, page_text: str) -> bool:
    """Tek bir kanıt cümlesinin sayfa metninde bulunup bulunmadığını kontrol et.

    Tam eşleşme yerine, kelimelerin büyük çoğunluğunun metninde
    bulunmasını arar. Böylece küçük biçimlendirme farklarını tolere eder.
    """
    if not evidence or not page_text:
        return False

    norm_evidence = _normalize_text(evidence)
    norm_text = _normalize_text(page_text)

    # 1. Tam alt dizgi eşleşmesi
    if norm_evidence in norm_text:
        return True

    # 2. Kelime tabanlı örtüşme kontrolü
    evidence_words = set(norm_evidence.split())
    if len(evidence_words) < 3:
        # Çok kısa kanıtlar için tam eşleşme gerekir
        return False

    text_words = set(norm_text.split())
    overlap = evidence_words & text_words
    overlap_ratio = len(overlap) / len(evidence_words)

    return overlap_ratio >= _MIN_OVERLAP_RATIO


def verify_evidence(
    response: AIValidationResponse,
    page_text: str,
    provider_name: str,
) -> ProviderValidationResult:
    """AI doğrulama yanıtındaki kanıt cümlelerini sayfa metninde doğrula.

    Kurallar:
    - Kanıt listesi boşsa → geçersiz (kanıt sunulmamış)
    - Herhangi bir kanıt cümlesi metinde bulunamıyorsa → geçersiz
    - Tüm kanıtlar doğrulanırsa → geçerli

    Args:
        response: AI modelin doğrulama yanıtı
        page_text: İndirilen ve temizlenmiş sayfa metni
        provider_name: Sağlayıcı adı (gemini | openai)

    Returns:
        ProviderValidationResult: Kanıt doğrulama sonuçları dahil
    """
    verified: list[str] = []
    unverified: list[str] = []

    # Kanıt yoksa geçersiz
    if not response.evidence:
        return ProviderValidationResult(
            provider_name=provider_name,
            response=response,
            evidence_verified=False,
            verified_evidence=[],
            unverified_evidence=[],
            is_valid=False,
            invalidation_reason=f"{provider_name}: Kanıt cümlesi sunulmadı.",
        )

    for ev in response.evidence:
        if _evidence_found_in_text(ev, page_text):
            verified.append(ev)
        else:
            unverified.append(ev)

    # Herhangi bir kanıt doğrulanamazsa → geçersiz
    all_verified = len(unverified) == 0
    is_valid = response.is_relevant and all_verified

    invalidation_reason = None
    if not response.is_relevant:
        invalidation_reason = f"{provider_name}: is_relevant=False."
    elif not all_verified:
        invalidation_reason = (
            f"{provider_name}: {len(unverified)} kanıt cümlesi sayfa metninde "
            f"bulunamadı → sonuç geçersiz."
        )

    return ProviderValidationResult(
        provider_name=provider_name,
        response=response,
        evidence_verified=all_verified,
        verified_evidence=verified,
        unverified_evidence=unverified,
        is_valid=is_valid,
        invalidation_reason=invalidation_reason,
    )
