"""İçerik bölümleme modülü — HTML ve PDF'ten yapılandırılmış bölümler.

H1-H6 başlıklarına göre bölümlere ayırır, tablolar ve listeler dahildir.
PDF'lerde sayfa numarasını korur.
Bölüm tabanlı saklama, extractorların bağlam içinde çalışmasını sağlar.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# PDF desteği için pdfplumber (pypdf yedek)
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False


class ContentSection(BaseModel):
    """Tek bir içerik bölümü."""

    heading: Optional[str] = None
    text: str = ""
    source_url: str = ""
    page_title: Optional[str] = None
    section_index: int = 0
    page_number: Optional[int] = None     # PDF için
    source_type: str = "html"             # "html" | "pdf" | "json_ld"
    tables: list[list[list[str]]] = []   # [[satır[hücre]]] formatında tablolar


def _clean_text(text: str) -> str:
    """Metni temizle — çok boşluk, satır başı vb."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_json_ld(soup: BeautifulSoup) -> list[str]:
    """Sayfadaki JSON-LD script etiketlerinden metin çıkar."""
    texts: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            texts.append(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass
    return texts


def _table_to_rows(table_tag: Tag) -> list[list[str]]:
    """HTML tablo etiketini string matrisine çevir."""
    rows = []
    for tr in table_tag.find_all("tr"):
        cells = [_clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        if any(cells):
            rows.append(cells)
    return rows


def extract_html_sections(
    html: bytes | str,
    source_url: str = "",
) -> list[ContentSection]:
    """HTML içeriğinden bölüm listesi çıkar.

    H1-H6 başlıkları bölüm sınırı olarak kullanılır.
    Her bölüm içindeki paragraflar, listeler ve tablolar dahildir.

    Args:
        html: HTML içeriği (bytes veya str)
        source_url: Kaynak URL (audit için)

    Returns:
        ContentSection listesi
    """
    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Sayfa başlığı
    page_title = ""
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()

    # JSON-LD bölümünü ekle
    json_ld_texts = _extract_json_ld(soup)
    sections: list[ContentSection] = []

    if json_ld_texts:
        sections.append(ContentSection(
            heading="JSON-LD Structured Data",
            text=" ".join(json_ld_texts),
            source_url=source_url,
            page_title=page_title,
            section_index=0,
            source_type="json_ld",
        ))

    # Gürültü etiketlerini kaldır
    for tag in soup.find_all(["script", "style", "noscript", "iframe", "svg", "canvas"]):
        tag.decompose()

    # Nav/footer tekrarlarını kaldır
    for tag in soup.find_all(["nav", "footer", "header"]):
        tag.decompose()

    # Cookie banner benzeri divleri kaldır
    for tag in soup.find_all(attrs={"class": re.compile(r"cookie|gdpr|banner|consent", re.I)}):
        tag.decompose()

    # Ana içerik alanı
    body = soup.find("main") or soup.find("article") or soup.body or soup

    # H1-H6 başlıklarına göre bölümlere böl. Yalnızca başlıkları dolaşıp
    # paragraf metnini atmak eski sürümdeki en kritik veri kaybıydı.
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    content_tags = heading_tags | {"p", "li", "dt", "dd", "blockquote", "pre", "table"}
    current_heading: Optional[str] = None
    current_chunks: list[str] = []
    current_tables: list[list[list[str]]] = []
    section_idx = len(sections)  # json_ld sonrası

    def flush_section():
        nonlocal section_idx
        text = _clean_text(" ".join(current_chunks))
        if text or current_tables:
            sections.append(ContentSection(
                heading=current_heading,
                text=text,
                source_url=source_url,
                page_title=page_title,
                section_index=section_idx,
                source_type="html",
                tables=current_tables[:],
            ))
            section_idx += 1

    if body:
        seen_chunks: set[str] = set()

        for element in body.find_all(content_tags):
            tag_name = element.name.lower() if element.name else ""

            # İç içe listelerde aynı metni iki kez alma. Tablo hücreleri de
            # tablo dönüştürücü tarafından ayrıca işlenir.
            if tag_name not in heading_tags and (
                element.find_parent("table")
                or element.find_parent(["p", "li", "dt", "dd", "blockquote", "pre"])
            ):
                continue

            if tag_name in heading_tags:
                flush_section()
                current_heading = _clean_text(element.get_text(" ", strip=True))
                current_chunks = []
                current_tables = []
                seen_chunks = set()
                continue

            if tag_name == "table":
                rows = _table_to_rows(element)
                if not rows:
                    continue
                current_tables.append(rows)
                chunk = " | ".join(
                    " | ".join(cell for cell in row)
                    for row in rows
                )
            else:
                chunk = _clean_text(element.get_text(" ", strip=True))

            # Menü kalıntıları ve yinelenen bloklar çıkarıcıları yanıltmasın.
            chunk_key = chunk.casefold()
            if len(chunk) >= 2 and chunk_key not in seen_chunks:
                current_chunks.append(chunk)
                seen_chunks.add(chunk_key)

    flush_section()

    # Yalnızca çok kısa metinli ve tablosuz bölümleri filtrele
    return [s for s in sections if len(s.text) > 20 or s.tables]


def extract_pdf_sections(
    pdf_bytes: bytes,
    source_url: str = "",
) -> list[ContentSection]:
    """PDF içeriğinden bölüm listesi çıkar.

    Sayfa numarasını korur. "Admission Requirements",
    "English Proficiency", "Tuition and Fees" gibi bölüm başlıklarını tanır.

    Args:
        pdf_bytes: PDF dosyasının bytes içeriği
        source_url: Kaynak URL

    Returns:
        ContentSection listesi
    """
    if not pdf_bytes:
        return []

    sections: list[ContentSection] = []

    # pdfplumber tercih edilir; yoksa pypdf
    if _HAS_PDFPLUMBER:
        try:
            import io
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                sections = _parse_pdf_with_pdfplumber(pdf, source_url)
        except Exception as e:
            logger.warning("pdfplumber başarısız (%s): %s", source_url, e)

    if not sections and _HAS_PYPDF:
        try:
            import io
            reader = PdfReader(io.BytesIO(pdf_bytes))
            sections = _parse_pdf_with_pypdf(reader, source_url)
        except Exception as e:
            logger.warning("pypdf başarısız (%s): %s", source_url, e)

    if not sections:
        logger.warning("PDF'ten metin çıkarılamadı: %s — manuel incelemeye gönderilecek", source_url)

    return sections


def _parse_pdf_with_pdfplumber(pdf, source_url: str) -> list[ContentSection]:
    """pdfplumber ile PDF'ten bölüm çıkar."""
    _SECTION_MARKERS = re.compile(
        r"^(admission requirements|english proficiency|english language|"
        r"tuition and fees|cost of attendance|program requirements|"
        r"academic requirements|language requirements|financial information)",
        re.I,
    )

    sections: list[ContentSection] = []
    current_heading: Optional[str] = None
    current_lines: list[str] = []
    current_page: Optional[int] = None
    section_idx = 0

    def flush(page_num):
        nonlocal section_idx
        text = _clean_text(" ".join(current_lines))
        if text:
            sections.append(ContentSection(
                heading=current_heading,
                text=text,
                source_url=source_url,
                page_title=None,
                section_index=section_idx,
                page_number=page_num,
                source_type="pdf",
            ))
            section_idx += 1

    for page_num, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if _SECTION_MARKERS.match(line):
                flush(current_page)
                current_heading = line
                current_lines = []
                current_page = page_num
            else:
                current_lines.append(line)
                if current_page is None:
                    current_page = page_num

    flush(current_page)
    return sections


def _parse_pdf_with_pypdf(reader, source_url: str) -> list[ContentSection]:
    """pypdf ile PDF'ten bölüm çıkar (basit sayfa bazlı)."""
    sections: list[ContentSection] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = _clean_text(text)
        if len(text) > 30:
            sections.append(ContentSection(
                heading=None,
                text=text,
                source_url=source_url,
                section_index=page_num - 1,
                page_number=page_num,
                source_type="pdf",
            ))
    return sections


def sections_to_plain_text(sections: list[ContentSection]) -> str:
    """Bölümleri düz metin olarak birleştir (backward compat için)."""
    parts: list[str] = []
    for s in sections:
        if s.heading:
            parts.append(f"\n## {s.heading}\n")
        parts.append(s.text)
    return "\n".join(parts)
