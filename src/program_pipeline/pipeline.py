"""Ana program pipeline v3 — tüm kalite bileşenlerini ve QA kontrolünü birleştirir.

İş akışı (her üniversite için):
1. Checkpoint & Schema sürüm kontrolü
2. Kaynak Excel'den URL'leri al
3. Genel politika URL'lerinden alanları çıkar
4. Doğrulanmış Program Manifesti oluştur
5. Taksonomiye göre yalnızca PROGRAM_DETAIL sayfalarını işle
6. Sınırlı kapsamda alanları çıkar ve kanıt doğrula
7. Export öncesi QA raporu üret
8. Yalnızca QA'den geçen kayıtları Excel'e yaz
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urljoin

from src.config import get_settings
from src.domain_utils import extract_domain, is_safe_url, is_official_domain
from src.fetch.page_fetcher import PageFetcher
from src.program_pipeline.checkpoint import CheckpointManager, PageCache, PIPELINE_SCHEMA_VERSION
from src.program_pipeline.confidence import classify_confidence, adjust_confidence
from src.program_pipeline.content_sections import extract_html_sections, extract_pdf_sections
from src.program_pipeline.evidence_validator import validate_all_fields
from src.program_pipeline.excel_writer import write_programs_to_excel, get_output_filename
from src.program_pipeline.field_merger import merge_all_fields, enrich_fields_with_derived_policies
from src.program_pipeline.general_policy_extractor import GeneralPolicyExtractor
from src.program_pipeline.models import (
    ExtractedField, MatchResult, ProgramRecord, ProgramPipelineResult,
    SourceUniversityRow, TemplateInfo,
)
from src.program_pipeline.program_discovery import (
    discover_program_pages, fetch_and_discover_programs,
)
from src.program_pipeline.program_extractor import ProgramExtractor
from src.program_pipeline.program_quality import (
    assess_program_page,
    detect_program_name,
    is_junk_program_name,
)
from src.program_pipeline.program_manifest import (
    ProgramManifest, ProgramCandidate, get_canonical_program_name,
    normalize_degree_level, extract_subject_from_name,
)
from src.program_pipeline.taxonomy import classify_page_taxonomy, PageTaxonomy
from src.program_pipeline.policy_scope import is_policy_compatible_with_program
from src.program_pipeline.tuition_matcher import format_tuition_value
from src.program_pipeline.qa_exporter import evaluate_qa_report, save_qa_report
from src.audit.evidence_store import EvidenceStore
from src.audit.review_queue import ReviewQueue
from src.models import ResearchCategory

logger = logging.getLogger(__name__)

_URL_TYPE_MAP = {
    "program_url": "program",
    "admission_url": "admission",
    "language_url": "language",
    "tuition_url": "tuition",
}


class ProgramPipeline:
    """Program veri doldurma pipeline orkestratörü v3."""

    def __init__(
        self,
        confidence_threshold: float = 0.85,
        resume: bool = True,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.resume = resume
        self.progress_callback = progress_callback
        self.fetcher = PageFetcher()
        self.general_extractor = GeneralPolicyExtractor()
        self.program_extractor = ProgramExtractor()
        settings = get_settings()
        self.cache = PageCache(settings.data_cache_dir)
        self.checkpoint = CheckpointManager(settings.checkpoint_dir)
        self._log_lines: list[str] = []

    def _log(self, msg: str, *args) -> None:
        text = msg % args if args else msg
        logger.info(text)
        self._log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    def _notify(self, uni_done: int, uni_total: int, prog_done: int, prog_total: int,
                uni_name: str = "") -> None:
        if self.progress_callback:
            try:
                self.progress_callback({
                    "uni_done": uni_done,
                    "uni_total": uni_total,
                    "prog_done": prog_done,
                    "prog_total": prog_total,
                    "uni_name": uni_name,
                    "log": self._log_lines[-1] if self._log_lines else "",
                })
            except Exception:
                pass

    async def run(
        self,
        source_rows: list[SourceUniversityRow],
        template_info: TemplateInfo,
        matches: list[MatchResult],
        template_path: Path | str,
        output_dir: Path | str,
    ) -> ProgramPipelineResult:
        """Pipeline'ı çalıştır."""
        settings = get_settings()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        audit = EvidenceStore(settings.audit_dir)
        review_q = ReviewQueue(settings.audit_dir / "review_queue.jsonl")
        output_path = get_output_filename(template_path, output_dir)

        all_programs: list[ProgramRecord] = []
        rejected_candidates_summary: list[dict] = []
        stats = {
            "total_programs": 0,
            "cells_written": 0,
            "cells_empty": 0,
            "needs_review": 0,
            "errors": [],
        }

        matched_rows = [
            m.source_row for m in matches
            if m.match_type not in ("needs_manual", "no_match")
        ]
        uni_total = len(matched_rows)

        for uni_idx, row in enumerate(matched_rows):
            uni_name = row.university_name
            self._log("İşleniyor: %s (%d/%d) [Schema: %s]", uni_name, uni_idx + 1, uni_total, PIPELINE_SCHEMA_VERSION)
            self._notify(uni_idx, uni_total, 0, 1, uni_name)

            if self.resume and self.checkpoint.is_completed(uni_name):
                self._log("Checkpoint bulundu (%s); cache üzerinden yeniden doğrulanıyor.", uni_name)

            try:
                programs, uni_stats, rej_list = await self._process_university(
                    row=row,
                    template_info=template_info,
                    audit=audit,
                    review_q=review_q,
                    uni_idx=uni_idx,
                    uni_total=uni_total,
                )
                all_programs.extend(programs)
                rejected_candidates_summary.extend(rej_list)
                stats["total_programs"] += len(programs)
                stats["cells_written"] += uni_stats["written"]
                stats["cells_empty"] += uni_stats["empty"]
                stats["needs_review"] += uni_stats["review"]

                if programs:
                    self.checkpoint.mark_completed(
                        uni_name,
                        program_count=len(programs),
                        output_path=str(output_path),
                    )
                else:
                    self._log("⚠️ %s: Hiç program verisi çıkarılamadı.", uni_name)

            except Exception as e:
                self._log("HATA: %s → %s", uni_name, e)
                self.checkpoint.mark_failed(uni_name, str(e))
                stats["errors"].append({"university": uni_name, "error": str(e)})
                logger.exception("Üniversite işleme hatası: %s", uni_name)

        # QA Değerlendirmesi
        qa_report = evaluate_qa_report(
            programs=all_programs,
            total_unis=uni_total,
            rejected_candidates=rejected_candidates_summary,
        )
        qa_json_path = output_dir / "qa_report.json"
        save_qa_report(qa_report, qa_json_path)

        if not qa_report.passed_qa:
            self._log("⚠️ QA KONTROLÜ BAŞARISIZ! Nedenler: %s", "; ".join(qa_report.failure_reasons))
            self._log("⛔ Kural ihlali olduğu için Excel dosyasına YAZILMADI.")
        elif all_programs:
            self._log("Excel yazılıyor: %d program", len(all_programs))
            try:
                write_programs_to_excel(
                    programs=all_programs,
                    template_path=template_path,
                    output_path=output_path,
                    template_info=template_info,
                    confidence_threshold=self.confidence_threshold,
                )
                self._log("Excel yazıldı: %s", output_path.name)
            except Exception as e:
                self._log("Excel yazma hatası: %s", e)
                stats["errors"].append({"stage": "excel_write", "error": str(e)})

        audit.close()

        return ProgramPipelineResult(
            total_programs=stats["total_programs"],
            cells_written=stats["cells_written"],
            cells_empty=stats["cells_empty"],
            needs_review_count=stats["needs_review"],
            output_path=str(output_path) if output_path.exists() else None,
            audit_path=audit.path,
            review_queue_path=review_q.path,
            errors=stats["errors"],
        )

    async def _process_university(
        self,
        row: SourceUniversityRow,
        template_info: TemplateInfo,
        audit: EvidenceStore,
        review_q: ReviewQueue,
        uni_idx: int = 0,
        uni_total: int = 1,
    ) -> tuple[list[ProgramRecord], dict, list[dict]]:
        """Tek bir üniversiteyi işle."""
        domain_set = set()
        for site_url in [row.official_website, row.program_url, row.admission_url, row.language_url, row.tuition_url]:
            if site_url and is_safe_url(site_url):
                d = extract_domain(site_url)
                if d:
                    domain_set.add(d)

        official_domain = list(domain_set)[0] if domain_set else extract_domain(row.official_website or "")
        page_texts: dict[str, str] = {}
        catalog_sections: list[tuple[str, list]] = []
        catalog_urls: list[str] = []
        stats = {"written": 0, "empty": 0, "review": 0}
        rejected_candidates: list[dict] = []

        manifest = ProgramManifest(row.university_id or "", row.university_name)
        general_fields: dict[str, ExtractedField] = {}

        url_fields = {
            "admission_url": row.admission_url,
            "language_url": row.language_url,
            "tuition_url": row.tuition_url,
        }

        for url_field, url in url_fields.items():
            if not url or not is_safe_url(url):
                continue
            url_type = _URL_TYPE_MAP[url_field]
            try:
                content = await self._fetch_html(url)
                if content:
                    page_texts[url] = ""
                    is_pdf = url.lower().split("?", 1)[0].endswith(".pdf") or content.startswith(b"%PDF")
                    sections = (
                        extract_pdf_sections(content, url)
                        if is_pdf else extract_html_sections(content, url)
                    )
                    for s in sections:
                        page_texts[url] += f"{s.heading or ''} {s.text} "
                    fields = (
                        self.general_extractor.extract_from_pdf(content, url, url_type)
                        if is_pdf else
                        self.general_extractor.extract_from_html(content, url, url_type)
                    )
                    for name, field in fields.items():
                        if name not in general_fields or field.confidence > general_fields[name].confidence:
                            general_fields[name] = field
            except Exception as e:
                self._log("Genel politika çekme hatası (%s): %s", url, e)

        # 2. Program sayfalarını keşfet
        self._log("%s: Program sayfaları keşfediliyor...", row.university_name)
        program_urls: list[str] = []

        if row.program_url and is_safe_url(row.program_url):
            try:
                program_urls.extend(await fetch_and_discover_programs(
                    row.program_url, self.fetcher, official_domain
                ))
            except Exception as e:
                logger.debug("Alt program URL çıkarma hatası: %s", e)

        try:
            discovered = await discover_program_pages(
                official_domain=official_domain,
                known_program_url=row.program_url,
                university_name=row.university_name,
                fetcher=self.fetcher,
                max_pages=40,
                max_depth=2,
            )
            for url in discovered:
                if url not in program_urls:
                    program_urls.append(url)
        except Exception as e:
            self._log("Program keşif hatası (%s): %s", row.university_name, e)

        settings = get_settings()
        sem = asyncio.Semaphore(settings.program_domain_concurrency)
        programs: list[ProgramRecord] = []

        prog_total = min(len(program_urls), settings.program_max_programs_per_uni)

        for prog_idx, prog_url in enumerate(program_urls[:prog_total]):
            self._notify(uni_idx, uni_total, prog_idx, prog_total, row.university_name)

            try:
                program, p_stats, candidate = await self._process_program(
                    prog_url=prog_url,
                    row=row,
                    official_domain=official_domain,
                    general_fields=general_fields,
                    page_texts=page_texts,
                    catalog_sections=catalog_sections,
                    template_info=template_info,
                    audit=audit,
                    review_q=review_q,
                    semaphore=sem,
                )
                if candidate:
                    manifest.add_candidate(candidate)
                    if not candidate.accepted:
                        rejected_candidates.append({
                            "url": prog_url,
                            "reason": candidate.rejection_reason,
                        })
                if program:
                    programs.append(program)
                    stats["written"] += p_stats["written"]
                    stats["empty"] += p_stats["empty"]
                    stats["review"] += p_stats["review"]

            except Exception as e:
                self._log("Program işleme hatası (%s): %s", prog_url, e)

        # Envanter ve Tekilleştirme
        final_programs: list[ProgramRecord] = []
        seen_keys: set[str] = set()

        for program in programs:
            raw_name = str(program.program_name.value or "")
            canonical_name = get_canonical_program_name(raw_name)
            deg_level = normalize_degree_level(canonical_name)
            subj = extract_subject_from_name(canonical_name)

            key = f"{deg_level}:{subj.lower()}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Ücret formatını koru
            if program.fields.get("Yıllık Ücret") and program.fields["Yıllık Ücret"].value:
                tuition_val = str(program.fields["Yıllık Ücret"].value)
                formatted = format_tuition_value(tuition_val)
                if formatted:
                    program.fields["Yıllık Ücret"].value = formatted.formatted_value

            final_programs.append(program)

        self._log("%s: %d doğrulanmış tekil program işlendi.", row.university_name, len(final_programs))
        return final_programs, stats, rejected_candidates

    async def _process_program(
        self,
        prog_url: str,
        row: SourceUniversityRow,
        official_domain: str,
        general_fields: dict[str, ExtractedField],
        page_texts: dict[str, str],
        catalog_sections: list[tuple[str, list]],
        template_info: TemplateInfo,
        audit: EvidenceStore,
        review_q: ReviewQueue,
        semaphore: asyncio.Semaphore,
    ) -> tuple[Optional[ProgramRecord], dict, Optional[ProgramCandidate]]:
        """Tek bir program sayfasını işle."""
        async with semaphore:
            stats = {"written": 0, "empty": 0, "review": 0}

            content = await self._fetch_html(prog_url)
            if not content:
                cand = ProgramCandidate(
                    row.university_id or "", row.university_name, "", "", "", "", "",
                    prog_url, "", 0, False, "sayfa içeriği indirilemedi"
                )
                return None, stats, cand

            is_pdf = prog_url.lower().split("?", 1)[0].endswith(".pdf") or content.startswith(b"%PDF")
            sections = (
                extract_pdf_sections(content, prog_url)
                if is_pdf else extract_html_sections(content, prog_url)
            )
            page_text = " ".join(f"{s.heading or ''} {s.text}" for s in sections)
            page_texts[prog_url] = page_text

            page_type = classify_page_taxonomy(prog_url, is_pdf=is_pdf)
            if page_type != PageTaxonomy.PROGRAM_DETAIL:
                cand = ProgramCandidate(
                    row.university_id or "", row.university_name, "", "", "", "", "",
                    prog_url, "", 0, False, f"taksonomi reddi ({page_type.value})"
                )
                return None, stats, cand

            program_name = detect_program_name(sections, prog_url)
            assessment = assess_program_page(prog_url, sections, program_name)

            if not assessment.accepted or not assessment.program_name or is_junk_program_name(assessment.program_name):
                reason = ", ".join(assessment.reasons) or "sert program kimliği doğrulanamadı"
                cand = ProgramCandidate(
                    row.university_id or "", row.university_name, assessment.program_name or "",
                    "", "", "", "", prog_url, "", assessment.score, False, reason
                )
                return None, stats, cand

            program_name = assessment.program_name
            canonical_name = get_canonical_program_name(program_name)
            deg_level = normalize_degree_level(canonical_name)
            subject = extract_subject_from_name(canonical_name)

            cand = ProgramCandidate(
                row.university_id or "", row.university_name, canonical_name,
                deg_level, subject, "", "standard", prog_url, program_name, assessment.score, True
            )

            prog_fields = self.program_extractor.extract(sections, canonical_name, prog_url, url_type="program")
            merged = merge_all_fields(prog_fields, general_fields)
            merged = enrich_fields_with_derived_policies(
                merged,
                row=row,
                prog_url=prog_url,
                canonical_name=canonical_name,
                deg_level=deg_level,
                subject=subject,
                official_domain=official_domain,
            )
            validation = validate_all_fields(merged, page_texts, official_domain, self.confidence_threshold)

            final_fields: dict[str, ExtractedField] = {}

            for field_name, field in merged.items():
                is_valid, reason = validation.get(field_name, (False, ""))

                if field.value is None:
                    audit.record(
                        row.university_id or "", row.university_name,
                        canonical_name, field_name, field, "empty"
                    )
                    stats["empty"] += 1
                    final_fields[field_name] = ExtractedField()
                    continue

                # Kapsam denetimi
                if field.scope and not is_policy_compatible_with_program(field.scope, deg_level):
                    final_fields[field_name] = ExtractedField()
                    stats["empty"] += 1
                    continue

                adj = adjust_confidence(
                    field=field,
                    is_official_domain=is_valid,
                    domain_validated=True,
                    evidence_verified=is_valid,
                    is_recent_content=not field.is_historical,
                    is_program_scope=(field.scope == "program"),
                )

                decision = classify_confidence(adj, self.confidence_threshold)

                if decision == "auto_write":
                    final_fields[field_name] = adj
                    stats["written"] += 1
                    audit.record(
                        row.university_id or "", row.university_name,
                        canonical_name, field_name, adj, "written"
                    )
                elif decision == "needs_review":
                    final_fields[field_name] = ExtractedField()
                    review_q.add_field(
                        row.university_id or "", row.university_name,
                        canonical_name, field_name, adj
                    )
                    stats["review"] += 1
                    audit.record(
                        row.university_id or "", row.university_name,
                        canonical_name, field_name, adj, "review_queue"
                    )
                else:
                    final_fields[field_name] = ExtractedField()
                    stats["empty"] += 1
                    audit.record(
                        row.university_id or "", row.university_name,
                        canonical_name, field_name, field, "skipped_low_confidence"
                    )

            program = ProgramRecord(
                university_id=row.university_id or "",
                university_name=row.university_name,
                program_name=ExtractedField(
                    value=canonical_name,
                    source_url=prog_url,
                    evidence=canonical_name,
                    source_type="program_page",
                    scope="program",
                    confidence=1.0,
                    is_explicit=True,
                ),
                fields=final_fields,
                program_url=prog_url,
                status="accepted",
            )

            return program, stats, cand

    async def _fetch_html(self, url: str) -> Optional[bytes]:
        """URL'den HTML içeriği getir (cache kontrolü ile)."""
        is_pdf_url = url.lower().split("?", 1)[0].endswith(".pdf")
        cached = self.cache.get_pdf(url) if is_pdf_url else self.cache.get_html(url)
        if cached:
            return cached

        try:
            result = await self.fetcher.fetch_candidate(url, ResearchCategory.PROGRAM)
            if result:
                raw_val = (
                    getattr(result, "raw_content", None)
                    or getattr(result, "raw_html", None)
                    or getattr(result, "extracted_text", None)
                )
                if raw_val:
                    html_bytes = raw_val.encode("utf-8") if isinstance(raw_val, str) else raw_val
                    if getattr(result, "is_pdf", False) or html_bytes.startswith(b"%PDF"):
                        self.cache.set_pdf(url, html_bytes)
                    else:
                        self.cache.set_html(url, html_bytes)
                    return html_bytes
        except Exception as e:
            logger.debug("HTML fetch hatası (%s): %s", url, e)

        return None
