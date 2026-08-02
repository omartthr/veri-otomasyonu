"""Hedefli İkinci Tarama Motoru — Eksik alanlar için arama aramaları çalıştırır.

Birinci turda eksik kalan kritik alanlar için resmî domainde hedefli web aramaları yapar.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.domain_utils import is_official_domain, is_safe_url
from src.search.web_searcher import search_web_for_domain

logger = logging.getLogger(__name__)


async def run_targeted_search_for_program(
    official_domain: str,
    program_name: str,
    missing_aspect: str = "admission requirements",
) -> list[str]:
    """Program adıyla hedefli ikinci tur web araması çalıştırır.

    Args:
        official_domain: Üniversite resmî domain'i
        program_name: Tam program adı (örn: "Master of Divinity")
        missing_aspect: Eksik alan bağlamı (tuition fees, IELTS TOEFL, credits curriculum)

    Returns:
        Doğrulanmış resmî kaynak URL'leri
    """
    if not official_domain or not program_name:
        return []

    query = f'site:{official_domain} "{program_name}" {missing_aspect}'
    try:
        urls = await search_web_for_domain(official_domain, query)
        valid_urls = [
            u for u in urls
            if is_safe_url(u) and is_official_domain(u, official_domain)
        ]
        return valid_urls[:3]
    except Exception as e:
        logger.debug("Targeted search hatası (%s - %s): %s", program_name, missing_aspect, e)
        return []
