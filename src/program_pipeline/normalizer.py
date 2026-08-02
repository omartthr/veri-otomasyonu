"""İsim normalizasyon modülü — üniversite adı eşleştirme için.

Büyük/küçük harf, noktalama, Unicode ve üniversite tipi
suffix'lerini normalize eder.

ÖNEMLİ: Normalizasyon yalnızca KARŞILAŞTIRMA için kullanılır.
Orijinal isimler hiçbir zaman değiştirilmez.
"""

from __future__ import annotations

import re
import unicodedata

# Karşılaştırmada yok sayılacak üniversite tipi suffix'leri
_UNI_SUFFIXES = {
    "university",
    "universities",
    "college",
    "colleges",
    "institute",
    "institutes",
    "institution",
    "school",
    "academy",
    "polytechnic",
    "seminary",
    "conservatory",
    "the",
    "of",
    "and",
    "&",
}

# Sık karıştırılan Türkçe/İngilizce karakter eşlemeleri
_CHAR_MAP = str.maketrans(
    "ğüşıöçĞÜŞİÖÇ",
    "gusiocGUSIOC",
)


def normalize_for_comparison(name: str) -> str:
    """İsmi karşılaştırma için normalize et.

    - Unicode normalize et (NFKD)
    - Türkçe karakterleri ASCII'ye çevir
    - Küçük harfe çevir
    - Noktalama kaldır
    - Fazla boşlukları temizle
    - UNI_SUFFIXES kelimeleri kaldır

    Args:
        name: Orijinal üniversite adı

    Returns:
        Normalize edilmiş versiyon (yalnızca karşılaştırma için)
    """
    if not name:
        return ""

    # Unicode normalize
    text = unicodedata.normalize("NFKD", name)
    # Türkçe karakterler
    text = text.translate(_CHAR_MAP)
    # ASCII olmayan karakterleri kaldır
    text = text.encode("ascii", errors="ignore").decode("ascii")
    # Küçük harf
    text = text.lower()
    # Noktalama kaldır
    text = re.sub(r"[^\w\s]", " ", text)
    # Fazla boşluk
    text = re.sub(r"\s+", " ", text).strip()
    # Suffix kelimeleri kaldır (sıralamayı koru)
    words = [w for w in text.split() if w not in _UNI_SUFFIXES]
    return " ".join(words)


def normalize_university_id(uid: str) -> str:
    """Üniversite ID'sini normalize et (tam eşleşme için)."""
    return str(uid).strip().upper()


def similarity_score(a: str, b: str) -> float:
    """İki normalize edilmiş isim arasındaki benzerlik skoru (0.0-1.0).

    Basit token overlap metriği.
    """
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
