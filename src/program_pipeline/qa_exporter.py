"""Export Öncesi Kalite Kontrolü (QA) ve Raporlama Motoru.

Excel yazılmadan önce kalite raporunu üretir ve sert kurallara uyulmadığında
export işlemini durdurur.

8 Kalite Kuralı Kontrolü:
1. Yüksek doluluk — kritik alanlar için doluluk oranı ölçülür
2. Yalnızca gerçek+doğrulanmış programlar — junk_count ve dup_count
3. Resmî kaynaklar — official_source_ratio
4. Kapsama uygun bilgiler — scope validation (pipeline'da yapılır)
5. Kaynak yorumları — Kabul Verisi Kaynağı doluluk oranı
6. Tekilleştirme + çöp filtresi — dup_count, junk_count
7. Uydurma yok — fake_derived_count
8. Görsel QA — fill_rates_by_field dict
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.program_pipeline.models import ProgramRecord
from src.program_pipeline.program_quality import is_junk_program_name

logger = logging.getLogger(__name__)

# Sabit/uydurulmuş derived_policy metinleri — bunlar sahte veri sayılır
_FAKE_DERIVED_TEXTS = {
    "çevrimiçi başvuru",
    "resmî kabul sayfası başvuru belgelerini ve şartlarını açıkça listeler",
    "lise diploması veya eşdeğeri ged; başvuru koşullarına uyum",
    "akredite kurumdan lisans diploması; akademik ve mesleki yeterlilik",
    "çevrimiçi başvuru; resmî lise transkripti veya ged; kimlik belgesi",
    "çevrimiçi başvuru; lisans transkripti; özgeçmiş; kişisel beyan/referanslar",
    "2026–2028 katalog / güncel ücret sayfası",
    "evet (veya ücretten muafiyet başvurusu)",
}

# Doluluk oranı izlenecek kritik alanlar
_CRITICAL_FIELDS = [
    "Eğitim Süresi",
    "Yıllık Ücret",
    "Minimum GPA",
    "Minimum IELTS",
    "Minimum TOEFL",
    "Essay Gerekli Mi",
    "Mülakat Gerekli Mi",
    "Kabul Verisi Kaynağı",
    "Başvuru Belgeleri",
    "Zorunlu Başvuru Maddeleri",
    "Başvuru Dönemi",
    "Son Başvuru Metni",
    "İngilizce Yeterlilik Gerekli Mi",
    "Standart Test Politikası",
    "Transkript/GED Gereksinimi",
    "Fakülte",
    "Eğitim Dili",
]


@dataclass
class QAReport:
    total_universities: int
    programs_per_university: dict[str, int]
    rejected_candidates_count: int
    rejection_reasons: dict[str, int]
    duplicate_count: int
    junk_program_names_count: int
    official_program_source_ratio: float
    name_and_url_only_count: int
    duration_fill_rate: float
    tuition_fill_rate: float
    admission_fill_rate: float
    language_fill_rate: float
    historical_source_count: int
    # Kural 7: Uydurma sayısı
    fake_derived_count: int
    # Kural 8: Alan bazlı doluluk oranı
    fill_rates_by_field: dict[str, float] = field(default_factory=dict)
    # Kaynak URL'si olmayan alan sayısı
    empty_source_url_count: int = 0
    passed_qa: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    warning_reasons: list[str] = field(default_factory=list)


def _is_fake_derived(fval: ExtractedField | None) -> bool:
    """Alan değeri uydurulmuş sabit metin mi?

    Yalnızca kural tabanlı derived_policy ile üretilmiş ve açık kanıtı olmayan
    sabit metinler sahte türetilmiş veri kabul edilir. Web sayfasından çekilen
    gerçek metinler sahte sayılmaz.
    """
    if not fval or fval.value is None:
        return False
    if fval.source_type != "derived_policy":
        return False
    v = str(fval.value).strip().lower()
    return v in _FAKE_DERIVED_TEXTS


def evaluate_qa_report(
    programs: list[ProgramRecord],
    total_unis: int,
    rejected_candidates: list[dict] | None = None,
) -> QAReport:
    """Excel çıktısı öncesi kalite değerlendirmesi yapar."""
    rejected_candidates = rejected_candidates or []
    programs_per_uni: dict[str, int] = {}
    junk_count = 0
    dup_set: set[str] = set()
    dup_count = 0
    official_sources_count = 0
    name_url_only_count = 0
    fake_derived_count = 0
    empty_source_url_count = 0

    duration_filled = 0
    tuition_filled = 0
    admission_filled = 0
    language_filled = 0
    historical_count = 0
    forbidden_text_found = False

    # Alan bazlı doluluk sayaçları
    field_filled: dict[str, int] = {f: 0 for f in _CRITICAL_FIELDS}

    failure_reasons: list[str] = []

    for prog in programs:
        uni = prog.university_name
        programs_per_uni[uni] = programs_per_uni.get(uni, 0) + 1

        name = str(prog.program_name.value or "")
        if is_junk_program_name(name):
            junk_count += 1

        key = f"{uni}:{name.lower()}"
        if key in dup_set:
            dup_count += 1
        dup_set.add(key)

        if prog.program_url and prog.program_name.source_url:
            official_sources_count += 1

        non_empty_fields = [
            k for k, v in prog.fields.items()
            if v.value is not None and str(v.value).strip() != ""
        ]
        if len(non_empty_fields) == 0:
            name_url_only_count += 1

        # Alan bazlı doluluk
        for fname in _CRITICAL_FIELDS:
            fval = prog.fields.get(fname)
            if fval and fval.value is not None and str(fval.value).strip():
                field_filled[fname] += 1

        # Kural 1: Kritik alanlar
        if prog.fields.get("Eğitim Süresi") and prog.fields["Eğitim Süresi"].value:
            duration_filled += 1
        if prog.fields.get("Yıllık Ücret") and prog.fields["Yıllık Ücret"].value:
            tuition_filled += 1
        if prog.fields.get("Minimum GPA") and prog.fields["Minimum GPA"].value:
            admission_filled += 1
        if (
            (prog.fields.get("Minimum IELTS") and prog.fields["Minimum IELTS"].value)
            or (prog.fields.get("Minimum TOEFL") and prog.fields["Minimum TOEFL"].value)
        ):
            language_filled += 1

        for fname, fval in prog.fields.items():
            # Kural 4: Tarihsel kaynak sayısı
            if fval.is_historical:
                historical_count += 1

            # Kural 7: Yasaklı boş metin
            if fval.value and str(fval.value).lower() in ("null", "n/a", "not found", "unknown"):
                forbidden_text_found = True

            # Kural 7: Uydurulmuş sabit metin
            if _is_fake_derived(fval):
                fake_derived_count += 1
                logger.debug("Sahte türetilmiş alan: %s = %s", fname, fval.value)

            # Kural 5: Kaynak URL'si olmayan alan
            if fval.value is not None and not fval.source_url:
                empty_source_url_count += 1

    total_progs = len(programs) or 1
    official_ratio = official_sources_count / total_progs

    # Alan bazlı doluluk oranları
    fill_rates = {fname: field_filled[fname] / total_progs for fname in _CRITICAL_FIELDS}

    rej_reasons_map: dict[str, int] = {}
    for r in rejected_candidates:
        reason = r.get("reason", "bilinmeyen")
        rej_reasons_map[reason] = rej_reasons_map.get(reason, 0) + 1

    warning_reasons: list[str] = []

    # ── QA Sert Kurallar (Excel engelleme nedenleri) ───────────────
    if junk_count > 0:
        failure_reasons.append(f"[Kural 6] Çöp program adı: {junk_count} adet")

    if dup_count > 0:
        failure_reasons.append(f"[Kural 6] Yinelenen program: {dup_count} adet")

    if official_ratio < 0.90:
        failure_reasons.append(
            f"[Kural 3] Resmî kaynağı doğrulanmamış satır var (oran: {official_ratio:.2f})"
        )

    if forbidden_text_found:
        failure_reasons.append(
            "[Kural 7] Hücrelerde yasaklı metin (null, N/A, not found, unknown) bulundu"
        )

    if fake_derived_count > 0:
        failure_reasons.append(
            f"[Kural 7] Uydurulmuş sabit metin tespit edildi: {fake_derived_count} hücre"
        )

    # ── Bilgilendirme Uyarıları (Excel engellemez) ───────────────────
    low_fill_warnings = [
        f"{fname} doluluk: %{fill_rates[fname]*100:.0f}"
        for fname in ["Eğitim Süresi", "Minimum GPA"]
        if fill_rates.get(fname, 0) < 0.30
    ]
    if low_fill_warnings:
        warning_reasons.append(
            f"[Kural 1] Düşük doluluk oranı: {'; '.join(low_fill_warnings)}"
        )

    passed = len(failure_reasons) == 0

    return QAReport(
        total_universities=total_unis,
        programs_per_university=programs_per_uni,
        rejected_candidates_count=len(rejected_candidates),
        rejection_reasons=rej_reasons_map,
        duplicate_count=dup_count,
        junk_program_names_count=junk_count,
        official_program_source_ratio=official_ratio,
        name_and_url_only_count=name_url_only_count,
        duration_fill_rate=duration_filled / total_progs,
        tuition_fill_rate=tuition_filled / total_progs,
        admission_fill_rate=admission_filled / total_progs,
        language_fill_rate=language_filled / total_progs,
        historical_source_count=historical_count,
        fake_derived_count=fake_derived_count,
        fill_rates_by_field=fill_rates,
        empty_source_url_count=empty_source_url_count,
        passed_qa=passed,
        failure_reasons=failure_reasons,
        warning_reasons=warning_reasons,
    )


def save_qa_report(report: QAReport, output_path: Path | str) -> None:
    """QA Raporunu JSON dosyasına yazar."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    logger.info("QA raporu yazıldı: %s", path)
