"""Program özel veri extractor v3.

Tek bir programın kendi sayfasından ve sınırlı yakın bölümlerinden program özgü alanları çıkarır.
Genel footer, menü ve ilgisiz kartlar programa ait veri olarak kullanılmaz.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from src.program_pipeline.content_sections import ContentSection
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

# URL türlerine göre çıkarılmasına izin verilen alanlar
_ALLOWED_FIELDS_BY_URL_TYPE = {
    "program": {
        "Program Adı", "Fakülte", "Eğitim Süresi", "Kredi Sayısı", "Program Dili",
        "Staj İmkanı", "Co-op İmkanı", "Exchange İmkanı", "Çift Diploma",
        "Mezun İstihdamı", "Mezun Maaşı", "Minimum GPA", "Standart Test Politikası",
        "Başvuru Belgeleri", "Portfolyo Gerekli Mi", "Mülakat Gerekli Mi", "Essay Gerekli Mi",
    },
    "admission": {
        "Minimum GPA", "Başvuru Türü", "Başvuru Ücreti", "Essay Gerekli Mi",
        "Referans Sayısı", "CV Gerekli Mi", "Mülakat Gerekli Mi", "Başvuru Belgeleri",
        "Transkript/GED Gereksinimi", "Son Başvuru Tarihi", "Video Başvuru Gerekli Mi",
    },
    "language": {
        "Minimum IELTS", "Minimum TOEFL", "Minimum Duolingo",
        "İngilizce Yeterlilik Gerekli Mi", "Muafiyet Şartları",
    },
    "tuition": {
        "Yıllık Ücret", "Kredi Başı Ücret", "Dönemlik Ücret", "Zorunlu Ek Ücretler",
        "Akademik Yıl", "Başvuru Ücreti",
    },
}


class ProgramExtractor:
    """Program sayfasından program özel alanlarını çıkarır."""

    def extract(
        self,
        sections: list[ContentSection],
        program_name: str,
        source_url: str,
        url_type: str = "program",
    ) -> dict[str, ExtractedField]:
        """Program bölümlerinden sınırlı kapsamda alanları çıkar.

        Args:
            sections: İçerik bölümleri
            program_name: Program adı (bağlam eşleştirme için)
            source_url: Kaynak URL
            url_type: URL türü ('program', 'admission', 'language', 'tuition')

        Returns:
            {alan_adı: ExtractedField} sözlüğü
        """
        # Yalnızca program adına yakın bölümleri tut
        relevant_sections = self._filter_relevant_sections(sections, program_name)
        target_sections = relevant_sections if relevant_sections else [
            s for s in sections
            if s.source_type not in ("json_ld", "menu", "footer", "nav")
        ]

        allowed_fields = _ALLOWED_FIELDS_BY_URL_TYPE.get(url_type, _ALLOWED_FIELDS_BY_URL_TYPE["program"])
        results: dict[str, ExtractedField] = {}

        def safe(name: str, fn, *args, **kwargs):
            if name not in allowed_fields and url_type != "program":
                return
            try:
                field = fn(*args, **kwargs)
                if field.value is not None:
                    field.scope = "program"
                    results[name] = field
            except Exception as e:
                logger.debug("ProgramExtractor hatası (%s - %s): %s", name, source_url, e)

        safe("Minimum GPA", extract_gpa, target_sections, program_name, source_url)
        safe("Minimum IELTS", extract_ielts, target_sections, source_url)
        safe("Minimum TOEFL", extract_toefl, target_sections, source_url)
        safe("Minimum Duolingo", extract_duolingo, target_sections, source_url)
        safe("Yıllık Ücret", extract_annual_tuition, target_sections, source_url)
        safe("Başvuru Ücreti", extract_application_fee, target_sections, source_url)
        safe("Portfolyo Gerekli Mi", extract_boolean_field, "portfolio", target_sections, source_url)
        safe("Mülakat Gerekli Mi", extract_boolean_field, "interview", target_sections, source_url)
        safe("Essay Gerekli Mi", extract_boolean_field, "essay", target_sections, source_url)
        safe("CV Gerekli Mi", extract_boolean_field, "cv", target_sections, source_url)
        safe("Video Başvuru Gerekli Mi", extract_boolean_field, "video", target_sections, source_url)
        safe("Referans Sayısı", extract_reference_count, target_sections, source_url)
        safe("Başvuru Belgeleri", extract_application_documents, target_sections, source_url)
        safe("Son Başvuru Tarihi", extract_application_deadline, target_sections, source_url)
        safe("Eğitim Süresi", extract_duration, target_sections, source_url)
        safe("Staj İmkanı", extract_internship, target_sections, source_url)
        safe("Co-op İmkanı", extract_coop, target_sections, source_url)
        safe("Exchange İmkanı", extract_exchange, target_sections, source_url)
        safe("Çift Diploma", extract_dual_degree, target_sections, source_url)
        safe("Mezun İstihdamı", extract_employment_rate, target_sections, source_url)
        safe("Mezun Maaşı", extract_average_salary, target_sections, source_url)

        semantic = extract_semantic_fields(
            target_sections,
            source_url,
            scope="program",
            url_type=url_type,
        )
        for name, field in semantic.items():
            if name in allowed_fields or url_type == "program":
                if name not in results or field.confidence > results[name].confidence:
                    results[name] = field

        return add_derived_policy_fields(results)

    def _filter_relevant_sections(
        self,
        sections: list[ContentSection],
        program_name: str,
    ) -> list[ContentSection]:
        """Program adının veya yakın derece terimlerinin geçtiği bölümleri seç."""
        if not program_name:
            return []

        keywords = {
            token
            for token in re.findall(r"[a-z0-9]+", program_name.lower())
            if len(token) >= 4
        }
        keywords -= {
            "master", "masters", "bachelor", "bachelors", "doctor", "doctoral",
            "degree", "program", "certificate", "diploma", "graduate",
            "undergraduate", "arts", "science",
        }

        relevant = []
        for idx, section in enumerate(sections):
            if section.source_type in ("json_ld", "menu", "footer", "nav"):
                continue
            combined = f"{section.heading or ''}\n{section.text[:500]}".lower()
            if keywords and any(
                re.search(rf"\b{re.escape(kw)}\b", combined)
                for kw in keywords
            ):
                relevant.append(section)
                # Komşu 1 ön ve 1 arka bölümü ekle (bağlam için)
                if idx > 0 and sections[idx - 1] not in relevant:
                    relevant.append(sections[idx - 1])
                if idx + 1 < len(sections) and sections[idx + 1] not in relevant:
                    relevant.append(sections[idx + 1])

        return relevant
