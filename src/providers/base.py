"""AI sağlayıcı temel arayüzü (Protocol).

Tüm AI sağlayıcılar bu protokolü uygular.
Kodun geri kalanında doğrudan Gemini veya OpenAI SDK çağrıları bulunmaz;
bunun yerine bu arayüz üzerinden çalışılır.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from src.models import AIValidationResponse


@runtime_checkable
class AIProvider(Protocol):
    """AI sağlayıcı arayüzü.

    Her sağlayıcı (Gemini, OpenAI vb.) bu protokolü uygulamalıdır.
    """

    @property
    def provider_name(self) -> str:
        """Sağlayıcı adı (ör. 'gemini', 'openai')."""
        ...

    @property
    def model_name(self) -> str:
        """Kullanılan model adı."""
        ...

    @property
    def is_configured(self) -> bool:
        """Sağlayıcının yapılandırılıp yapılandırılmadığı (API anahtarı vb.)."""
        ...

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Metin üretimi.

        Args:
            prompt: Kullanıcı istemi
            system_instruction: Sistem talimatı
            temperature: Yaratıcılık seviyesi (0.0 – 1.0)
            max_tokens: Maksimum çıktı token sayısı

        Returns:
            Üretilen metin
        """
        ...

    async def validate_page(
        self,
        page_text: str,
        page_title: str,
        page_url: str,
        university_name: str,
        university_website: str,
        expected_category: str,
        system_prompt: str,
    ) -> AIValidationResponse:
        """Sayfa doğrulama.

        İndirilen bir sayfanın metnini, beklenen kategori ile karşılaştırarak
        AIValidationResponse döndürür.

        Args:
            page_text: Temizlenmiş sayfa metni
            page_title: Sayfa başlığı
            page_url: Yönlendirmelerden sonra ulaşılan son URL
            university_name: Üniversite adı
            university_website: Üniversitenin resmî web sitesi
            expected_category: Beklenen kategori (program, admission, language, tuition)
            system_prompt: Sistem istemi (prompts/ klasöründen)

        Returns:
            AIValidationResponse
        """
        ...

    async def discover_sources(
        self,
        university_name: str,
        university_website: str,
        category: str,
        search_context: str,
        system_prompt: str,
    ) -> list[str]:
        """Kaynak keşfi — AI'dan aday URL listesi al.

        Not: Bu fonksiyonun döndürdüğü URL'ler doğrudan kabul edilmez;
        sistem tarafından indirilip doğrulanmaları gerekir.

        Args:
            university_name: Üniversite adı
            university_website: Üniversitenin resmî web sitesi
            category: Araştırma kategorisi
            search_context: Arama bağlamı
            system_prompt: Sistem istemi

        Returns:
            Aday URL listesi
        """
        ...
