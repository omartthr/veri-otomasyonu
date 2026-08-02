"""HTTP ile sayfa indirme modülü.

httpx kullanarak web sayfalarını ve PDF dosyalarını indirir.
Güvenlik (is_safe_url), maksimum dosya boyutu, SSL esnekliği ve
retry mekanizmalarını yönetir.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings
from src.domain_utils import is_official_domain, is_safe_url, normalize_url
from src.fetch.html_extractor import extract_html_content
from src.fetch.pdf_extractor import extract_pdf_content
from src.models import CandidateURL, ResearchCategory

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_CURL_META_MARKER = b"\n__UNIVERSITY_FETCH_META__\t"
_CHALLENGE_MARKERS = (
    b"cf-chl-", b"just a moment", b"checking your browser", b"verify you are human",
    b"enable javascript and cookies", b"captcha challenge", b"<title>captcha",
    b"access denied", b"request blocked",
)


def _looks_like_challenge(content: bytes) -> bool:
    """Bot koruması/CAPTCHA HTML'sini gerçek üniversite içeriğinden ayır."""
    sample = content[:200_000].lower()
    return any(marker in sample for marker in _CHALLENGE_MARKERS)


async def _fetch_with_curl(
    url: str,
    timeout: int,
    max_redirects: int,
    max_size: int,
    proxy_url: Optional[str] = None,
) -> tuple[int, str, str, bytes] | None:
    """403/429 bot korumasında sistem curl'ü ile tarayıcı benzeri güvenli fallback."""
    curl_exe = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_exe:
        return None
    write_out = "\\n__UNIVERSITY_FETCH_META__\\t%{http_code}\\t%{url_effective}\\t%{content_type}"
    args = [
        curl_exe,
        "--silent",
        "--show-error",
        "--location",
        "--compressed",
        "--max-time", str(timeout),
        "--max-redirs", str(max_redirects),
        "--max-filesize", str(max_size),
        "--header", f"User-Agent: {USER_AGENT}",
        "--header", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
        "--header", "Accept-Language: en-US,en;q=0.9",
        "--write-out", write_out,
    ]
    if proxy_url:
        args.extend(["--proxy", proxy_url])
    args.append(url)
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0 or _CURL_META_MARKER not in stdout:
        return None
    body, _, metadata = stdout.rpartition(_CURL_META_MARKER)
    parts = metadata.decode("utf-8", errors="replace").split("\t", 2)
    if len(parts) != 3:
        return None
    try:
        status = int(parts[0])
    except ValueError:
        return None
    return status, normalize_url(parts[1]), parts[2].lower(), body


async def _fetch_with_browser(
    url: str,
    timeout: int,
    max_size: int,
    proxy_url: Optional[str] = None,
) -> tuple[int, str, str, bytes] | None:
    """JS/cookie gerektiren resmî sayfayı mevcut Edge ile render et."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    try:
        async with async_playwright() as playwright:
            launch_args = {"channel": "msedge", "headless": True}
            if proxy_url:
                launch_args["proxy"] = {"server": proxy_url}
            browser = await playwright.chromium.launch(**launch_args)
            try:
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    locale="en-US",
                    viewport={"width": 1440, "height": 1000},
                )
                page = await context.new_page()

                async def guard_navigation(route, request):
                    if request.is_navigation_request() and (
                        not is_safe_url(request.url)
                        or not is_official_domain(request.url, url)
                    ):
                        await route.abort()
                    else:
                        await route.continue_()

                await page.route("**/*", guard_navigation)
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout * 1000,
                )
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=min(timeout * 1000, 8000),
                    )
                except Exception:
                    pass

                final_url = normalize_url(page.url)
                html = (await page.content()).encode("utf-8", errors="replace")
                if len(html) > max_size:
                    return None
                status = response.status if response else 0
                content_type = (
                    (await response.header_value("content-type")) if response else None
                ) or "text/html; charset=utf-8"
                return status, final_url, content_type.lower(), html
            finally:
                await browser.close()
    except Exception as exc:
        logger.info("Tarayıcı fallback kullanılamadı (%s): %s", url, exc)
        return None


class PageFetcher:
    """Async web sayfası ve PDF indirici."""

    def __init__(
        self,
        timeout: Optional[int] = None,
        max_size: Optional[int] = None,
        max_redirects: Optional[int] = None,
    ):
        settings = get_settings()
        self.timeout = timeout or settings.http_timeout
        self.max_size = max_size or settings.max_download_size
        self.max_redirects = max_redirects or settings.max_redirects
        self.proxy_url = settings.proxy_url

    async def fetch_candidate(
        self,
        url: str,
        category: ResearchCategory,
        source_query: str = "",
    ) -> CandidateURL:
        """Belirtilen URL'yi indir ve CandidateURL olarak döndür.

        Args:
            url: İndirilecek web adresi
            category: Araştırma kategorisi
            source_query: URL'yi bulan arama sorgusu

        Returns:
            CandidateURL nesnesi (sayfa metni, başlık, HTTP durumu vb. dahil)
        """
        # Güvenlik kontrolü
        if not is_safe_url(url):
            logger.warning(f"Güvenli olmayan URL engellendi: {url}")
            return CandidateURL(
                url=url,
                category=category,
                source_query=source_query,
                http_status=403,
            )

        norm_url = normalize_url(url)
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }

        try:
            client_kwargs = {
                "timeout": httpx.Timeout(self.timeout),
                "follow_redirects": True,
                "max_redirects": self.max_redirects,
                "headers": headers,
                "verify": True,
            }
            if self.proxy_url:
                client_kwargs["proxy"] = self.proxy_url

            async with httpx.AsyncClient(
                **client_kwargs,
            ) as client:
                try:
                    response = await client.get(norm_url)
                except (httpx.RequestError, httpx.HTTPError) as exc:
                    logger.info(f"İstek hatası ({exc}), doğrulamamasız deneniyor: {norm_url}")
                    fallback_kwargs = dict(client_kwargs)
                    fallback_kwargs["verify"] = False
                    async with httpx.AsyncClient(**fallback_kwargs) as fallback_client:
                        response = await fallback_client.get(norm_url)

                http_status = response.status_code
                final_url = normalize_url(str(response.url))
                redirect_count = len(response.history)
                content_type = response.headers.get("content-type", "").lower()
                content = response.content
                browser_attempted = False

                if http_status in (403, 429):
                    curl_result = await _fetch_with_curl(
                        norm_url,
                        self.timeout,
                        self.max_redirects,
                        self.max_size,
                        self.proxy_url,
                    )
                    if curl_result:
                        http_status, final_url, content_type, content = curl_result
                        logger.info("Curl fallback başarılı: %s | HTTP=%s", final_url, http_status)

                if http_status in (403, 429) or _looks_like_challenge(content):
                    browser_attempted = True
                    browser_result = await _fetch_with_browser(
                        norm_url,
                        self.timeout,
                        self.max_size,
                        self.proxy_url,
                    )
                    if browser_result:
                        http_status, final_url, content_type, content = browser_result
                        logger.info("Tarayıcı fallback başarılı: %s | HTTP=%s", final_url, http_status)

                # Yönlendirme sonrası resmî/güvenli alan zorunluluğunu indirme katmanında da uygula.
                if (
                    not is_safe_url(final_url)
                    or not is_official_domain(final_url, norm_url)
                ):
                    return CandidateURL(
                        url=final_url,
                        requested_url=norm_url,
                        redirect_count=redirect_count,
                        category=category,
                        source_query=source_query,
                        http_status=403,
                        content_type=content_type,
                    )

                if _looks_like_challenge(content):
                    http_status = 403

                content_length = len(content)

                # Boyut sınırı kontrolü
                if content_length > self.max_size:
                    logger.warning(f"Maksimum dosya boyutu aşıldı ({content_length} byte): {norm_url}")
                    return CandidateURL(
                        url=final_url,
                        requested_url=norm_url,
                        redirect_count=redirect_count,
                        category=category,
                        source_query=source_query,
                        http_status=http_status,
                        content_type=content_type,
                        content_length=content_length,
                    )

                if http_status != 200:
                    return CandidateURL(
                        url=final_url,
                        requested_url=norm_url,
                        redirect_count=redirect_count,
                        category=category,
                        source_query=source_query,
                        http_status=http_status,
                        content_type=content_type,
                    )

                # PDF vs HTML ayrımı
                is_pdf = "pdf" in content_type or final_url.lower().endswith(".pdf")

                if is_pdf:
                    title, text = extract_pdf_content(content)
                else:
                    title, text = extract_html_content(content)

                # HTTP 200 dönse bile yalnızca boş bir JavaScript kabuğu geldiyse render et.
                if (
                    not is_pdf
                    and len(text) < 200
                    and not browser_attempted
                ):
                    browser_result = await _fetch_with_browser(
                        norm_url,
                        self.timeout,
                        self.max_size,
                        self.proxy_url,
                    )
                    if browser_result:
                        browser_status, browser_url, browser_type, browser_content = browser_result
                        if (
                            browser_status == 200
                            and is_safe_url(browser_url)
                            and is_official_domain(browser_url, norm_url)
                            and not _looks_like_challenge(browser_content)
                        ):
                            http_status = browser_status
                            final_url = browser_url
                            content_type = browser_type
                            content = browser_content
                            content_length = len(content)
                            title, text = extract_html_content(content)
                raw_html_str = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)

                return CandidateURL(
                    url=final_url,
                    requested_url=norm_url,
                    redirect_count=redirect_count,
                    category=category,
                    source_query=source_query,
                    http_status=http_status,
                    content_type=content_type,
                    content_length=content_length,
                    page_title=title,
                    extracted_text=text,
                    raw_html=raw_html_str,
                    raw_content=content,
                    is_pdf=is_pdf,
                )

        except Exception as e:
            logger.warning(f"URL indirilemedi ({norm_url}): {e}")
            return CandidateURL(
                url=norm_url,
                category=category,
                source_query=source_query,
                http_status=500,
            )
