"""Phoenix Seminary entegrasyon testi — @pytest.mark.live ile işaretli.

Canlı HTTP istekleri yapar. Normal pytest çalışmasında atlanır.
Çalıştırmak için: pytest tests/test_integration_phoenix.py -v -m live

Beklenen değerler:
  MDiv GPA: 2.5
  ThM GPA: 3.0
  DMin GPA: 3.0
  IELTS: 6.5
  TOEFL iBT: 92
  Başvuru ücreti: $40
"""

import asyncio
import pytest

pytestmark = pytest.mark.live  # pytest -m "not live" ile atla

PHOENIX_DOMAIN = "ps.edu"
PHOENIX_PROGRAM_URL = "https://ps.edu/degree-programs/"
PHOENIX_ADMISSION_URL = "https://ps.edu/admissions/"
PHOENIX_LANGUAGE_URL = "https://ps.edu/admissions/"
PHOENIX_TUITION_URL = "https://ps.edu/tuition-and-fees/"

EXPECTED = {
    "mdiv_gpa": 2.5,
    "thm_gpa": 3.0,
    "dmin_gpa": 3.0,
    "ielts": 6.5,
    "toefl": 92,
    "app_fee": 40,
}


@pytest.mark.asyncio
async def test_phoenix_gpa_extraction():
    """Phoenix Seminary kabul GPA değerlerini doğru çıkarıyor mu?"""
    from src.fetch.page_fetcher import PageFetcher
    from src.models import ResearchCategory
    from src.program_pipeline.content_sections import extract_html_sections
    from src.extractors.gpa import extract_gpa

    fetcher = PageFetcher()
    result = await fetcher.fetch_candidate(
        PHOENIX_ADMISSION_URL, ResearchCategory.ADMISSION
    )

    if not result or not result.extracted_text:
        pytest.skip("Phoenix Seminary'ye erişilemedi")

    import httpx
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(PHOENIX_ADMISSION_URL)
        if resp.status_code != 200:
            pytest.skip(f"HTTP {resp.status_code}")
        html = resp.content

    sections = extract_html_sections(html, PHOENIX_ADMISSION_URL)
    field = extract_gpa(sections, source_url=PHOENIX_ADMISSION_URL)

    assert field.value is not None, "GPA bulunamadı"
    assert 2.0 <= field.value <= 4.0


@pytest.mark.asyncio
async def test_phoenix_language_requirements():
    """Phoenix Seminary dil şartlarını doğru çıkarıyor mu?"""
    import httpx
    from src.program_pipeline.content_sections import extract_html_sections
    from src.extractors.language_tests import extract_ielts, extract_toefl

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(PHOENIX_LANGUAGE_URL)
        if resp.status_code != 200:
            pytest.skip(f"HTTP {resp.status_code}")
        html = resp.content

    sections = extract_html_sections(html, PHOENIX_LANGUAGE_URL)

    ielts = extract_ielts(sections, source_url=PHOENIX_LANGUAGE_URL)
    toefl = extract_toefl(sections, source_url=PHOENIX_LANGUAGE_URL)

    assert ielts.value == EXPECTED["ielts"], f"IELTS beklenen={EXPECTED['ielts']}, bulunan={ielts.value}"
    assert toefl.value == EXPECTED["toefl"], f"TOEFL beklenen={EXPECTED['toefl']}, bulunan={toefl.value}"


@pytest.mark.asyncio
async def test_phoenix_application_fee():
    """Phoenix Seminary başvuru ücretini doğru buluyor mu?"""
    import httpx
    from src.program_pipeline.content_sections import extract_html_sections
    from src.extractors.tuition import extract_application_fee

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(PHOENIX_ADMISSION_URL)
        if resp.status_code != 200:
            pytest.skip(f"HTTP {resp.status_code}")
        html = resp.content

    sections = extract_html_sections(html, PHOENIX_ADMISSION_URL)
    fee = extract_application_fee(sections, source_url=PHOENIX_ADMISSION_URL)

    assert fee.value is not None, "Başvuru ücreti bulunamadı"
    assert str(EXPECTED["app_fee"]) in str(fee.value), \
        f"Beklenen ${EXPECTED['app_fee']}, bulunan: {fee.value}"
