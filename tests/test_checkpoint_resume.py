"""Checkpoint ve resume testleri."""
import pytest
import tempfile
from pathlib import Path
from src.program_pipeline.checkpoint import CheckpointManager, PageCache

@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path

def test_checkpoint_complete_and_check(tmp_dir):
    cp = CheckpointManager(tmp_dir)
    assert not cp.is_completed("Harvard University")
    cp.mark_completed("Harvard University", program_count=5)
    assert cp.is_completed("Harvard University")

def test_checkpoint_persists(tmp_dir):
    cp1 = CheckpointManager(tmp_dir)
    cp1.mark_completed("MIT")
    # Yeni instance oluştur — kalıcılık kontrolü
    cp2 = CheckpointManager(tmp_dir)
    assert cp2.is_completed("MIT")

def test_checkpoint_reset(tmp_dir):
    cp = CheckpointManager(tmp_dir)
    cp.mark_completed("Stanford")
    cp.reset()
    assert not cp.is_completed("Stanford")

def test_checkpoint_failed(tmp_dir):
    cp = CheckpointManager(tmp_dir)
    cp.mark_failed("Broken Uni", "HTTP 403")
    assert "Broken Uni" in cp._state["failed_universities"]

# ── PageCache ──

def test_page_cache_html(tmp_dir):
    cache = PageCache(tmp_dir)
    url = "https://example.edu/admissions/"
    assert cache.get_html(url) is None
    cache.set_html(url, b"<html>test</html>")
    result = cache.get_html(url)
    assert result == b"<html>test</html>"

def test_page_cache_pdf(tmp_dir):
    cache = PageCache(tmp_dir)
    url = "https://example.edu/catalog.pdf"
    cache.set_pdf(url, b"%PDF fake")
    assert cache.get_pdf(url) == b"%PDF fake"

def test_page_cache_clear(tmp_dir):
    cache = PageCache(tmp_dir)
    cache.set_html("https://example.edu/", b"content")
    cache.clear()
    assert cache.get_html("https://example.edu/") is None
