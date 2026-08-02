"""PDF metin çıkarma modülü.

pypdf kullanarak PDF dosyalarından metin içeriğini çıkarır.
"""

from __future__ import annotations

import io
import logging
import re
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_pdf_content(pdf_bytes: bytes) -> tuple[str, str]:
    """PDF içeriğinden sayfa başlığını (varsa) ve temizlenmiş metni çıkarır.

    Args:
        pdf_bytes: PDF dosyasının ham baytları

    Returns:
        (pdf_title, clean_text) çifti
    """
    if not pdf_bytes:
        return "", ""

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))

        # Başlık meta verisi
        pdf_title = ""
        if reader.metadata and reader.metadata.title:
            pdf_title = reader.metadata.title.strip()

        extracted_pages: list[str] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                extracted_pages.append(text)

        full_text = "\n".join(extracted_pages)
        clean_text = re.sub(r"\s+", " ", full_text).strip()

        if not pdf_title and reader.pages:
            # İlk sayfadan başlık benzeri ilk satırı al
            first_line = clean_text.split(". ")[0][:100]
            pdf_title = first_line if first_line else "PDF Document"

        return pdf_title, clean_text

    except Exception as e:
        logger.warning(f"PDF metin çıkarma hatası: {e}")
        return "", ""
