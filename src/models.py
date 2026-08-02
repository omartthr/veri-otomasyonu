"""Pydantic veri modelleri — tüm uygulama genelinde kullanılan veri yapıları.

Yüksek doğruluk mimarisi: Çift AI doğrulama (Gemini + OpenAI),
kanıt doğrulama ve sıkı karar kuralları.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─────────────────────────── Sabitler ───────────────────────────

class ResearchCategory(str, Enum):
    """Araştırılacak bilgi kategorileri."""
    PROGRAM = "program"
    ADMISSION = "admission"
    LANGUAGE = "language"
    TUITION = "tuition"


class RowStatus(str, Enum):
    """Satır işlem durumu."""
    PENDING = "Bekliyor"
    IN_PROGRESS = "İnceleniyor"
    COMPLETED = "Tamamlandı"
    MANUAL_REVIEW = "Manuel Kontrol"
    NOT_FOUND = "Web sitesi yok/bulunamadı"


class DecisionType(str, Enum):
    """Aday URL karar türü."""
    ACCEPTED = "accepted"
    MANUAL_REVIEW = "manual_review"
    REJECTED = "rejected"
    NOT_FOUND = "not_found"


# ───────────────── Eksik alan → sütun eşleştirmesi ─────────────────

# F-I sütunları: "Evet" ise araştırılacak
# J-M sütunları: Bulunan URL buraya yazılacak
MISSING_FLAG_COLUMNS: dict[ResearchCategory, str] = {
    ResearchCategory.PROGRAM: "F",
    ResearchCategory.ADMISSION: "G",
    ResearchCategory.LANGUAGE: "H",
    ResearchCategory.TUITION: "I",
}

URL_RESULT_COLUMNS: dict[ResearchCategory, str] = {
    ResearchCategory.PROGRAM: "J",
    ResearchCategory.ADMISSION: "K",
    ResearchCategory.LANGUAGE: "L",
    ResearchCategory.TUITION: "M",
}

# Korunan sütunlar — Q, R, S, T
PROTECTED_COLUMNS = ["Q", "R", "S", "T"]

# Durum ve Notlar sütunları
STATUS_COLUMN = "O"
NOTES_COLUMN = "P"
ASSIGNED_PERSON_COLUMN = "N"
DEFAULT_ASSIGNED_PERSON = "Omar Taher"


# ─────────────────────── Excel satırı modeli ───────────────────────

class UniversityRow(BaseModel):
    """Excel'den okunan tek bir üniversite satırı."""

    row_number: int = Field(..., description="Excel satır numarası (1-tabanlı)")
    university_id: Optional[str] = Field(None, description="A sütunu — Üniversite ID")
    university_name: str = Field(..., description="B sütunu — Üniversite Adı")
    city: Optional[str] = Field(None, description="C sütunu — Şehir")
    institution_type: Optional[str] = Field(None, description="D sütunu — Kurum Türü")
    website: Optional[str] = Field(None, description="E sütunu — Web Sitesi")

    # Eksik bayrakları (F-I)
    program_missing: Optional[str] = Field(None, description="F — Program Listesi Eksik?")
    admission_missing: Optional[str] = Field(None, description="G — Kabul Şartları Eksik?")
    language_missing: Optional[str] = Field(None, description="H — Dil Şartları Eksik?")
    tuition_missing: Optional[str] = Field(None, description="I — Ücret Bilgisi Eksik?")

    # Mevcut URL'ler (J-M)
    program_url: Optional[str] = Field(None, description="J — Program Listesi URL")
    admission_url: Optional[str] = Field(None, description="K — Kabul Şartları URL")
    language_url: Optional[str] = Field(None, description="L — Dil Şartları URL")
    tuition_url: Optional[str] = Field(None, description="M — Ücret URL")

    # Ek bilgiler (N-P)
    assigned_person: Optional[str] = Field(None, description="N — Atanan Kişi")
    status: Optional[str] = Field(None, description="O — Durum")
    notes: Optional[str] = Field(None, description="P — Notlar")

    def get_missing_categories(self) -> list[ResearchCategory]:
        """'Evet' olarak işaretlenmiş eksik alanların listesini döndür.

        'Hayır' ve 'gerekli değil' olan alanlar dahil edilmez.
        """
        categories: list[ResearchCategory] = []
        flag_map = {
            ResearchCategory.PROGRAM: self.program_missing,
            ResearchCategory.ADMISSION: self.admission_missing,
            ResearchCategory.LANGUAGE: self.language_missing,
            ResearchCategory.TUITION: self.tuition_missing,
        }
        for category, value in flag_map.items():
            if value and value.strip().lower() == "evet":
                categories.append(category)
        return categories

    def get_existing_url(self, category: ResearchCategory) -> Optional[str]:
        """Belirtilen kategori için mevcut URL'yi döndür."""
        url_map = {
            ResearchCategory.PROGRAM: self.program_url,
            ResearchCategory.ADMISSION: self.admission_url,
            ResearchCategory.LANGUAGE: self.language_url,
            ResearchCategory.TUITION: self.tuition_url,
        }
        return url_map.get(category)


# ───────────────── AI doğrulama yanıt modeli ─────────────────

class AIValidationResponse(BaseModel):
    """Hem Gemini hem OpenAI'dan beklenen standart JSON yanıt şeması.

    İki model de aynı şemayı döndürür; birbirlerinin çıktılarını görmez.
    """

    is_relevant: bool = Field(..., description="Sayfa ilgili mi?")
    category: str = Field(
        ..., description="program | admission | language | tuition | unknown"
    )
    institution_match: bool = Field(..., description="Kurum eşleşmesi")
    campus_match: bool = Field(True, description="Kampüs eşleşmesi")
    evidence: list[str] = Field(
        default_factory=list, description="Sayfadan kanıt cümleleri"
    )
    reason: str = Field("", description="Kısa değerlendirme")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Güven skoru 0–1")
    content_year: Optional[int] = Field(None, description="İçerik yılı")
    scope: str = Field(
        "unknown", description="Bilginin kapsamı: institution | program | mixed | unknown"
    )
    warnings: list[str] = Field(default_factory=list, description="Uyarılar")


# ──────────────── Tek sağlayıcı doğrulama sonucu ────────────────

class ProviderValidationResult(BaseModel):
    """Tek bir Gemini doğrulama adımının sonucu + kanıt doğrulaması."""

    provider_name: str = Field(..., description="gemini_pass1 | gemini_pass2")
    response: AIValidationResponse
    evidence_verified: bool = Field(
        False, description="Kanıt cümleleri gerçekten sayfa metninde bulundu mu?"
    )
    verified_evidence: list[str] = Field(
        default_factory=list, description="Metinde doğrulanan kanıt cümleleri"
    )
    unverified_evidence: list[str] = Field(
        default_factory=list, description="Metinde bulunamayan kanıt cümleleri"
    )
    is_valid: bool = Field(
        False,
        description="Sonuç geçerli mi? (is_relevant=True VE kanıt doğrulanmış)",
    )
    invalidation_reason: Optional[str] = Field(
        None, description="Geçersizse nedeni"
    )


# ──────────────── Çift doğrulama birleşik sonucu ────────────────

class DualValidationResult(BaseModel):
    """İki bağımsız Gemini doğrulama geçişinin birleşik sonucu.

    Otomatik kabul için TÜM koşullar sağlanmalıdır:
    - İki bağımsız Gemini değerlendirmesi de is_relevant=True
    - Kategori değerleri aynı
    - Kurum eşleşmesi aynı (True)
    - Kampüs eşleşmesi aynı (True)
    - İki güven skoru da >= 0.90
    - Kanıt cümleleri metinde doğrulanmış
    """

    gemini_pass1_result: Optional[ProviderValidationResult] = None
    gemini_pass2_result: Optional[ProviderValidationResult] = None

    # Uzlaşma sonuçları
    both_relevant: bool = Field(False, description="İkisi de is_relevant=True mi?")
    categories_agree: bool = Field(False, description="İkisi de aynı category mi?")
    institutions_agree: bool = Field(False, description="İkisi de institution_match=True mi?")
    campuses_agree: bool = Field(False, description="İkisi de campus_match=True mi?")
    both_confident: bool = Field(
        False, description="İkisinin de confidence >= 0.90 mı?"
    )
    both_evidence_verified: bool = Field(
        False, description="İkisinin de kanıtları metinde doğrulanmış mı?"
    )

    agreed_category: Optional[str] = Field(
        None, description="Üzerinde uzlaşılan kategori"
    )
    consensus_confidence: float = Field(
        0.0, description="İki Gemini değerlendirmesinin minimum confidence değeri"
    )

    disagreement_details: list[str] = Field(
        default_factory=list, description="Uyuşmazlık detayları"
    )

    @property
    def is_unanimous(self) -> bool:
        """Tam uzlaşma var mı? (Otomatik kabul için ön koşul)."""
        return (
            self.both_relevant
            and self.categories_agree
            and self.institutions_agree
            and self.campuses_agree
            and self.both_confident
            and self.both_evidence_verified
        )


# ───────────────────── Güven puanı dağılımı ─────────────────────

class ScoreBreakdown(BaseModel):
    """100 üzerinden güven puanı bileşenleri."""

    official_domain: int = Field(0, ge=0, le=20, description="Resmî domain: 0-20")
    http_accessible: int = Field(0, ge=0, le=10, description="HTTP erişilebilirlik: 0-10")
    institution_name_match: int = Field(0, ge=0, le=15, description="Kurum adı eşleşmesi: 0-15")
    campus_match: int = Field(0, ge=0, le=10, description="Kampüs eşleşmesi: 0-10")
    category_keywords: int = Field(0, ge=0, le=15, description="Kategori anahtar kelimeleri: 0-15")
    strong_category_evidence: int = Field(0, ge=0, le=15, description="Güçlü kategori kanıtı: 0-15")
    ai_confidence: int = Field(0, ge=0, le=10, description="Çift AI consensus confidence: 0-10")
    recency: int = Field(0, ge=0, le=5, description="Güncellik: 0-5")

    # Cezalar
    penalty_old_catalog: int = Field(0, le=0, ge=-10)
    penalty_homepage_only: int = Field(0, le=0, ge=-15)
    penalty_wrong_campus: int = Field(0, le=0, ge=-25)

    @property
    def total(self) -> int:
        """Toplam puan (0–100 arasında kenetlenmiş)."""
        raw = (
            self.official_domain
            + self.http_accessible
            + self.institution_name_match
            + self.campus_match
            + self.category_keywords
            + self.strong_category_evidence
            + self.ai_confidence
            + self.recency
            + self.penalty_old_catalog
            + self.penalty_homepage_only
            + self.penalty_wrong_campus
        )
        return max(0, min(100, raw))

    @property
    def decision(self) -> DecisionType:
        """Puana göre karar — yüksek doğruluk eşikleri.

        NOT: Bu yalnızca puan tabanlı ön karar verir.
        Nihai karar iki bağımsız Gemini doğrulamasını da gerektirir.
        """
        if self.total >= 90:
            return DecisionType.ACCEPTED
        elif self.total >= 70:
            return DecisionType.MANUAL_REVIEW
        else:
            return DecisionType.REJECTED


# ───────────────────── Aday URL modeli ─────────────────────

class CandidateURL(BaseModel):
    """Araştırma sırasında bulunan aday URL."""

    url: str = Field(..., description="Normalize edilmiş URL")
    requested_url: Optional[str] = Field(None, description="İlk istenen aday URL")
    redirect_count: int = Field(0, ge=0, description="İzlenen HTTP yönlendirme sayısı")
    category: ResearchCategory
    source_query: str = Field("", description="Bu URL'yi bulan arama sorgusu")
    http_status: Optional[int] = Field(None, description="HTTP durum kodu")
    content_type: Optional[str] = Field(None, description="İçerik tipi")
    content_length: Optional[int] = Field(None, description="İçerik uzunluğu")
    page_title: Optional[str] = Field(None, description="Sayfa başlığı")
    extracted_text: Optional[str] = Field(None, description="Temizlenmiş metin")
    raw_html: Optional[str] = Field(None, description="Ham HTML içeriği")
    raw_content: Optional[bytes] = Field(
        None,
        description="İndirilen ham içerik; özellikle PDF ayrıştırması için kullanılır",
        exclude=True,
    )
    is_pdf: bool = Field(False, description="PDF mi?")


# ──────────────── Tekil aday değerlendirme sonucu ────────────────

class CandidateResult(BaseModel):
    """Tek bir aday URL'nin iki bağımsız Gemini doğrulaması dahil değerlendirme sonucu."""

    candidate: CandidateURL
    rule_passed: bool = Field(False, description="Kurallı doğrulamayı geçti mi?")
    rule_details: dict[str, bool] = Field(default_factory=dict)
    rule_evidence: list[str] = Field(
        default_factory=list, description="Kodla sayfa metninden çıkarılan kanıt kesitleri"
    )
    content_year: Optional[int] = Field(None, description="Kodla tespit edilen en güncel içerik yılı")
    scope: str = Field("unknown", description="institution | program | mixed | unknown")

    # Çift Gemini doğrulama birleşik sonucu
    dual_validation: Optional[DualValidationResult] = None

    score: Optional[ScoreBreakdown] = None
    decision: DecisionType = Field(DecisionType.REJECTED)
    rejection_reason: Optional[str] = None
    manually_approved: bool = Field(
        False,
        description="URL, Manuel Kontrol ekranında kullanıcı tarafından açıkça onaylandı mı?",
    )


# ──────────────── Denetim kaydı modeli ────────────────

class AuditRecord(BaseModel):
    """Her araştırma sonucu için ayrı denetim kaydı."""

    university_name: str = ""
    university_id: Optional[str] = None
    target_type: str = ""
    selected_url: Optional[str] = None
    http_status: Optional[int] = None
    final_score: int = 0

    gemini_pass1_decision: Optional[dict] = None
    gemini_pass2_decision: Optional[dict] = None
    verified_evidence: list[str] = Field(default_factory=list)

    alternatives: list[dict] = Field(default_factory=list)

    decision: str = "not_found"
    decision_reason: str = ""
    checked_at: Optional[str] = None


# ──────────────── Üniversite araştırma sonucu ────────────────

class UniversityResearchResult(BaseModel):
    """Bir üniversite için tüm kategorilerdeki araştırma sonucu."""

    row_number: int
    university_name: str
    university_id: Optional[str] = None

    # Kategori bazında en iyi sonuçlar
    best_results: dict[ResearchCategory, Optional[CandidateResult]] = Field(
        default_factory=dict
    )

    # Tüm adaylar (denetim raporu için)
    all_candidates: dict[ResearchCategory, list[CandidateResult]] = Field(
        default_factory=dict
    )

    # Denetim kayıtları
    audit_records: dict[ResearchCategory, AuditRecord] = Field(
        default_factory=dict
    )

    # Genel durum
    status: RowStatus = Field(RowStatus.PENDING)
    notes: list[str] = Field(default_factory=list)

    # Zaman damgası
    processed_at: Optional[datetime] = None

    def determine_status(self) -> RowStatus:
        """Sonuçlara göre genel durumu belirle."""
        if not self.best_results:
            # NOT_FOUND yalnızca kurumun gerçekten kapalı/sitesiz olduğu ayrıca
            # doğrulanmış ve açıkça atanmışsa korunur.
            if self.status in {RowStatus.COMPLETED, RowStatus.NOT_FOUND}:
                return self.status
            return RowStatus.MANUAL_REVIEW

        if all(
            result is not None and result.decision == DecisionType.ACCEPTED
            for result in self.best_results.values()
        ):
            return RowStatus.COMPLETED

        # Erişememe, aday bulamama veya doğrulama başarısızlığı kurumun web
        # sitesinin yok olduğunu kanıtlamaz.
        return RowStatus.MANUAL_REVIEW


# ──────────────── Pipeline ilerleme modeli ────────────────

class PipelineProgress(BaseModel):
    """İşlem hattı ilerleme bilgisi (arayüz için)."""

    total_universities: int = 0
    processed_universities: int = 0
    total_missing_fields: int = 0
    found_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    manual_review_count: int = 0
    current_university: Optional[str] = None
    is_running: bool = False
    is_cancelled: bool = False
