"""Aday URL araştırma modülü — anahtarsız, kural tabanlı keşif.

Her eksik alan için GERÇEK canlı web sayfalarını bulmak amacıyla:
1. Sitemap + ana sayfa bağlantıları
2. DuckDuckGo / Bing / Google canlı web araması
3. Resmî site içi derin tarama
yöntemlerini birleştirir.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.config import get_settings
from src.domain_utils import deduplicate_urls, is_official_domain, is_safe_url, normalize_url
from src.models import ResearchCategory
from src.search.query_builder import build_search_queries
from src.search.site_discovery import (
    discover_homepage_links,
    discover_sitemap_urls,
    deep_crawl_official_site,
    rank_candidate_urls,
)
from src.search.web_searcher import search_web_for_domain

logger = logging.getLogger(__name__)


class SourceSearcher:
    """Üniversite resmî sitesinde aday URL bulucu — kural tabanlı."""

    def __init__(self, provider=None):
        pass

    async def discover_candidates(
        self,
        university_name: str,
        official_domain: str,
        category: ResearchCategory,
    ) -> list[str]:
        """Belirtilen üniversite ve kategori için GERÇEK canlı aday URL listesi üret."""
        candidates: list[str] = []

        if not official_domain:
            return []

        settings = get_settings()

        # 1. Arama sorguları, sitemap ve ana sayfadaki gerçek bağlantıları paralel keşfet.
        queries = build_search_queries(university_name, official_domain, category)
        discovery_tasks = [
            search_web_for_domain(official_domain, query)
            for query in queries[:max(2, settings.search_query_count)]
        ]
        discovery_tasks.extend([
            discover_sitemap_urls(official_domain, category),
            discover_homepage_links(official_domain, category),
        ])
        discovered_groups = await asyncio.gather(*discovery_tasks, return_exceptions=True)
        for group in discovered_groups:
            if isinstance(group, list):
                candidates.extend(group)

        # 2. İlk keşif URL'lerinden başlayıp resmî site içinde birkaç katman ilerle.
        deep_candidates = await deep_crawl_official_site(
            official_domain=official_domain,
            category=category,
            seed_urls=candidates,
            max_pages=settings.deep_crawl_max_pages,
            max_depth=settings.deep_crawl_max_depth,
            concurrency=settings.deep_crawl_concurrency,
            max_candidates=settings.max_candidates_per_category,
        )
        candidates.extend(deep_candidates)

        # 3. Normalize et, tekilleştir ve resmî domain kontrolü yap.
        cleaned_urls: list[str] = []
        for url in candidates:
            norm = normalize_url(url)
            if (
                is_safe_url(norm)
                and is_official_domain(norm, official_domain)
            ):
                cleaned_urls.append(norm)

        deduped = rank_candidate_urls(
            cleaned_urls,
            category,
            limit=settings.max_candidates_per_category,
        )
        logger.info(
            "%s - %s: %d öncelikli canlı aday doğrulamaya gönderildi.",
            university_name,
            category.value,
            len(deduped),
        )
        return deduped
