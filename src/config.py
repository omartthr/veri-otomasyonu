"""Uygulama yapılandırma modülü.

Pydantic Settings kullanarak .env dosyasından ayarları okur.
Projeye özel dizin yollarını ve doğrulama parametrelerini yönetir.

Not: Gemini/AI bağımlılıkları kaldırılmıştır.
Sistem tamamen kural tabanlı, deterministik, API anahtarı gerektirmeyen
modda çalışmaktadır.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Proje kök dizini
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# .env dosyasını yükle
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """Uygulama ayarları sınıfı."""

    # ─── İndirme ve HTTP Ayarları ───
    http_timeout: int = Field(
        default=30,
        description="HTTP istek zaman aşımı (saniye)",
    )
    max_download_size: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        description="Maksimum indirilecek dosya boyutu (byte)",
    )
    max_redirects: int = Field(
        default=5,
        description="Maksimum HTTP yönlendirme sayısı",
    )
    max_concurrency: int = Field(
        default=5,
        description="Eşzamanlı araştırılabilecek üniversite sayısı",
    )
    search_query_count: int = Field(
        default=4,
        validation_alias="SEARCH_QUERY_COUNT",
        description="Kategori başına paralel çalıştırılacak farklı web araması sayısı",
    )
    max_candidates_per_category: int = Field(
        default=24,
        validation_alias="MAX_CANDIDATES_PER_CATEGORY",
        description="Doğrulamaya gönderilecek en fazla güçlü aday URL sayısı",
    )
    deep_crawl_max_pages: int = Field(
        default=40,
        validation_alias="DEEP_CRAWL_MAX_PAGES",
        description="Kategori başına resmî site içinde taranacak azami sayfa",
    )
    deep_crawl_max_depth: int = Field(
        default=3,
        validation_alias="DEEP_CRAWL_MAX_DEPTH",
        description="Resmî site bağlantılarında izlenecek azami derinlik",
    )
    deep_crawl_concurrency: int = Field(
        default=6,
        validation_alias="DEEP_CRAWL_CONCURRENCY",
        description="Bir kurumun derin taramasındaki paralel HTTP isteği sayısı",
    )

    # ─── Doğrulama ve Karar Eşikleri (URL Bulma) ───
    rule_accept_threshold: int = Field(
        default=80,
        description="Anahtarsız kural motoru kabul eşiği (0-100)",
    )

    # ─── Program Pipeline Ayarları ───
    program_auto_write_threshold: float = Field(
        default=0.85,
        validation_alias="PROGRAM_AUTO_WRITE_THRESHOLD",
        description="Alan değerinin otomatik Excel'e yazılması için minimum confidence (0.0-1.0)",
    )
    program_domain_concurrency: int = Field(
        default=2,
        validation_alias="PROGRAM_DOMAIN_CONCURRENCY",
        description="Aynı domaine eşzamanlı maksimum istek sayısı (program pipeline)",
    )
    program_max_programs_per_uni: int = Field(
        default=100,
        description="Bir üniversiteden keşfedilecek maksimum program sayısı",
    )

    # ─── Proxy Ayarları (isteğe bağlı) ───
    proxy_url: Optional[str] = Field(
        default=None,
        validation_alias="PROXY_URL",
        description="Playwright için proxy URL (örn: http://user:pass@host:port)",
    )

    # ─── Dizin Yolları ───
    base_dir: Path = Field(default=PROJECT_ROOT)
    data_input_dir: Path = Field(default=PROJECT_ROOT / "data" / "input")
    data_output_dir: Path = Field(default=PROJECT_ROOT / "data" / "output")
    data_cache_dir: Path = Field(default=PROJECT_ROOT / "data" / "cache")
    checkpoint_dir: Path = Field(default=PROJECT_ROOT / "data" / "cache" / "checkpoints")
    audit_dir: Path = Field(default=PROJECT_ROOT / "data" / "audit")
    prompts_dir: Path = Field(default=PROJECT_ROOT / "prompts")

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def ensure_directories(self) -> None:
        """Gerekli veri dizinlerinin varlığından emin ol."""
        self.data_input_dir.mkdir(parents=True, exist_ok=True)
        self.data_output_dir.mkdir(parents=True, exist_ok=True)
        self.data_cache_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        (self.data_cache_dir / "html").mkdir(parents=True, exist_ok=True)
        (self.data_cache_dir / "pdf").mkdir(parents=True, exist_ok=True)
        (self.data_cache_dir / "playwright").mkdir(parents=True, exist_ok=True)
        (self.data_cache_dir / "extracted").mkdir(parents=True, exist_ok=True)


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Ayar örneğini döndürür (singleton)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
