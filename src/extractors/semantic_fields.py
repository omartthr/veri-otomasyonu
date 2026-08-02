"""48 sütunlu Programlar şablonu için kanıt-temelli metin alanları.

LLM kullanmadan yalnızca sayfada açıkça bulunan cümleleri ve kontrollü Türkçe
etiketleri üretir. Bir alan için açık kanıt yoksa değer döndürmez.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from src.program_pipeline.content_sections import ContentSection
from src.program_pipeline.models import ExtractedField


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])|(?<=:)\s+(?=[A-Z•])", text)
    return [part.strip(" •\t\r\n") for part in parts if 12 <= len(part.strip()) <= 700]


def _iter_evidence(
    sections: Iterable[ContentSection],
    pattern: re.Pattern[str],
) -> Iterable[tuple[ContentSection, str]]:
    for section in sections:
        if section.source_type == "json_ld":
            continue
        heading = section.heading or ""
        for sentence in _sentences(f"{heading}. {section.text}"):
            if pattern.search(sentence):
                yield section, sentence


def _field(
    value: object,
    section: ContentSection,
    evidence: str,
    source_url: str,
    *,
    scope: str,
    confidence: float = 0.90,
    notes: str | None = None,
) -> ExtractedField:
    return ExtractedField(
        value=value,
        source_url=source_url,
        evidence=evidence[:500],
        source_type=section.source_type,
        page_number=section.page_number,
        scope=scope,
        confidence=confidence,
        is_explicit=True,
        notes=notes,
    )


_DOC_LABELS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bofficial transcripts?\b", re.I), "resmî transkript"),
    (re.compile(r"\bunofficial transcripts?\b", re.I), "resmî olmayan transkript"),
    (re.compile(r"\btranscripts?\b", re.I), "transkript"),
    (re.compile(r"\bletters?\s+of\s+recommendation\b|\brecommendation\s+(?:forms?|letters?)\b", re.I), "tavsiye mektubu/formu"),
    (re.compile(r"\bpersonal statement\b|\bstatement of purpose\b", re.I), "kişisel/amaç beyanı"),
    (re.compile(r"\bpersonal testimony\b|\bwritten testimony\b", re.I), "yazılı kişisel tanıklık"),
    (re.compile(r"\bwriting sample\b|\bresearch paper\b", re.I), "yazı/araştırma örneği"),
    (re.compile(r"\bresume\b|\brésumé\b|\bcurriculum vitae\b|\bCV\b"), "CV/özgeçmiş"),
    (re.compile(r"\bproof of english proficiency\b|\benglish proficiency (?:score|test|result)\b", re.I), "İngilizce yeterlilik belgesi"),
    (re.compile(r"\bfinancial (?:statement|document|certification)\b", re.I), "mali belge"),
    (re.compile(r"\bapplication form\b|\bonline application\b", re.I), "çevrimiçi başvuru"),
    (re.compile(r"\bpassport\b|\bproof of identity\b", re.I), "kimlik/pasaport"),
]


def _extract_documents(
    sections: list[ContentSection],
    source_url: str,
    scope: str,
) -> ExtractedField:
    context_re = re.compile(
        r"\b(application requirements?|required materials?|application checklist|"
        r"how to apply|must submit|must provide|required documents?)\b",
        re.I,
    )
    for section in sections:
        combined = f"{section.heading or ''}. {section.text}"
        if not context_re.search(combined):
            continue
        labels: list[str] = []
        for pattern, label in _DOC_LABELS:
            if (
                label == "transkript"
                and any(existing in labels for existing in ("resmî transkript", "resmî olmayan transkript"))
            ):
                continue
            if pattern.search(combined) and label not in labels:
                labels.append(label)
        if labels:
            evidence = next(
                (
                    sentence for sentence in _sentences(combined)
                    if any(pattern.search(sentence) for pattern, _ in _DOC_LABELS)
                ),
                combined[:500],
            )
            return _field(
                "; ".join(labels),
                section,
                evidence,
                source_url,
                scope=scope,
                confidence=0.91,
            )
    return ExtractedField()


def extract_semantic_fields(
    sections: list[ContentSection],
    source_url: str,
    *,
    scope: str = "university",
    url_type: str = "general",
) -> dict[str, ExtractedField]:
    """Şablondaki anlatı/politika alanlarını açık kaynak cümlelerinden çıkar."""
    results: dict[str, ExtractedField] = {}

    def first(
        name: str,
        pattern: re.Pattern[str],
        value_builder,
        *,
        confidence: float = 0.90,
    ) -> None:
        for section, sentence in _iter_evidence(sections, pattern):
            value = value_builder(sentence)
            if value not in (None, ""):
                results[name] = _field(
                    value,
                    section,
                    sentence,
                    source_url,
                    scope=scope,
                    confidence=confidence,
                )
                return

    first(
        "Eğitim Dili",
        re.compile(
            r"\b(language of instruction|medium of instruction|courses? (?:are|is) taught)\b"
            r".{0,80}\benglish\b|\benglish\b.{0,80}\b(language of instruction|medium of instruction)\b",
            re.I,
        ),
        lambda _: "İngilizce",
        confidence=0.93,
    )

    first(
        "Başvuru Türü",
        re.compile(r"\b(apply online|online application|application portal)\b", re.I),
        lambda _: "Çevrimiçi başvuru",
        confidence=0.92,
    )

    first(
        "Mülakat Gerekli Mi",
        re.compile(
            r"\b(interview|personal interview)\b.{0,100}"
            r"\b(may|might|at the discretion|if requested|upon request)\b|"
            r"\b(may|might)\b.{0,100}\b(interview|personal interview)\b",
            re.I,
        ),
        lambda sentence: "Koşullu: " + sentence,
        confidence=0.91,
    )

    first(
        "İngilizce Yeterlilik Gerekli Mi",
        re.compile(
            r"\b(?:must|required to|are required to|need to)\b.{0,100}"
            r"\b(?:english proficiency|toefl|ielts|duolingo)\b|"
            r"\b(?:english proficiency|toefl|ielts|duolingo)\b.{0,100}"
            r"\b(?:required|must submit|must demonstrate)\b",
            re.I,
        ),
        lambda sentence: (
            "Koşullu: " + sentence
            if re.search(r"\b(if|unless|international|non-native|first language|native language)\b", sentence, re.I)
            else "Evet: " + sentence
        ),
        confidence=0.92,
    )

    first(
        "Standart Test Politikası",
        re.compile(
            r"\b(toefl|ielts|duolingo|english proficiency test)\b.{0,180}"
            r"\b(score|minimum|valid|within|years?|required|accepted)\b|"
            r"\b(score|results?)\b.{0,100}\b(toefl|ielts|duolingo)\b",
            re.I,
        ),
        lambda sentence: sentence,
        confidence=0.91,
    )

    first(
        "Transkript/GED Gereksinimi",
        re.compile(
            r"\b(official transcripts?|transcripts? from all|ged|secondary school record|"
            r"credential evaluation|course-by-course evaluation)\b",
            re.I,
        ),
        lambda sentence: sentence,
        confidence=0.92,
    )

    first(
        "Son Başvuru Metni",
        re.compile(
            r"\b(applications?.{0,80}(?:deadline|due|accepted|received)|"
            r"apply.{0,80}(?:before|by|prior to)|rolling admissions?|"
            r"no more than.{0,40}(?:year|month).{0,40}(?:start|enroll))\b",
            re.I,
        ),
        lambda sentence: sentence,
        confidence=0.90,
    )

    first(
        "Başvuru Dönemi",
        re.compile(r"\b(fall|spring|summer|winter)\s+(?:admission|entry|intake|semester|term)\b", re.I),
        lambda sentence: sentence,
        confidence=0.89,
    )

    first(
        "Akademik Yıl",
        re.compile(r"\b(?:academic year|catalog|tuition).{0,60}\b20\d{2}\s*[-–]\s*(?:20)?\d{2}\b", re.I),
        lambda sentence: (
            re.search(r"\b20\d{2}\s*[-–]\s*(?:20)?\d{2}\b", sentence).group(0)
            if re.search(r"\b20\d{2}\s*[-–]\s*(?:20)?\d{2}\b", sentence)
            else sentence
        ),
        confidence=0.91,
    )

    first(
        "Meslek Çıktıları",
        re.compile(
            r"\b(career opportunities|career paths?|graduates? (?:work|serve|pursue)|"
            r"prepares? (?:students|graduates|you) for|professional roles?|"
            r"employment opportunities|vocational opportunities)\b",
            re.I,
        ),
        lambda sentence: sentence,
        confidence=0.88,
    )

    results["Başvuru Belgeleri"] = _extract_documents(
        sections, source_url, scope
    )
    if results["Başvuru Belgeleri"].value is None:
        results.pop("Başvuru Belgeleri")

    required_item_pattern = re.compile(
        r"\b(minimum gpa|bachelor(?:'s)? degree|master(?:'s)? degree|"
        r"prerequisite|eligibility|must have completed|must hold|"
        r"degree from an accredited|professional experience required)\b",
        re.I,
    )
    required_sentences: list[tuple[ContentSection, str]] = []
    for section, sentence in _iter_evidence(sections, required_item_pattern):
        if not re.search(r"\b(required|must|minimum|eligible|prerequisite|at least)\b", sentence, re.I):
            continue
        if sentence not in [item[1] for item in required_sentences]:
            required_sentences.append((section, sentence))
    if required_sentences:
        section = required_sentences[0][0]
        evidence = " ".join(sentence for _, sentence in required_sentences[:4])
        results["Zorunlu Başvuru Maddeleri"] = _field(
            "; ".join(sentence for _, sentence in required_sentences[:4]),
            section,
            evidence,
            source_url,
            scope=scope,
            confidence=0.90,
        )

    review_pattern = re.compile(
        r"\b(admission committee|review committee|case[- ]by[- ]case|"
        r"holistic review|may be requested|may require|at the discretion|"
        r"credential evaluation|equivalency evaluation)\b",
        re.I,
    )
    for section, sentence in _iter_evidence(sections, review_pattern):
        results["İnceleme Gerektiren Maddeler"] = _field(
            sentence,
            section,
            sentence,
            source_url,
            scope=scope,
            confidence=0.90,
        )
        break

    # Kabul sayfasının kendisi, Kabul Verisi Kaynağı için en doğru değerdir.
    if url_type == "admission":
        evidence = next(
            (
                sentence
                for section in sections
                if section.source_type != "json_ld"
                for sentence in _sentences(f"{section.heading or ''}. {section.text}")
                if re.search(r"\b(admission|application|requirement)\b", sentence, re.I)
            ),
            None,
        )
        if evidence:
            section = next(s for s in sections if s.source_type != "json_ld")
            results["Kabul Verisi Kaynağı"] = _field(
                source_url,
                section,
                evidence,
                source_url,
                scope="university",
                confidence=0.99,
            )

    return results


def add_derived_policy_fields(
    fields: dict[str, ExtractedField],
) -> dict[str, ExtractedField]:
    """Yalnızca doğrulanmış bir ana alandan güvenli ikincil alan üret."""
    result = dict(fields)
    application_fee = result.get("Başvuru Ücreti")
    if application_fee and application_fee.value is not None:
        result["Başvuru Ücreti Gerekli Mi"] = application_fee.model_copy(
            update={"value": True, "notes": "Açık başvuru ücretinden türetildi"}
        )
    return result
