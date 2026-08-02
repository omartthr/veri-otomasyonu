"""Genel üniversite politikası extractor.

Kabul, dil ve ücret sayfalarından üniversite genelindeki değerleri çıkarır.
Program özel değerler bu genel değerlerin üzerine yazar.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.program_pipeline.content_sections import ContentSection, extract_html_sections, extract_pdf_sections
from src.program_pipeline.models import ExtractedField
from src.extractors.gpa import extract_gpa
from src.extractors.language_tests import extract_ielts, extract_toefl, extract_duolingo
from src.extractors.tuition import extract_annual_tuition, extract_application_fee
from src.extractors.boolean_fields import extract_boolean_field, extract_reference_count
from src.extractors.application_documents import extract_application_documents
from src.extractors.deadlines import extract_application_deadline
from src.extractors.duration import extract_duration
from src.extractors.internship import extract_internship, extract_coop, extract_exchange, extract_dual_degree
from src.extractors.career_outcomes import extract_employment_rate, extract_average_salary
from src.extractors.semantic_fields import extract_semantic_fields, add_derived_policy_fields

logger = logging.getLogger(__name__)


class GeneralPolicyExtractor:
    """Resmî URL'lerden üniversite genelindeki politikaları çıkarır."""

    def extract_from_html(
        self,
        html: bytes | str,
        source_url: str,
        url_type: str = "general",
    ) -> dict[str, ExtractedField]:
        """HTML içeriğinden tüm genel politika alanlarını çıkar.

        Args:
            html: Sayfa HTML içeriği
            source_url: Kaynak URL
            url_type: "admission" | "language" | "tuition" | "program" | "general"

        Returns:
            {alan_adı: ExtractedField} sözlüğü
        """
        sections = extract_html_sections(html, source_url)
        return self._extract_all(sections, source_url, url_type)

    def extract_from_pdf(
        self,
        pdf_bytes: bytes,
        source_url: str,
        url_type: str = "general",
    ) -> dict[str, ExtractedField]:
        """PDF içeriğinden tüm genel politika alanlarını çıkar."""
        sections = extract_pdf_sections(pdf_bytes, source_url)
        return self._extract_all(sections, source_url, url_type)

    def _extract_all(
        self,
        sections: list[ContentSection],
        source_url: str,
        url_type: str,
    ) -> dict[str, ExtractedField]:
        """Tüm alanları bölümlerden çıkar."""
        results: dict[str, ExtractedField] = {}

        # Her extractor çağrısını güvenle sarmalandır
        def safe(name: str, fn, *args, **kwargs) -> None:
            try:
                field = fn(*args, **kwargs)
                if field.value is not None:
                    results[name] = field
            except Exception as e:
                logger.debug("Extractor hatası (%s - %s): %s", name, source_url, e)

        # Kabul ve genel
        safe("Minimum GPA", extract_gpa, sections, "", source_url)
        safe("Minimum IELTS", extract_ielts, sections, source_url)
        safe("Minimum TOEFL", extract_toefl, sections, source_url)
        safe("Minimum Duolingo", extract_duolingo, sections, source_url)
        safe("Portfolyo Gerekli Mi", extract_boolean_field, "portfolio", sections, source_url)
        safe("Mülakat Gerekli Mi", extract_boolean_field, "interview", sections, source_url)
        safe("Essay Gerekli Mi", extract_boolean_field, "essay", sections, source_url)
        safe("CV Gerekli Mi", extract_boolean_field, "cv", sections, source_url)
        safe("Video Başvuru Gerekli Mi", extract_boolean_field, "video", sections, source_url)
        safe("Referans Sayısı", extract_reference_count, sections, source_url)
        safe("Başvuru Belgeleri", extract_application_documents, sections, source_url)
        safe("Son Başvuru Tarihi", extract_application_deadline, sections, source_url)

        # Ücret
        safe("Yıllık Ücret", extract_annual_tuition, sections, source_url)
        safe("Başvuru Ücreti", extract_application_fee, sections, source_url)

        # Program özellik
        safe("Eğitim Süresi", extract_duration, sections, source_url)
        safe("Staj İmkanı", extract_internship, sections, source_url)
        safe("Co-op İmkanı", extract_coop, sections, source_url)
        safe("Exchange İmkanı", extract_exchange, sections, source_url)
        safe("Çift Diploma", extract_dual_degree, sections, source_url)
        safe("Mezun İstihdamı", extract_employment_rate, sections, source_url)
        safe("Mezun Maaşı", extract_average_salary, sections, source_url)

        # Şablondaki anlatı/politika alanları (kanıt cümlesi zorunlu).
        semantic = extract_semantic_fields(
            sections,
            source_url,
            scope="university",
            url_type=url_type,
        )
        for name, field in semantic.items():
            if name not in results or field.confidence > results[name].confidence:
                results[name] = field

        results = add_derived_policy_fields(results)

        # source_type'ı url_type'a göre güncelle
        for field in results.values():
            if url_type != "general":
                field.source_type = url_type

        return results
