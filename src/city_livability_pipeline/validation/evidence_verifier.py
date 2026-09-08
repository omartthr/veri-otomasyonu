"""Şehir & Yaşam Rehberi — Kanıt (Evidence) ve Kaynak Doğrulayıcı.

Çıkarılan her alanın dayanak metnini (quote), kaynak domain otoritesini
ve güncellik yılını doğrular.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

# Resmî veya Yüksek Güvenilirlikteki Domain Kalıpları
GOV_TR_PATTERN = re.compile(r"\.(gov|bel|pol|afad|mgm|tuik|osym|yok|gsb)\.tr$", re.IGNORECASE)
EDU_TR_PATTERN = re.compile(r"\.edu\.tr$", re.IGNORECASE)
KNOWN_TRUSTED_DOMAINS = {
    "tuik.gov.tr", "data.tuik.gov.tr", "mgm.gov.tr", "deprem.afad.gov.tr",
    "yok.gov.tr", "istatistik.yok.gov.tr", "yokatlas.yok.gov.tr",
    "osym.gov.tr", "gsb.gov.tr", "kyk.gsb.gov.tr",
    "tcddtasimacilik.gov.tr", "dhmi.gov.tr",
    "iett.istanbul", "ego.gov.tr", "eshot.gov.tr",
    "endeksa.com", "sahibinden.com", "emlakjet.com",
    "openstreetmap.org", "wikipedia.org", "wikimedia.org",
}


def get_domain_authority_score(url: Optional[str]) -> float:
    """URL'in domain otorite puanını hesapla (0.0 - 1.0).

    .gov.tr, resmî kurumlar: 1.0
    .edu.tr (üniversiteler): 0.95
    belediye / ulaşım kurumları: 0.90
    kurumsal endeksler (Endeksa vb.): 0.80
    genel web: 0.50
    """
    if not url:
        return 0.0
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        # Port numarasını temizle
        if ":" in netloc:
            netloc = netloc.split(":")[0]

        # Doğrudan bilinen resmî domainler
        if any(netloc == d or netloc.endswith("." + d) for d in KNOWN_TRUSTED_DOMAINS):
            if "gov.tr" in netloc or "afad" in netloc or "mgm" in netloc:
                return 1.0
            if "edu.tr" in netloc:
                return 0.95
            return 0.85

        # TLD kalıpları
        if GOV_TR_PATTERN.search(netloc):
            return 1.0
        if EDU_TR_PATTERN.search(netloc):
            return 0.95
        if ".org.tr" in netloc or ".bel.tr" in netloc:
            return 0.90

        return 0.50
    except Exception:
        return 0.0


def verify_evidence_contains_value(
    value: Any,
    evidence_text: Optional[str],
) -> bool:
    """Çıkarılan değerin kanıt metninde (quote) gerçekten yer alıp almadığını doğrula."""
    if value is None or not evidence_text:
        return False

    val_str = str(value).strip().lower()
    ev_norm = evidence_text.strip().lower()

    # Tam eşleşme
    if val_str in ev_norm:
        return True

    # Sayısal format toleransı (15000 -> 15.000 veya 15,000)
    try:
        val_float = float(val_str.replace(",", "."))
        val_int = int(round(val_float))

        patterns = [
            str(val_int),
            f"{val_int:,}".replace(",", "."),  # 15.000
            f"{val_int:,}",                   # 15,000
            f"{val_float:.2f}".replace(".", ","),
        ]
        for p in patterns:
            if p in ev_norm:
                return True
    except (ValueError, TypeError):
        pass

    return False


def detect_content_year(text: Optional[str]) -> Optional[int]:
    """Metin içindeki en güncel yılı tespit et (Örn: 2024, 2025, 2026, 2027)."""
    if not text:
        return None
    years = re.findall(r"\b(202[0-9])\b", text)
    if years:
        return max(int(y) for y in years)
    return None


def format_cell_comment(
    source_url: Optional[str],
    evidence: Optional[str] = None,
    rule_info: Optional[str] = None,
) -> Optional[str]:
    """Excel hücresine eklenecek zengin kaynak yorumunu formatla."""
    lines = []
    if source_url:
        lines.append(f"🔗 Kaynak: {source_url}")
    if evidence:
        clean_ev = evidence.strip()
        if len(clean_ev) > 250:
            clean_ev = clean_ev[:247] + "..."
        lines.append(f"📝 Kanıt: \"{clean_ev}\"")
    if rule_info:
        lines.append(f"⚙️ Doğrulama: {rule_info}")

    return "\n".join(lines) if lines else None
