"""Domain yardımcıları testleri."""

from __future__ import annotations

import pytest

from src.domain_utils import (
    extract_domain, normalize_url, is_same_domain, is_official_domain,
    is_blocked_domain, is_search_engine, is_safe_url, is_homepage_only,
    deduplicate_urls, get_base_domain,
)


class TestExtractDomain:
    def test_basic(self):
        assert extract_domain("https://www.example.edu/page") == "example.edu"

    def test_no_scheme(self):
        assert extract_domain("example.edu/page") == "example.edu"

    def test_subdomain(self):
        assert extract_domain("https://admissions.example.edu") == "admissions.example.edu"

    def test_www_removed(self):
        assert extract_domain("https://www.example.edu") == "example.edu"

    def test_empty(self):
        assert extract_domain("") == ""

    def test_none_safe(self):
        assert extract_domain(None) == ""  # type: ignore


class TestNormalizeUrl:
    def test_adds_scheme(self):
        assert normalize_url("example.edu/page").startswith("https://")

    def test_removes_fragment(self):
        assert "#" not in normalize_url("https://example.edu/page#section")

    def test_empty(self):
        assert normalize_url("") == ""

    def test_does_not_append_slash_to_file_urls(self):
        assert normalize_url("https://example.edu/catalog.pdf").endswith("catalog.pdf")
        assert normalize_url("https://example.edu/sitemap.xml").endswith("sitemap.xml")


class TestIsSameDomain:
    def test_exact_match(self):
        assert is_same_domain("example.edu", "example.edu")

    def test_subdomain(self):
        assert is_same_domain("admissions.example.edu", "example.edu")

    def test_different(self):
        assert not is_same_domain("example.edu", "other.edu")

    def test_www(self):
        assert is_same_domain("https://www.example.edu", "https://example.edu")


class TestIsOfficialDomain:
    def test_official(self):
        assert is_official_domain("https://www.testuni.edu/prog", "https://www.testuni.edu")

    def test_subdomain_official(self):
        assert is_official_domain("https://admissions.testuni.edu/apply", "https://testuni.edu")

    def test_third_party(self):
        assert not is_official_domain("https://wikipedia.org/testuni", "https://testuni.edu")

    def test_empty(self):
        assert not is_official_domain("", "https://testuni.edu")


class TestIsBlockedDomain:
    def test_wikipedia(self):
        assert is_blocked_domain("https://en.wikipedia.org/wiki/Test")

    def test_studyportals(self):
        assert is_blocked_domain("https://www.studyportals.com/uni")

    def test_linkedin(self):
        assert is_blocked_domain("https://linkedin.com/school/test")

    def test_official_not_blocked(self):
        assert not is_blocked_domain("https://www.testuni.edu/programs")

    def test_empty_blocked(self):
        assert is_blocked_domain("")


class TestIsSearchEngine:
    def test_google(self):
        assert is_search_engine("https://www.google.com/search?q=test")

    def test_bing(self):
        assert is_search_engine("https://bing.com/search?q=test")

    def test_not_search(self):
        assert not is_search_engine("https://example.edu")


class TestIsSafeUrl:
    def test_safe(self):
        assert is_safe_url("https://example.edu")

    def test_localhost(self):
        assert not is_safe_url("http://localhost/admin")

    def test_private_ip(self):
        assert not is_safe_url("http://192.168.1.1/admin")

    def test_file_protocol(self):
        assert not is_safe_url("file:///etc/passwd")

    def test_empty(self):
        assert not is_safe_url("")

    def test_javascript(self):
        assert not is_safe_url("javascript:alert(1)")


class TestIsHomepageOnly:
    def test_homepage(self):
        assert is_homepage_only("https://example.edu")
        assert is_homepage_only("https://example.edu/")

    def test_not_homepage(self):
        assert not is_homepage_only("https://example.edu/programs")

    def test_with_query(self):
        assert not is_homepage_only("https://example.edu/?lang=en")


class TestDeduplicateUrls:
    def test_removes_duplicates(self):
        urls = [
            "https://example.edu/page",
            "https://example.edu/page#section",
            "https://example.edu/other",
        ]
        result = deduplicate_urls(urls)
        assert len(result) == 2

    def test_preserves_order(self):
        urls = ["https://b.com", "https://a.com"]
        result = deduplicate_urls(urls)
        assert result[0] == "https://b.com"


class TestGetBaseDomain:
    def test_simple(self):
        assert get_base_domain("example.edu") == "example.edu"

    def test_subdomain(self):
        assert get_base_domain("admissions.example.edu") == "example.edu"

    def test_double_tld(self):
        assert get_base_domain("www.example.edu.tr") == "example.edu.tr"
