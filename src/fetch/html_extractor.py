"""HTML içerik çıkarma modülü.

BeautifulSoup kullanarak HTML sayfalarından gürültüyü (navigasyon,
altbilgi, script, stil) temizler ve ana metni çıkarır.
"""

from __future__ import annotations

import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Temizlenecek gereksiz HTML etiketleri
NOISE_TAGS = [
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "header", "footer", "nav", "aside", "form",
]


def extract_html_content(html_bytes: bytes | str) -> tuple[str, str]:
    """HTML içeriğinden sayfa başlığını ve temizlenmiş metni çıkarır.

    Args:
        html_bytes: HTML içeriği (bytes veya str)

    Returns:
        (page_title, clean_text) çifti
    """
    if not html_bytes:
        return "", ""

    try:
        soup = BeautifulSoup(html_bytes, "html.parser")
    except Exception as e:
        logger.warning(f"HTML ayrıştırma hatası: {e}")
        return "", ""

    # Sayfa başlığı
    page_title = ""
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()
    elif soup.h1 and soup.h1.string:
        page_title = soup.h1.string.strip()

    # Gürültü etiketlerini kaldır
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Ana içeriği veya gövdeyi al
    main_element = soup.find("main") or soup.find("article") or soup.body or soup

    # Metni çıkar
    text = main_element.get_text(separator=" ", strip=True)

    # Fazla boşluk ve yeni satırları temizle
    text = re.sub(r"\s+", " ", text).strip()

    return page_title, text
