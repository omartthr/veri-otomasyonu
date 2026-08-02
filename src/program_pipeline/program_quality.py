"""Program sayfası ve program adı için deterministik kalite kapısı v3.

Bu modülün amacı resmî domaindeki her akademik sayfayı programa çevirmek
değil, yalnızca adı ve içeriği gerçek bir derece/sertifika programını açıkça
gösteren sayfaları kabul etmektir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from src.program_pipeline.content_sections import ContentSection


_AWARD_RE = re.compile(
    r"\b("
    r"associate(?:'s)?|bachelor(?:'s)?|master(?:'s)?|doctor(?:al|ate)?|"
    r"doctor\s+of|master\s+of|bachelor\s+of|associate\s+of|"
    r"graduate\s+(?:certificate|diploma)|postgraduate\s+(?:certificate|diploma)|"
    r"undergraduate\s+certificate|certificate\s+in|diploma\s+in|"
    r"ph\.?\s*d\.?|d\.?\s*min\.?|d\.?\s*div\.?|ed\.?\s*d\.?|psy\.?\s*d\.?|"
    r"m\.?\s*div\.?|th\.?\s*m\.?|m\.?\s*a\.?|m\.?\s*s\.?|m\.?\s*b\.?\s*a\.?|"
    r"b\.?\s*a\.?|b\.?\s*s\.?|b\.?\s*b\.?\s*a\.?|a\.?\s*a\.?|a\.?\s*s\.?|"
    r"march|dba"
    r")\b",
    re.I,
)

_PROGRAM_CONTEXT_RE = re.compile(
    r"\b(program overview|degree requirements?|program requirements?|"
    r"curriculum|credit hours?|credits required|learning outcomes?|"
    r"admission to (?:the )?program|complete the program|degree completion)\b",
    re.I,
)

# Kesinlikle reddedilecek çöp program adları
_EXPLICIT_JUNK_PATTERNS = re.compile(
    r"^(?:"
    r"courses?|programs?|degree programs?|academic programs?|academics?|degrees?|majors?|"
    r"graduate programs?|undergraduate programs?|course catalog|academic catalog|student catalog|"
    r"admissions?|admission requirements?|tuition(?: and fees)?|fees?|"
    r"apply|application|register|registration|contact(?: us)?|about(?: us)?|"
    r"home|news|events?|insights?|blog|policies|policy|resources?|student services?|"
    r"json-ld structured data|content\.php|model curriculum|office hours|"
    r"mission|values|goals|team|executive team|advisory board|"
    r"licensure and accreditation|licensure|accreditation|consumer information|"
    r"catalog|schedule|continuing education"
    r")$"
    r"|\b(?:highest paying|best online|how to|how much|jobs with|online degree)\b",
    re.I,
)

_BAD_FILENAME_RE = re.compile(
    r".*(?:catalog|catalogs|schedule|handbook).*\.pdf$"
    r"|.*20\d{2}.*20\d{2}.*\.pdf$",
    re.I,
)

_BAD_PATH_RE = re.compile(
    r"/(?:"
    r"news|blog|insights?|events?|calendar|author|authors|tag|category|archive|"
    r"wp-json|feed|podcasts?|articles?|press|announcements?|"
    r"contact|about|people|faculty|staff|directory|alumni|giving|donate|"
    r"admissions?|apply|application|register|registration|tuition|fees?|"
    r"financial-aid|policies|policy|privacy|terms|resources?|library|bookstore|"
    r"search|login|portal|schedule|office-hours|licensure|accreditation|content\.php"
    r")(?:/|$)",
    re.I,
)

_LIST_PATH_RE = re.compile(
    r"/(?:degree-programs?|academic-programs?|programs?|academics?|degrees?|majors?)/?$",
    re.I,
)

_TITLE_SUFFIX_RE = re.compile(
    r"\s+(?:\||–|—|-)\s+(?:[^|–<ctrl42>]{2,80})$"
)


@dataclass(frozen=True)
class ProgramPageAssessment:
    accepted: bool
    score: int
    program_name: str | None
    reasons: tuple[str, ...]


def is_junk_program_name(name: str | None) -> bool:
    """Metnin çöp program adı olup olmadığını kontrol eder."""
    if not name:
        return True
    text = name.strip()
    if _EXPLICIT_JUNK_PATTERNS.search(text):
        return True
    if _BAD_FILENAME_RE.search(text):
        return True
    if re.search(r"\b(404|not found|access denied|just a moment)\b", text, re.I):
        return True
    return False


def clean_program_name(value: str | None) -> str | None:
    """Başlık metnini temizle ve genel sayfa adlarını reddet."""
    if not value:
        return None

    text = re.sub(r"\s+", " ", value).strip(" \t\r\n|–—-:")
    text = re.sub(
        r"^(?:program|degree)\s+(?:overview|details?)\s*[:\-–—]\s*",
        "",
        text,
        flags=re.I,
    )

    if _TITLE_SUFFIX_RE.search(text):
        left = _TITLE_SUFFIX_RE.sub("", text).strip()
        if _AWARD_RE.search(left):
            text = left

    text = re.sub(
        r"\s+(?:program|degree)\s+(?:overview|details?|information)$",
        "",
        text,
        flags=re.I,
    ).strip()

    if not (3 <= len(text) <= 180):
        return None
    if is_junk_program_name(text):
        return None
    return text


def _name_score(name: str, url: str) -> int:
    score = 0
    if _AWARD_RE.search(name):
        score += 6
    if re.search(r"\b(program|major|concentration)\b", name, re.I):
        score += 1

    slug = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    slug_words = {
        word for word in re.split(r"[-_./\s]+", slug.casefold())
        if len(word) > 2 and word not in {"program", "degree"}
    }
    name_words = {
        word for word in re.findall(r"[a-z0-9]+", name.casefold())
        if len(word) > 2 and word not in {"program", "degree", "the"}
    }
    if slug_words and len(slug_words & name_words) >= min(2, len(slug_words)):
        score += 2
    return score


def detect_program_name(
    sections: list[ContentSection],
    url: str,
) -> str | None:
    """H1/bölüm başlığı, sayfa başlığı ve URL'den en güçlü program adını seç."""
    raw_candidates: list[str] = []

    for section in sections:
        if section.source_type == "json_ld":
            continue
        if section.heading:
            raw_candidates.append(section.heading)

    for section in sections:
        if section.page_title:
            raw_candidates.append(section.page_title)
            break

    path = unquote(urlparse(url).path.rstrip("/"))
    if path:
        raw_candidates.append(
            path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ").title()
        )

    best_name: str | None = None
    best_score = -1
    seen: set[str] = set()
    for raw in raw_candidates:
        name = clean_program_name(raw)
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        score = _name_score(name, url)
        if score > best_score:
            best_name, best_score = name, score

    if not best_name:
        return None

    if _AWARD_RE.search(best_name):
        return best_name

    has_identity = False
    for section in sections:
        if section.source_type == "json_ld":
            continue
        sec_text = f"{section.heading or ''} {section.text}"
        if _AWARD_RE.search(sec_text) and _PROGRAM_CONTEXT_RE.search(sec_text):
            has_identity = True
            break

    return best_name if has_identity else None


def assess_program_page(
    url: str,
    sections: list[ContentSection],
    program_name: str | None = None,
) -> ProgramPageAssessment:
    """Sayfanın tekil bir program sayfası olup olmadığını puanla ve doğrula."""
    reasons: list[str] = []
    score = 0
    path = urlparse(url).path or "/"

    if _BAD_PATH_RE.search(path):
        return ProgramPageAssessment(False, -20, None, ("program dışı URL yolu",))

    name = program_name or detect_program_name(sections, url)
    if not name or is_junk_program_name(name):
        return ProgramPageAssessment(False, 0, None, ("doğrulanmış program adı yok",))

    name_points = _name_score(name, url)
    score += name_points
    reasons.append(f"program adı={name_points}")

    visible_text = " ".join(
        f"{section.heading or ''} {section.text}"
        for section in sections
        if section.source_type != "json_ld"
    )

    if _PROGRAM_CONTEXT_RE.search(visible_text):
        score += 3
        reasons.append("program bağlamı")

    has_degree = bool(_AWARD_RE.search(name))
    has_subject_context = False
    for section in sections:
        sec_text = f"{section.heading or ''} {section.text}"
        if _AWARD_RE.search(sec_text) and _PROGRAM_CONTEXT_RE.search(sec_text):
            has_subject_context = True
            break

    if not (has_degree or has_subject_context):
        return ProgramPageAssessment(False, score, None, ("sert program kimlik koşulu sağlanmadı",))

    if _LIST_PATH_RE.search(path):
        score -= 7
        reasons.append("genel program listesi")
    if len(visible_text) < 180:
        score -= 2
        reasons.append("yetersiz içerik")

    accepted = score >= 5 and not is_junk_program_name(name)
    return ProgramPageAssessment(accepted, score, name, tuple(reasons))


def looks_like_program_link(url: str, title: str = "") -> bool:
    """Keşif aşamasında kullanılacak ucuz, yüksek hassasiyetli ön filtre."""
    path = urlparse(url).path or "/"
    if _BAD_PATH_RE.search(path):
        return False
    if title and is_junk_program_name(title):
        return False

    cleaned_title = clean_program_name(title) if title else None
    if cleaned_title and _AWARD_RE.search(cleaned_title):
        return True

    slug = unquote(path.rstrip("/").rsplit("/", 1)[-1]).replace("-", " ")
    if _AWARD_RE.search(slug):
        return True

    return bool(re.search(
        r"/(?:programs?|degrees?|majors?|areas-of-study|academics?)/[^/]{3,}/?$",
        path,
        re.I,
    ))


def normalize_program_key(name: str) -> str:
    """Program tekilleştirmesi için noktalama/boşluk duyarsız anahtar."""
    return re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()
