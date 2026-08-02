"""ResearchPipeline uçtan uca entegrasyon testi."""

from __future__ import annotations

import pytest
from src.models import AIValidationResponse, CandidateURL, DecisionType, ResearchCategory, UniversityRow
from src.pipeline import ResearchPipeline


class MockGeminiProvider:
    """Test için sahte Gemini AI sağlayıcısı."""

    def __init__(self, name: str = "gemini"):
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return "gemini-3.5-flash"

    @property
    def is_configured(self) -> bool:
        return True

    async def generate_text(self, prompt: str, **kwargs) -> str:
        return "mock text"

    async def validate_page(
        self,
        page_text: str,
        page_title: str,
        page_url: str,
        university_name: str,
        university_website: str,
        expected_category: str,
        system_prompt: str,
        temperature: float = 0.05,
    ) -> AIValidationResponse:
        return AIValidationResponse(
            is_relevant=True,
            category=expected_category,
            institution_match=True,
            campus_match=True,
            evidence=["Undergraduate Admission Requirements"],
            reason="Mock valid page",
            confidence=0.96,
        )

    async def discover_sources(self, **kwargs) -> list[str]:
        return ["https://testuni.edu/admissions"]


class ExplodingGeminiProvider(MockGeminiProvider):
    """Ücretsiz modda yanlışlıkla çağrılırsa testi düşürür."""

    async def validate_page(self, *args, **kwargs):
        raise AssertionError("Ücretsiz mod Gemini doğrulamasını çağırmamalı")

    async def discover_sources(self, **kwargs):
        raise AssertionError("Ücretsiz mod Gemini aramasını çağırmamalı")


@pytest.mark.asyncio
class TestPipeline:
    async def test_run_pipeline_with_mock_gemini(self):
        gemini = MockGeminiProvider("gemini")

        pipeline = ResearchPipeline(
            gemini_provider=gemini,
        )

        row = UniversityRow(
            row_number=2,
            university_name="Test University",
            website="https://testuni.edu",
            program_missing="Evet",
            admission_missing="Evet",
        )

        results = await pipeline.run([row])
        assert len(results) == 1
        res = results[0]
        assert res.university_name == "Test University"
        assert res.status is not None

    async def test_keyless_mode_never_calls_gemini(self):
        provider = ExplodingGeminiProvider()
        pipeline = ResearchPipeline(gemini_provider=provider, use_ai=False)

        async def fake_discover(**kwargs):
            return ["https://example.edu/english-proficiency/"]

        async def fake_fetch(url, category, source_query=""):
            return CandidateURL(
                url=url,
                requested_url=url,
                category=category,
                http_status=200,
                page_title="English Proficiency | Example University",
                extracted_text=(
                    "Example University English language proficiency requirements. "
                    "Applicants must submit TOEFL 80 or IELTS 6.5 for the 2026-2027 academic year."
                ),
            )

        pipeline.searcher.discover_candidates = fake_discover
        pipeline.fetcher.fetch_candidate = fake_fetch
        row = UniversityRow(
            row_number=2,
            university_name="Example University",
            website="https://example.edu",
            language_missing="Evet",
        )
        result = (await pipeline.run([row]))[0]
        assert result.best_results[ResearchCategory.LANGUAGE].decision == DecisionType.ACCEPTED
        assert result.best_results[ResearchCategory.LANGUAGE].dual_validation is None
