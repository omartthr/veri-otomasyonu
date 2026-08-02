"""Üniversite eşleştirme modülü.

İki Excel arasındaki üniversiteleri şu öncelik sırasına göre eşleştirir:
  1. Üniversite ID tam eşleşmesi
  2. Normalize edilmiş üniversite adı
  3. Doğrulanmış resmî domain
  4. Benzer isim (yalnızca yüksek güven - 0.85+)

Birden fazla aday varsa needs_manual olarak işaretler.
Fuzzy match tek başına otomatik eşleşme için yeterli değildir.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.domain_utils import extract_domain
from src.program_pipeline.models import MatchResult, SourceUniversityRow
from src.program_pipeline.normalizer import (
    normalize_for_comparison,
    normalize_university_id,
    similarity_score,
)

logger = logging.getLogger(__name__)

_FUZZY_AUTO_THRESHOLD = 0.85  # Bu eşiğin altında tek aday bile otomatik eşleşemez


def match_universities(
    source_rows: list[SourceUniversityRow],
    template_university_names: list[str] | TemplateInfo,
) -> list[MatchResult]:
    """Kaynak Excel'deki üniversiteleri template'tekilerle eşleştir."""
    if hasattr(template_university_names, "university_names"):
        names_list = template_university_names.university_names
    elif isinstance(template_university_names, list):
        names_list = template_university_names
    else:
        names_list = []

    # Template üniversitelerini normalize et
    norm_template: list[tuple[str, str]] = [
        (normalize_for_comparison(str(name)), str(name))
        for name in names_list
    ]

    results: list[MatchResult] = []

    for row in source_rows:
        match = _match_single(row, norm_template)
        results.append(match)
        logger.debug(
            "Eşleştirme: '%s' → type=%s, matched='%s', conf=%.2f",
            row.university_name,
            match.match_type,
            match.matched_name or "—",
            match.confidence,
        )

    matched = sum(1 for r in results if r.match_type not in ("needs_manual", "no_match"))
    logger.info(
        "Üniversite eşleştirmesi tamamlandı: %d kaynak, %d eşleşti, %d belirsiz, %d eşleşmedi",
        len(source_rows),
        matched,
        sum(1 for r in results if r.match_type == "needs_manual"),
        sum(1 for r in results if r.match_type == "no_match"),
    )
    return results


def _match_single(
    row: SourceUniversityRow,
    norm_template: list[tuple[str, str]],
) -> MatchResult:
    """Tek bir kaynak üniversiteyi eşleştir."""

    # ── 1. ID tam eşleşmesi ──
    if row.university_id:
        norm_id = normalize_university_id(row.university_id)
        for norm_name, original_name in norm_template:
            # Template'te ID sütunu yoksa isim içinde ID'yi ara
            if norm_id in normalize_university_id(original_name):
                return MatchResult(
                    source_row=row,
                    match_type="id",
                    matched_name=original_name,
                    confidence=1.0,
                )

    # ── 2. Normalize edilmiş ad tam eşleşmesi ──
    norm_source = normalize_for_comparison(row.university_name)
    if norm_source:
        for norm_tmpl, orig_tmpl in norm_template:
            if norm_source == norm_tmpl:
                return MatchResult(
                    source_row=row,
                    match_type="name",
                    matched_name=orig_tmpl,
                    confidence=1.0,
                )

    # ── 3. Domain eşleşmesi ──
    if row.official_website:
        source_domain = extract_domain(row.official_website)
        if source_domain:
            for norm_tmpl, orig_tmpl in norm_template:
                tmpl_domain_guess = norm_tmpl.replace(" ", "") + ".edu"
                if source_domain in orig_tmpl.lower() or source_domain in tmpl_domain_guess:
                    return MatchResult(
                        source_row=row,
                        match_type="domain",
                        matched_name=orig_tmpl,
                        confidence=0.90,
                    )

    # ── 4. Benzer isim (fuzzy) ──
    best_score = 0.0
    best_candidates: list[str] = []

    for norm_tmpl, orig_tmpl in norm_template:
        score = similarity_score(norm_source, norm_tmpl)
        if score > best_score:
            best_score = score
            best_candidates = [orig_tmpl]
        elif score == best_score and score > 0.5:
            best_candidates.append(orig_tmpl)

    if best_score >= _FUZZY_AUTO_THRESHOLD and len(best_candidates) == 1:
        return MatchResult(
            source_row=row,
            match_type="name",
            matched_name=best_candidates[0],
            confidence=best_score,
        )

    if best_score >= 0.60 and best_candidates:
        # Birden fazla aday veya düşük güven → manuel
        return MatchResult(
            source_row=row,
            match_type="needs_manual",
            matched_name=best_candidates[0] if len(best_candidates) == 1 else None,
            candidates=[row],  # Kaynak satırı candidate olarak gönder
            confidence=best_score,
        )

    return MatchResult(
        source_row=row,
        match_type="no_match",
        confidence=0.0,
    )
