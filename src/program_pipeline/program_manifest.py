"""Program Envanteri ve Manifest Yönetimi.

Alan çıkarmaya başlamadan önce her üniversite için doğrulanmış program adaylarından
oluşan tekil bir program manifesti oluşturur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgramCandidate:
    university_id: str
    university_name: str
    canonical_program_name: str
    degree_level: str
    subject: str
    campus: str
    modality: str
    program_url: str
    identity_evidence: str
    identity_score: int
    accepted: bool
    rejection_reason: str = ""


_DEGREE_ALIAS_MAP = {
    "mba": "Master of Business Administration",
    "m.b.a.": "Master of Business Administration",
    "m.b.a": "Master of Business Administration",
    "master of business administration": "Master of Business Administration",
    "online master of business administration": "Master of Business Administration",
    "mdiv": "Master of Divinity",
    "m.div.": "Master of Divinity",
    "master of divinity": "Master of Divinity",
    "bsn": "Bachelor of Science in Nursing",
    "b.s.n.": "Bachelor of Science in Nursing",
    "bachelor of science in nursing": "Bachelor of Science in Nursing",
    "dba": "Doctor of Business Administration",
    "d.b.a.": "Doctor of Business Administration",
    "doctor of business administration": "Doctor of Business Administration",
    "phd": "Doctor of Philosophy",
    "ph.d.": "Doctor of Philosophy",
    "doctor of philosophy": "Doctor of Philosophy",
}


def normalize_degree_level(name: str) -> str:
    """Program adından derece seviyesini çıkarır (Bachelor, Master, Doctor, Certificate vb.)."""
    lower = name.lower()
    if re.search(r"\b(doctor|doctorate|ph\.?d\.?|d\.?min\.?|edd|psyd|dba)\b", lower):
        return "Doctoral"
    if re.search(r"\b(master|masters|m\.?div\.?|m\.?a\.?|m\.?s\.?|m\.?b\.?a\.?|march|thm)\b", lower):
        return "Graduate"
    if re.search(r"\b(bachelor|bachelors|b\.?a\.?|b\.?s\.?|b\.?b\.?a\.?|bsn)\b", lower):
        return "Undergraduate"
    if re.search(r"\b(associate|a\.?a\.?|a\.?s\.?)\b", lower):
        return "Associate"
    if re.search(r"\b(certificate|diploma)\b", lower):
        return "Certificate"
    return "Other"


def get_canonical_program_name(name: str) -> str:
    """Program adını canonical formata çevirir (MBA -> Master of Business Administration vb.)."""
    cleaned = re.sub(r"\s+", " ", name).strip()
    key = cleaned.lower()

    if key in _DEGREE_ALIAS_MAP:
        return _DEGREE_ALIAS_MAP[key]

    # Online öneklerini standardize et
    normalized = re.sub(r"^(?:online|hybrid)\s+", "", cleaned, flags=re.I).strip()
    key_norm = normalized.lower()
    if key_norm in _DEGREE_ALIAS_MAP:
        return _DEGREE_ALIAS_MAP[key_norm]

    return cleaned


def extract_subject_from_name(name: str) -> str:
    """Program adından ana konu alanını çıkarır."""
    text = re.sub(
        r"^(?:Associate|Bachelor|Master|Doctor|Doctorate|PhD|DBA|DMin|EdD|PsyD|Certificate|Diploma)\s+(?:of|in|of Science in|of Arts in|of Business Administration in)?\s*",
        "",
        name,
        flags=re.I,
    ).strip()
    return text or name


def generate_dedup_key(
    university_name: str,
    degree_level: str,
    subject: str,
    campus: str = "",
    modality: str = "",
) -> str:
    """Güçlü tekilleştirme anahtarı oluşturur.

    Anahtar bileşenleri: üniversite + derece seviyesi + ana konu + kampüs + eğitim türü
    """
    u_key = re.sub(r"[^a-z0-9]+", "", university_name.lower())
    d_key = degree_level.lower()
    s_key = re.sub(r"[^a-z0-9]+", "", subject.lower())
    c_key = re.sub(r"[^a-z0-9]+", "", campus.lower()) if campus else "main"
    m_key = re.sub(r"[^a-z0-9]+", "", modality.lower()) if modality else "standard"
    return f"{u_key}:{d_key}:{s_key}:{c_key}:{m_key}"


class ProgramManifest:
    """Üniversiteye ait doğrulanmış program manifestini tutar ve yönetir."""

    def __init__(self, university_id: str, university_name: str):
        self.university_id = university_id
        self.university_name = university_name
        self.candidates: list[ProgramCandidate] = []
        self._seen_keys: dict[str, ProgramCandidate] = {}

    def add_candidate(self, candidate: ProgramCandidate) -> bool:
        """Adayı manifest'e ekler. Yinelenen varsa yüksek puanlı olan kazanır.

        Returns:
            Aday yeni mi yoksa güncellendi mi?
        """
        if not candidate.accepted:
            self.candidates.append(candidate)
            return False

        key = generate_dedup_key(
            self.university_name,
            candidate.degree_level,
            candidate.subject,
            candidate.campus,
            candidate.modality,
        )

        existing = self._seen_keys.get(key)
        if existing is None:
            self._seen_keys[key] = candidate
            self.candidates.append(candidate)
            return True

        if candidate.identity_score > existing.identity_score:
            # Mevcut adayın yerine yenisini koy
            idx = self.candidates.index(existing)
            self.candidates[idx] = candidate
            self._seen_keys[key] = candidate
            return True

        return False

    def get_accepted_candidates(self) -> list[ProgramCandidate]:
        """Kabul edilen tekil adayların listesini döndürür."""
        return list(self._seen_keys.values())

    def get_rejected_candidates(self) -> list[ProgramCandidate]:
        """Reddedilen adayların listesini döndürür."""
        return [c for c in self.candidates if not c.accepted]
