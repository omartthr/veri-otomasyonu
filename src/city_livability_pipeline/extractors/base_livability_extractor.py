"""Şehir & Yaşam Rehberi — Çıkarılan Alan Temel Modeli ve Soyut Çıkarıcı.

Her çıkarıcı bu taban sınıfı ve `ExtractedLivabilityField` modelini kullanır.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ExtractedLivabilityField(BaseModel):
    """Kanıtlı, güven puanlı ve kaynaklı çıkarılmış tek bir alan."""

    value: Any = None
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    source_type: Optional[str] = "resmi"  # "resmi" | "ilan" | "tahmin" | "türev"
    confidence: float = 0.0
    confidence_level: str = "Düşük"       # "Yüksek" | "Orta" | "Düşük"
    needs_review: bool = False
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None

    @property
    def is_accepted(self) -> bool:
        return self.value is not None and self.confidence >= 0.60
