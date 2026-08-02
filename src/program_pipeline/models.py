"""Program Pipeline — Pydantic veri modelleri.

Kural tabanlı, kanıt destekli, confidence puanı olan veri yapıları.
Hiçbir AI/LLM bağımlılığı yoktur.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    """Çıkarılan tek bir alan — değer + kanıt + güven bilgisi."""

    value: Any = None
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    source_type: Optional[str] = None  # "program_page" | "catalog_pdf" | "general_page" | "general_policy"
    page_number: Optional[int] = None
    scope: Literal["program", "university", "unknown"] = "unknown"
    confidence: float = 0.0
    is_explicit: bool = False        # Değer sayfada açıkça yazılmış mı?
    is_historical: bool = False      # Eski ama resmî ve çalışan kaynak mı?
    notes: Optional[str] = None


class ProgramRecord(BaseModel):
    """Tek bir program için tüm alanları ve kanıtları tutan kayıt."""

    university_id: str = ""
    university_name: str = ""
    program_name: ExtractedField = Field(default_factory=ExtractedField)
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    program_url: str = ""
    status: Literal["accepted", "needs_review", "rejected"] = "accepted"

    def get_field(self, name: str) -> ExtractedField:
        return self.fields.get(name, ExtractedField())

    def set_field(self, name: str, field: ExtractedField) -> None:
        self.fields[name] = field


class SourceUniversityRow(BaseModel):
    """URL kaynak Excel'den okunan tek bir üniversite satırı."""

    row_number: int
    university_id: Optional[str] = None
    university_name: str
    official_website: Optional[str] = None
    program_url: Optional[str] = None
    admission_url: Optional[str] = None
    language_url: Optional[str] = None
    tuition_url: Optional[str] = None
    notes: Optional[str] = None

    # "gerekli değil (... verisi mevcut)" yazılı sütunlar için bayraklar.
    # True ise URL boş olabilir ama veri zaten mevcut → official_website'ten keşif yap.
    program_not_needed: bool = False
    admission_not_needed: bool = False
    language_not_needed: bool = False
    tuition_not_needed: bool = False


class TemplateInfo(BaseModel):
    """Template Excel'den okunan meta bilgiler."""

    sheet_name: str = "Programlar"
    header_row: int = 1
    column_map: dict[str, int] = Field(default_factory=dict)  # "Üniversite ID" -> 1
    university_names: list[str] = Field(default_factory=list)
    existing_programs: list[tuple[str, str]] = Field(
        default_factory=list,
        description="(normalized_uni_id_or_name, normalized_program_name) çiftleri",
    )


class MatchResult(BaseModel):
    """İki Excel arasındaki üniversite eşleşme sonucu."""

    source_row: SourceUniversityRow
    match_type: Literal["id", "name", "domain", "needs_manual", "no_match"] = "no_match"
    matched_name: Optional[str] = None   # template'teki eşleşen üniversite adı
    candidates: list[SourceUniversityRow] = Field(default_factory=list)
    confidence: float = 0.0


class ProgramPipelineResult(BaseModel):
    """Program pipeline çalışmasının özet sonucu."""

    total_programs: int = 0
    cells_written: int = 0
    cells_empty: int = 0
    needs_review_count: int = 0
    output_path: Optional[str] = None
    audit_path: Optional[str] = None
    review_queue_path: Optional[str] = None
    errors: list[dict] = Field(default_factory=list)


# ─── Hata tipleri ───

PROGRAM_ERROR_TYPES = {
    "SOURCE_FILE_ERROR",
    "TEMPLATE_FILE_ERROR",
    "COLUMN_MAPPING_ERROR",
    "UNIVERSITY_MATCH_ERROR",
    "FETCH_ERROR",
    "ACCESS_BLOCKED",
    "PDF_EXTRACTION_ERROR",
    "PROGRAM_DISCOVERY_ERROR",
    "FIELD_EXTRACTION_ERROR",
    "VALIDATION_ERROR",
    "EXCEL_WRITE_ERROR",
}
