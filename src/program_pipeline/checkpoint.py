"""Checkpoint sistemi v3 — program pipeline ilerlemesini kaydeder ve sürüm denetimi yapar.

Schema sürümü değiştiğinde eski checkpoint kararları geçersiz sayılır.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PIPELINE_SCHEMA_VERSION = "program-quality-v3"
_CHECKPOINT_FILE = "program_pipeline_checkpoint.json"


class CheckpointManager:
    """Program pipeline checkpoint yönetimi."""

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_path = self.checkpoint_dir / _CHECKPOINT_FILE
        self._state: dict = self._load()

    def _load(self) -> dict:
        if self._checkpoint_path.exists():
            try:
                with open(self._checkpoint_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("schema_version") == PIPELINE_SCHEMA_VERSION:
                        return data
                    else:
                        logger.info("Eski schema sürümü tespit edildi (%s != %s). Checkpoint yenileniyor.",
                                    data.get("schema_version"), PIPELINE_SCHEMA_VERSION)
            except Exception as e:
                logger.warning("Checkpoint okunamadı, sıfırlanıyor: %s", e)
        return {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "completed_universities": [],
            "failed_universities": {},
            "program_counts": {},
            "last_saved_output": None,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    def save(self) -> None:
        """Checkpoint'i diske kaydet."""
        self._state["schema_version"] = PIPELINE_SCHEMA_VERSION
        self._state["updated_at"] = datetime.now().isoformat()
        try:
            tmp = self._checkpoint_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            tmp.replace(self._checkpoint_path)
        except Exception as e:
            logger.error("Checkpoint kaydetme hatası: %s", e)

    def is_completed(self, university_name: str) -> bool:
        """Bu üniversite geçerli sürümde tamamlandı mı?"""
        return university_name in self._state.get("completed_universities", [])

    def mark_completed(
        self,
        university_name: str,
        program_count: int = 0,
        output_path: Optional[str] = None,
    ) -> None:
        """Üniversiteyi tamamlandı olarak işaretle."""
        completed = self._state.setdefault("completed_universities", [])
        if university_name not in completed:
            completed.append(university_name)
        self._state.setdefault("program_counts", {})[university_name] = program_count
        if output_path:
            self._state["last_saved_output"] = output_path
        self.save()

    def mark_failed(self, university_name: str, reason: str) -> None:
        """Üniversiteyi başarısız olarak işaretle."""
        self._state.setdefault("failed_universities", {})[university_name] = {
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        self.save()

    def get_last_output(self) -> Optional[str]:
        return self._state.get("last_saved_output")

    def reset(self) -> None:
        """Checkpoint'i sıfırla."""
        self._state = {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "completed_universities": [],
            "failed_universities": {},
            "program_counts": {},
            "last_saved_output": None,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.save()
        logger.info("Checkpoint sıfırlandı.")


class PageCache:
    """HTTP sayfa içeriği cache sistemi."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        for subdir in ("html", "pdf", "playwright", "extracted"):
            (self.cache_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        return hashlib.sha256(f"{PIPELINE_SCHEMA_VERSION}:{url}".encode("utf-8")).hexdigest()[:16]

    def get_html(self, url: str) -> Optional[bytes]:
        path = self.cache_dir / "html" / f"{self._key(url)}.html"
        if path.exists():
            try:
                return path.read_bytes()
            except Exception:
                pass
        return None

    def set_html(self, url: str, content: bytes) -> None:
        path = self.cache_dir / "html" / f"{self._key(url)}.html"
        try:
            path.write_bytes(content)
        except Exception as e:
            logger.debug("Cache yazma hatası (%s): %s", url, e)

    def get_pdf(self, url: str) -> Optional[bytes]:
        path = self.cache_dir / "pdf" / f"{self._key(url)}.pdf"
        if path.exists():
            try:
                return path.read_bytes()
            except Exception:
                pass
        return None

    def set_pdf(self, url: str, content: bytes) -> None:
        path = self.cache_dir / "pdf" / f"{self._key(url)}.pdf"
        try:
            path.write_bytes(content)
        except Exception as e:
            logger.debug("PDF cache yazma hatası (%s): %s", url, e)

    def get_extracted(self, url: str) -> Optional[dict]:
        path = self.cache_dir / "extracted" / f"{self._key(url)}.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def set_extracted(self, url: str, data: dict) -> None:
        path = self.cache_dir / "extracted" / f"{self._key(url)}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.debug("Extracted cache yazma hatası (%s): %s", url, e)

    def clear(self) -> None:
        """Cache'i temizle."""
        import shutil
        for subdir in ("html", "pdf", "playwright", "extracted"):
            p = self.cache_dir / subdir
            if p.exists():
                shutil.rmtree(p)
                p.mkdir(parents=True, exist_ok=True)
        logger.info("Cache temizlendi.")
