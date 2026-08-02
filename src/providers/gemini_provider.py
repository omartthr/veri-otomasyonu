"""Gemini AI sağlayıcısı — DEVRE DIŞI.

Bu dosya artık yalnızca geriye dönük uyumluluk için var.
google-genai bağımlılığı kaldırılmıştır.
Sistem tamamen kural tabanlı, deterministik modda çalışmaktadır.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Gemini AI sağlayıcısı stub — devre dışı.

    Bu sınıf artık hiçbir AI çağrısı yapmamaktadır.
    Mevcut import'ların bozulmaması için korunmaktadır.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        search_model: Optional[str] = None,
        validation_model: Optional[str] = None,
    ):
        self._api_key = None

    @property
    def provider_name(self) -> str:
        return "gemini_disabled"

    @property
    def model_name(self) -> str:
        return "none"

    @property
    def is_configured(self) -> bool:
        return False

    async def validate_page(self, *args, **kwargs):
        raise RuntimeError("GeminiProvider devre dışı. Lütfen kural tabanlı motoru kullanın.")

    async def discover_sources(self, *args, **kwargs) -> list:
        return []

    async def generate_text(self, *args, **kwargs) -> str:
        return ""
