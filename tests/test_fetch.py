"""Fetch ve metin çıkarma modülleri testleri."""

from __future__ import annotations

import pytest
from src.fetch.html_extractor import extract_html_content
from src.fetch.pdf_extractor import extract_pdf_content
from src.fetch.page_fetcher import PageFetcher, _looks_like_challenge
from src.models import ResearchCategory


class TestHtmlExtractor:
    def test_extracts_title_and_clean_text(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test University Admissions</title></head>
        <body>
            <header><nav><a href="#">Home</a></nav></header>
            <main>
                <h1>Undergraduate Admission Requirements</h1>
                <p>Applicants must submit official transcripts and proof of English proficiency.</p>
            </main>
            <footer><p>Copyright 2026</p></footer>
            <script>console.log("ignore me");</script>
        </body>
        </html>
        """
        title, text = extract_html_content(html)
        assert title == "Test University Admissions"
        assert "Undergraduate Admission Requirements" in text
        assert "official transcripts" in text
        assert "Copyright" not in text
        assert "ignore me" not in text

    def test_empty_html(self):
        title, text = extract_html_content("")
        assert title == ""
        assert text == ""


class TestPdfExtractor:
    def test_empty_pdf(self):
        title, text = extract_pdf_content(b"")
        assert title == ""
        assert text == ""


def test_challenge_page_detection():
    assert _looks_like_challenge(b"<title>Just a moment...</title>Checking your browser")
    assert _looks_like_challenge(b"Please verify you are human with a CAPTCHA challenge")
    assert not _looks_like_challenge(b"<h1>English Proficiency Requirements</h1>")


@pytest.mark.asyncio
class TestPageFetcher:
    async def test_unsafe_url_blocked(self):
        fetcher = PageFetcher()
        result = await fetcher.fetch_candidate("javascript:alert(1)", ResearchCategory.PROGRAM)
        assert result.http_status == 403
