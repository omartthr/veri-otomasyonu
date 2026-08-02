"""Manuel kontrol kararlarını tutarlı ve denetlenebilir biçimde uygular.

Ayrıca tarama bittikten sonra Manuel Kontrol durumunda kalan URL'leri
ücretsiz Bot motoruyla ikincil taramadan ve doğrulamadan geçirir.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from src.domain_utils import extract_domain, is_safe_url, normalize_url
from src.fetch.page_fetcher import PageFetcher
from src.models import (
    AuditRecord,
    CandidateResult,
    CandidateURL,
    DecisionType,
    ResearchCategory,
    RowStatus,
    UniversityResearchResult,
)
from src.search.gemini_search import SourceSearcher
from src.validation.rule_based_validator import evaluate_rule_based_candidate
from src.validation.rule_validator import validate_rules

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


def approve_manual_url(
    result: UniversityResearchResult,
    category: ResearchCategory,
    url: str,
) -> str:
    """Kullanıcının açık URL onayını sonuca ve denetim kaydına uygula."""
    normalized = normalize_url(url.strip())
    if not normalized or not is_safe_url(normalized):
        raise ValueError("Yalnızca geçerli bir http/https URL onaylanabilir.")

    candidate_result = result.best_results.get(category)
    if candidate_result is None:
        raise ValueError("Bu kategori için onaylanabilecek bir aday URL yok.")

    candidate_result.candidate.url = normalized
    candidate_result.decision = DecisionType.ACCEPTED
    candidate_result.manually_approved = True
    candidate_result.rejection_reason = None

    audit = result.audit_records.get(category)
    if audit is not None:
        audit.selected_url = normalized
        audit.decision = DecisionType.ACCEPTED.value
        audit.decision_reason = "Manuel Kontrol ekranında kullanıcı tarafından onaylandı."

    unresolved = [
        cat for cat, cand in result.best_results.items()
        if cand is None or cand.decision != DecisionType.ACCEPTED
    ]
    result.notes = _build_missing_source_note(unresolved)
    result.status = result.determine_status()
    return normalized


def reject_manual_url(
    result: UniversityResearchResult,
    category: ResearchCategory,
) -> None:
    """Kullanıcının açık ret kararını uygula."""
    candidate_result = result.best_results.get(category)
    if candidate_result is None:
        raise ValueError("Bu kategori için reddedilebilecek bir aday URL yok.")

    candidate_result.decision = DecisionType.REJECTED
    candidate_result.manually_approved = False
    candidate_result.rejection_reason = "Manuel Kontrol ekranında kullanıcı tarafından reddedildi."

    audit = result.audit_records.get(category)
    if audit is not None:
        audit.decision = DecisionType.REJECTED.value
        audit.decision_reason = candidate_result.rejection_reason

    unresolved = [
        cat for cat, cand in result.best_results.items()
        if cand is None or cand.decision != DecisionType.ACCEPTED
    ]
    result.notes = _build_missing_source_note(unresolved)
    result.status = result.determine_status()


async def bot_verify_manual_results(
    results: list[UniversityResearchResult],
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> tuple[list[UniversityResearchResult], dict[str, int]]:
    """Tarama bittikten sonra Manuel Kontrol durumunda kalan URL'leri
    ücretsiz Bot motoruyla (Sitemap + Site İçi + DDG + Bing) ikincil taramadan geçirir ve doğrular.

    Doğrulanan URL'lerin kararını ACCEPTED yapar ve Excel'e yazılacak hale getirir.
    Doğrulanamayanlar dürüstçe Manuel Kontrol olarak kalır.

    Args:
        results: İşlenmiş veya kısmen işlenmiş sonuç listesi
        progress_callback: İlerleme bildirimi (işlenen, toplam, üniversite_adı)

    Returns:
        Güncellenmiş sonuçlar ve istatistik sözlüğü
    """
    fetcher = PageFetcher()
    searcher = SourceSearcher(provider=None)

    manual_results = [
        res for res in results
        if res.status == RowStatus.MANUAL_REVIEW or any(
            cand is None or cand.decision != DecisionType.ACCEPTED
            for cand in res.best_results.values()
        )
    ]

    total_manual = len(manual_results)
    verified_count = 0

    for idx, result in enumerate(manual_results, 1):
        if progress_callback:
            progress_callback(idx, total_manual, result.university_name)

        university_name = result.university_name
        official_domain = ""
        for cand in result.best_results.values():
            if cand and cand.candidate and cand.candidate.url:
                official_domain = extract_domain(cand.candidate.url)
                if official_domain:
                    break

        unresolved_cats = [
            cat for cat, cand in result.best_results.items()
            if cand is None or cand.decision != DecisionType.ACCEPTED
        ]

        for category in unresolved_cats:
            candidate_urls: list[str] = []

            existing_best = result.best_results.get(category)
            if existing_best and existing_best.candidate and existing_best.candidate.url:
                candidate_urls.append(existing_best.candidate.url)

            if category in result.all_candidates:
                for c in result.all_candidates[category]:
                    if c.candidate and c.candidate.url and c.candidate.url not in candidate_urls:
                        candidate_urls.append(c.candidate.url)

            if len(candidate_urls) < 3:
                discovered = await searcher.discover_candidates(
                    university_name=university_name,
                    official_domain=official_domain or university_name.lower().replace(" ", "") + ".edu",
                    category=category,
                )
                for d in discovered:
                    if d not in candidate_urls:
                        candidate_urls.append(d)

            for url in candidate_urls:
                try:
                    cand_page = None
                    if (
                        existing_best
                        and existing_best.candidate
                        and existing_best.candidate.url == url
                        and existing_best.candidate.extracted_text
                    ):
                        cand_page = existing_best.candidate
                    else:
                        cand_page = await fetcher.fetch_candidate(url, category)

                    if not cand_page or not cand_page.extracted_text or len(cand_page.extracted_text) < 50:
                        continue

                    rule_res = evaluate_rule_based_candidate(
                        candidate=cand_page,
                        university_name=university_name,
                        official_domain=official_domain or extract_domain(url),
                    )

                    if rule_res.decision == DecisionType.ACCEPTED:
                        result.best_results[category] = rule_res
                        verified_count += 1

                        audit = result.audit_records.get(category)
                        if audit:
                            audit.selected_url = url
                            audit.decision = DecisionType.ACCEPTED.value
                            audit.decision_reason = "Bot ikincil kural taramasıyla başarıyla doğrulandı."
                            audit.final_score = rule_res.score.total if rule_res.score else 85

                        logger.info(
                            "Bot ikincil doğrulaması başarılı: %s | %s -> %s",
                            university_name, category.value, url
                        )
                        break
                except Exception as e:
                    logger.warning(
                        "Bot ikincil doğrulama hatası (%s, %s, %s): %s",
                        university_name, category.value, url, e
                    )

        still_unresolved = [
            cat for cat, cand in result.best_results.items()
            if cand is None or cand.decision != DecisionType.ACCEPTED
        ]
        result.notes = _build_missing_source_note(still_unresolved)
        result.status = result.determine_status()

    stats = {
        "checked_universities": total_manual,
        "verified_fields": verified_count,
        "remaining_manual": sum(
            1 for res in results if res.status == RowStatus.MANUAL_REVIEW
        ),
    }

    return results, stats
