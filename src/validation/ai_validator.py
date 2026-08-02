"""AI tabanlı doğrulama orkestratör modülü — DEVRE DIŞI.

Gemini bağımlılığı kaldırıldı. DualAIValidator artık doğrudan
rule_based_validator'a yönlendiriyor.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.models import (
    CandidateResult,
    CandidateURL,
    DecisionType,
)
from src.validation.rule_based_validator import evaluate_rule_based_candidate

logger = logging.getLogger(__name__)


class DualAIValidator:
    """AI Doğrulayıcısı stub — rule_based_validator'a yönlendiriyor."""

    def __init__(self, gemini_provider=None):
        # gemini_provider parametresi geriye dönük uyumluluk için var; kullanılmıyor.
        pass

    async def validate_candidate(
        self,
        candidate: CandidateURL,
        university_name: str,
        official_domain: str,
        rule_passed: bool,
        rule_details: dict,
        has_stronger_alternative: bool = False,
    ) -> CandidateResult:
        """Kural tabanlı değerlendirmeye yönlendir."""
        return evaluate_rule_based_candidate(
            candidate=candidate,
            university_name=university_name,
            official_domain=official_domain,
        )
