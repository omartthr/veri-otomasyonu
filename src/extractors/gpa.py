"""GPA çıkarım modülü — kural tabanlı, deterministik.

Kabul şartlarındaki minimum GPA gereksinimlerini tespit eder.
Mezuniyet GPA'sını ve sürdürme GPA'sını atlar — ancak satır bazlı
ayrım yapar: Aynı bölümde hem mezuniyet hem kabul GPA'sı olabilir.
"""

from __future__ import annotations

import re
from typing import Optional

from src.program_pipeline.models import ExtractedField
from src.program_pipeline.content_sections import ContentSection

# Kabul bağlamı gösteren başlık kalıpları
_ADMISSION_HEADINGS = re.compile(
    r"(admission|application|eligibility|requirement|prerequisite|minimum qualif)",
    re.I,
)

# Mezuniyet/sürdürme bağlamı — yalnızca satır düzeyinde uygula
_GRADUATION_LINE_CONTEXT = re.compile(
    r"\b(maintain(?:ing)?|graduation\s+requirement|to\s+remain\s+enrolled|"
    r"satisfactory\s+academic\s+(?:progress|standing)|"
    r"to\s+stay\s+in\s+(?:good\s+)?standing|academic\s+probation)\b",
    re.I,
)

# GPA değeri kalıpları — öncelik sıralamasıyla
_GPA_PATTERNS = [
    # "minimum GPA of 3.0" — en güçlü
    re.compile(r"minimum\s+(?:cumulative\s+)?gpa\s+of\s+([\d]+\.[\d]+)", re.I),
    # "minimum cumulative grade point average of 2.75"
    re.compile(r"minimum\s+cumulative\s+grade\s+point\s+average\s+of\s+([\d]+\.[\d]+)", re.I),
    # "at least a 3.0 GPA"
    re.compile(r"at\s+least\s+a?\s*([\d]+\.[\d]+)\s*gpa", re.I),
    # "GPA of 3.0 or higher"
    re.compile(r"gpa\s+of\s+([\d]+\.[\d]+)\s*(?:or\s+higher|or\s+above|and\s+above)?", re.I),
    # "cumulative GPA: 3.25"
    re.compile(r"cumulative\s+(?:grade\s+point\s+average|gpa)\s*[:=]\s*([\d]+\.[\d]+)", re.I),
    # "GPA: 3.0" veya "gpa = 2.5"
    re.compile(r"\bgpa\s*[:=]\s*([\d]+\.[\d]+)", re.I),
    # "3.0 GPA"
    re.compile(r"([\d]+\.[\d]+)\s*(?:cumulative\s+)?gpa\b", re.I),
]

# Confidence skorları
_CONFIDENCE_EXPLICIT = 0.93   # "minimum GPA of X.X" gibi net ifade
_CONFIDENCE_CONTEXTUAL = 0.88  # Kabul başlığı altında
_CONFIDENCE_IMPLICIT = 0.80   # Bağlamsal tahmin

# GPA aralığı — kabul GPA'sı genelde 0.0–4.0
_GPA_MIN = 1.0
_GPA_MAX = 4.0


def _split_lines(text: str) -> list[str]:
    """Metni satırlara böl; çok kısa satırları atla."""
    lines = re.split(r"[\n\r]+|(?<=\.)\s{2,}", text)
    return [ln.strip() for ln in lines if len(ln.strip()) > 10]


def extract_gpa(
    sections: list[ContentSection],
    program_name: str = "",
    source_url: str = "",
) -> ExtractedField:
    """Verilen bölümlerden kabul GPA şartını çıkar.

    Mezuniyet/sürdürme bağlamı artık SADECEo satır için geçerli —
    aynı bölümdeki diğer satırlarda kabul GPA'sı aranmaya devam eder.

    Args:
        sections: İçerik bölümleri (HTML veya PDF)
        program_name: Program adı (bağlam için)
        source_url: Kaynak URL

    Returns:
        ExtractedField (değer boşsa value=None)
    """
    best: Optional[ExtractedField] = None

    for section in sections:
        heading = (section.heading or "").lower()
        is_admission_heading = bool(_ADMISSION_HEADINGS.search(heading))

        # Program adı eşleşmesi → bonus confidence
        prog_match = (
            bool(re.search(re.escape(program_name), section.text, re.I))
            if program_name else False
        )

        # Satır bazlı tarama — her satırı bağımsız değerlendir
        lines = _split_lines(section.text)
        for line in lines:
            # Bu satır mezuniyet/sürdürme bağlamındaysa → sadece bu satırı atla
            if _GRADUATION_LINE_CONTEXT.search(line):
                continue

            line_lower = line.lower()
            # Kabul bağlamı var mı bu satırda?
            is_admission_line = bool(_ADMISSION_HEADINGS.search(line_lower))

            for pat_idx, pattern in enumerate(_GPA_PATTERNS):
                m = pattern.search(line)
                if not m:
                    continue

                try:
                    gpa_val = float(m.group(1))
                except (ValueError, IndexError):
                    continue

                # Geçerli GPA aralığı
                if not (_GPA_MIN <= gpa_val <= _GPA_MAX):
                    continue

                # Confidence hesapla
                if pat_idx <= 1:
                    # En güçlü kalıplar (minimum GPA of X)
                    confidence = _CONFIDENCE_EXPLICIT
                elif is_admission_heading or is_admission_line:
                    confidence = _CONFIDENCE_CONTEXTUAL
                else:
                    confidence = _CONFIDENCE_IMPLICIT

                if prog_match:
                    confidence = min(1.0, confidence + 0.04)

                # 50 karakter öncesi+sonrası bağlam
                combined_full = f"{section.heading or ''}\n{section.text}"
                m_full = pattern.search(combined_full)
                if m_full:
                    ctx_start = max(0, m_full.start() - 80)
                    ctx_end = min(len(combined_full), m_full.end() + 80)
                    evidence = combined_full[ctx_start:ctx_end].strip()
                else:
                    evidence = line

                candidate = ExtractedField(
                    value=gpa_val,
                    source_url=source_url,
                    evidence=evidence[:400],
                    source_type=section.source_type,
                    page_number=section.page_number,
                    scope="program" if prog_match else "university",
                    confidence=confidence,
                    is_explicit=(is_admission_heading or is_admission_line or pat_idx <= 1),
                )

                if best is None or candidate.confidence > best.confidence:
                    best = candidate
                break  # Bu satır için en iyi kalıbı bulduk

    return best or ExtractedField()
