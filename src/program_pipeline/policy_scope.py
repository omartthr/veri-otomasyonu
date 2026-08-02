"""Politika Kapsamı ve Genel-Program Uyumluluk Denetleyicisi.

Her çıkarılan alan için kapsam belirler ve genel politikaların programlara aktarılma kurallarını denetler.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Literal

PolicyScopeType = Literal[
    "university",
    "undergraduate",
    "graduate",
    "doctoral",
    "certificate",
    "program_family",
    "specific_program",
    "campus",
    "online",
    "historical",
]


def is_policy_compatible_with_program(
    policy_scope: str,
    program_degree_level: str,
    program_modality: str = "standard",
    program_campus: str = "",
) -> bool:
    """Genel bir politikanın hedef programa uygulanabilir olup olmadığını kontrol eder.

    Örnekler:
    - Doktora (doctoral) politikası lisans (undergraduate) programa uygulanamaz.
    - Graduate GPA lisans programa uygulanamaz.
    - Online politikası kampüs içi programa uygulanamaz.
    """
    scope = policy_scope.lower()
    level = program_degree_level.lower()
    modality = program_modality.lower()

    if scope == "university":
        return True

    if scope == "doctoral" and level != "doctoral":
        return False

    if scope == "graduate" and level not in ("graduate", "doctoral"):
        return False

    if scope == "undergraduate" and level not in ("undergraduate", "associate"):
        return False

    if scope == "online" and modality != "online":
        return False

    if scope == "campus" and modality == "online":
        return False

    return True
