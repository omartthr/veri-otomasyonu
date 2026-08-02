"""Ana araştırma işlem hattı — üniversite veri otomasyonu.

Her üniversite için eksik alanları araştırır, aday sayfaları indirir,
kural tabanlı doğrulamadan geçirir, denetim kaydı oluşturur ve sonuçları toplar.

Yalnızca kural tabanlı, deterministik, API anahtarı gerektirmez.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from src.config import get_settings
from src.domain_utils import extract_domain
from src.fetch.page_fetcher import PageFetcher
from src.models import (
    AuditRecord,
    CandidateResult,
    DecisionType,
    PipelineProgress,
    ResearchCategory,
    RowStatus,
    UniversityResearchResult,
    UniversityRow,
)
from src.search.gemini_search import SourceSearcher
from src.validation.rule_based_validator import evaluate_rule_based_candidate

logger = logging.getLogger(__name__)

_CATEGORY_NOTE_NAMES: dict[ResearchCategory, str] = {
    ResearchCategory.PROGRAM: "Program listesi",
    ResearchCategory.ADMISSION: "Kabul şartları",
    ResearchCategory.LANGUAGE: "Dil şartları",
    ResearchCategory.TUITION: "Ücret bilgisi",
}


def _build_missing_source_note(categories: list[ResearchCategory]) -> list[str]:
    """Eksik kalan alanlar için tek ve kısa kullanıcı notu üret."""
    if not categories:
        return []
    names = [_CATEGORY_NOTE_NAMES[category] for category in categories]
    if len(names) == 1:
        subject = names[0]
    else:
        subject = ", ".join(names[:-1]) + f" ve {names[-1]}"
    return [
        f"{subject} için doğrudan ve doğrulanabilir resmî kaynak bulunamadı."
    ]


class ResearchPipeline:
    """Anahtarsız kural motoru tabanlı araştırma hattı."""

    def __init__(
        self,
        gemini_provider=None,  # geriye dönük uyumluluk için — kullanılmıyor
        progress_callback: Optional[Callable[[PipelineProgress], None]] = None,
        use_ai: bool = False,  # artık dikkate alınmıyor, yalnızca kural motoru
    ):
        self.progress_callback = progress_callback
        self.fetcher = PageFetcher()
        self.searcher = SourceSearcher()
        self.progress = PipelineProgress()
        self._cancelled = False

    def cancel(self) -> None:
        """İşlemi iptal et."""
        self._cancelled = True
        self.progress.is_cancelled = True

    def _notify_progress(self) -> None:
        """Arayüze ilerleme bilgisini bildir."""
        if self.progress_callback:
            try:
                self.progress_callback(self.progress)
            except Exception as e:
                logger.warning(f"İlerleme geri çağırım hatası: {e}")

    async def run(
        self,
        rows: list[UniversityRow],
        auto_verify_manual_with_bot: bool = False,
    ) -> list[UniversityResearchResult]:
        """Tüm üniversiteleri araştır ve doğrula."""
        self.progress.total_universities = len(rows)
        self.progress.total_missing_fields = sum(
            len(r.get_missing_categories()) for r in rows
        )
        self.progress.is_running = True
        self.progress.processed_universities = 0
        self._notify_progress()

        settings = get_settings()
        concurrency = max(1, settings.max_concurrency)
        semaphore = asyncio.Semaphore(concurrency)

        async def process_row(row: UniversityRow) -> Optional[UniversityResearchResult]:
            async with semaphore:
                if self._cancelled:
                    return None
                self.progress.current_university = row.university_name
                self._notify_progress()
                logger.info("Kurum araştırması başladı: %s", row.university_name)
                result = await self._process_single_university(row)
                self.progress.processed_universities += 1
                self._notify_progress()
                logger.info(
                    "Kurum araştırması tamamlandı: %s | durum=%s | ilerleme=%d/%d",
                    row.university_name,
                    result.status.value,
                    self.progress.processed_universities,
                    self.progress.total_universities,
                )
                return result

        gathered = await asyncio.gather(*(process_row(row) for row in rows))
        results = [result for result in gathered if result is not None]

        if auto_verify_manual_with_bot:
            logger.info("Post-scan Bot Manuel Kontrol ikincil doğrulaması başlatılıyor...")
            from src.manual_review import bot_verify_manual_results
            results, _ = await bot_verify_manual_results(results)

        self.progress.is_running = False
        self._notify_progress()
        return results

    async def _process_single_university(
        self,
        row: UniversityRow,
    ) -> UniversityResearchResult:
        """Tek bir üniversiteyi araştır."""
        missing_categories = row.get_missing_categories()
        official_domain = extract_domain(row.website or "")
        official_website = row.website or official_domain

        best_results: dict[ResearchCategory, Optional[CandidateResult]] = {}
        all_candidates_map: dict[ResearchCategory, list[CandidateResult]] = {}
        audit_records: dict[ResearchCategory, AuditRecord] = {}
        unresolved_categories: list[ResearchCategory] = []

        if not missing_categories:
            return UniversityResearchResult(
                row_number=row.row_number,
                university_name=row.university_name,
                university_id=row.university_id,
                best_results={},
                status=RowStatus.COMPLETED,
                notes=[],
                processed_at=datetime.now(),
            )

        for category in missing_categories:
            if self._cancelled:
                break

            cand_result, candidate_list, audit = await self._research_category(
                university_name=row.university_name,
                official_domain=official_domain,
                official_website=official_website,
                category=category,
            )

            best_results[category] = cand_result
            all_candidates_map[category] = candidate_list
            audit_records[category] = audit

            if cand_result and cand_result.decision == DecisionType.ACCEPTED:
                self.progress.accepted_count += 1
            elif cand_result and cand_result.decision == DecisionType.MANUAL_REVIEW:
                self.progress.manual_review_count += 1
                unresolved_categories.append(category)
            else:
                self.progress.rejected_count += 1
                unresolved_categories.append(category)

        res = UniversityResearchResult(
            row_number=row.row_number,
            university_name=row.university_name,
            university_id=row.university_id,
            best_results=best_results,
            all_candidates=all_candidates_map,
            audit_records=audit_records,
            notes=_build_missing_source_note(unresolved_categories),
            processed_at=datetime.now(),
        )
        res.status = res.determine_status()
        return res

    async def _research_category(
        self,
        university_name: str,
        official_domain: str,
        official_website: str,
        category: ResearchCategory,
    ) -> tuple[Optional[CandidateResult], list[CandidateResult], AuditRecord]:
        """Tek bir kategori için adayları araştır, doğrula ve en iyisini seç."""

        # 1. Aday URL'leri keşfet
        urls = await self.searcher.discover_candidates(
            university_name=university_name,
            official_domain=official_website,
            category=category,
        )

        if not urls:
            audit = AuditRecord(
                university_name=university_name,
                target_type=category.value,
                decision="not_found",
                decision_reason="Aday URL bulunamadı.",
                checked_at=datetime.now().isoformat(),
            )
            return None, [], audit

        # 2. Sayfaları indir
        fetch_semaphore = asyncio.Semaphore(
            max(1, get_settings().deep_crawl_concurrency)
        )

        async def fetch_with_limit(url: str):
            async with fetch_semaphore:
                return await self.fetcher.fetch_candidate(url, category)

        fetch_tasks = [fetch_with_limit(url) for url in urls]
        candidates = await asyncio.gather(*fetch_tasks)

        # Aynı son URL'ye yönlenen tekrarlı adayları temizle
        unique_candidates = []
        seen_final_urls: set[str] = set()
        for candidate in candidates:
            if candidate.url in seen_final_urls:
                continue
            seen_final_urls.add(candidate.url)
            unique_candidates.append(candidate)
        candidates = unique_candidates

        # 3. Kural tabanlı değerlendirme
        evaluated_candidates: list[CandidateResult] = []
        for cand in candidates:
            cand_result = evaluate_rule_based_candidate(
                candidate=cand,
                university_name=university_name,
                official_domain=official_domain,
            )
            evaluated_candidates.append(cand_result)

        # Adayları puana göre sırala (en yüksek puan ilk)
        evaluated_candidates.sort(
            key=lambda c: (c.score.total if c.score else 0),
            reverse=True,
        )

        # En iyi kabul edilen adayı seç; ikinci kez eriş
        best: Optional[CandidateResult] = None
        for cand_res in evaluated_candidates:
            if cand_res.decision == DecisionType.ACCEPTED:
                rechecked = await self.fetcher.fetch_candidate(
                    cand_res.candidate.url,
                    category,
                    source_query="final_recheck",
                )
                recheck_result = evaluate_rule_based_candidate(
                    candidate=rechecked,
                    university_name=university_name,
                    official_domain=official_domain,
                )
                if recheck_result.decision == DecisionType.ACCEPTED:
                    cand_res.candidate = recheck_result.candidate
                    cand_res.rule_details = recheck_result.rule_details
                    cand_res.rule_evidence = recheck_result.rule_evidence
                    cand_res.content_year = recheck_result.content_year
                    cand_res.scope = recheck_result.scope
                    cand_res.score = recheck_result.score
                    best = cand_res
                    break
                cand_res.decision = DecisionType.REJECTED
                cand_res.rejection_reason = (
                    f"Son erişilebilirlik/içerik kontrolü başarısız: {recheck_result.rejection_reason}"
                )

        if best is None:
            for cand_res in evaluated_candidates:
                if cand_res.decision == DecisionType.MANUAL_REVIEW:
                    best = cand_res
                    break

        if best is None and evaluated_candidates:
            best = evaluated_candidates[0]

        # Alternatif URL listesi
        alternatives = [
            {
                "url": c.candidate.url,
                "score": c.score.total if c.score else 0,
                "decision": c.decision.value,
                "reason": c.rejection_reason or "",
            }
            for c in evaluated_candidates
            if best is None or c.candidate.url != best.candidate.url
        ]

        # Denetim kaydı
        verified_ev = list(best.rule_evidence) if best else []
        audit = AuditRecord(
            university_name=university_name,
            target_type=category.value,
            selected_url=best.candidate.url if best else None,
            http_status=best.candidate.http_status if best else None,
            final_score=best.score.total if (best and best.score) else 0,
            verified_evidence=verified_ev,
            alternatives=alternatives,
            decision=best.decision.value if best else "not_found",
            decision_reason=best.rejection_reason or (
                "Kural tabanlı doğrulamayla kabul edildi"
                if best and best.decision == DecisionType.ACCEPTED else ""
            ),
            checked_at=datetime.now().isoformat(),
        )

        logger.info(
            "Kategori kararı: kurum=%s | kategori=%s | karar=%s | puan=%d | aday=%d | url=%s",
            university_name,
            category.value,
            audit.decision,
            audit.final_score,
            len(evaluated_candidates),
            audit.selected_url or "-",
        )

        return best, evaluated_candidates, audit
