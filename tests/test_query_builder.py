"""Genişletilmiş kategori arama sorguları testleri."""

from src.models import ResearchCategory
from src.search.query_builder import build_search_queries


def test_queries_cover_web_catalog_and_pdf_routes():
    queries = build_search_queries(
        "Example University",
        "https://www.example.edu",
        ResearchCategory.LANGUAGE,
    )
    assert len(queries) >= 6
    assert any(query.startswith("site:example.edu") for query in queries)
    assert any("filetype:pdf" in query for query in queries)
    assert any("catalog OR handbook OR bulletin" in query for query in queries)
    assert any('"Example University"' in query for query in queries)
    assert not any("site:https://" in query for query in queries)
