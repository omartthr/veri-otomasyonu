"""Kaldırılan Gemini entegrasyonunun çağrı yapmadığını doğrular."""

import pytest

from src.providers.gemini_provider import GeminiProvider


@pytest.mark.asyncio
async def test_gemini_provider_is_disabled_and_never_calls_api():
    provider = GeminiProvider(api_key="must-not-be-used")
    assert provider.is_configured is False
    assert provider.provider_name == "gemini_disabled"
    assert await provider.discover_sources() == []
    with pytest.raises(RuntimeError, match="devre dışı"):
        await provider.validate_page()
