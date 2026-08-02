"""JSONL audit kaydı — her alan çıkarım ve yazma kararını loglar.

Her satır bir JSONL kaydıdır:
{
  "university_id": "...",
  "university_name": "...",
  "program_name": "...",
  "field_name": "Minimum GPA",
  "value": 3.0,
  "source_url": "...",
  "evidence": "...",
  "page_number": 52,
  "scope": "program",
  "confidence": 0.97,
  "status": "written",  // "written" | "skipped_low_confidence" | "review_queue" | "empty"
  "timestamp": "..."
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.program_pipeline.models import ExtractedField

logger = logging.getLogger(__name__)

_AUDIT_FILE_NAME = "program_pipeline_audit.jsonl"


class EvidenceStore:
    """JSONL formatında audit kayıtları yönetir."""

    def __init__(self, audit_dir: Path):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.audit_dir / _AUDIT_FILE_NAME
        self._buffer: list[dict] = []
        self._flush_threshold = 50

    def record(
        self,
        university_id: str,
        university_name: str,
        program_name: str,
        field_name: str,
        field: ExtractedField,
        status: str,  # "written" | "skipped_low_confidence" | "review_queue" | "empty"
    ) -> None:
        """Bir alan kararını kaydet."""
        record = {
            "university_id": university_id or "",
            "university_name": university_name,
            "program_name": program_name,
            "field_name": field_name,
            "value": field.value,
            "source_url": field.source_url,
            "evidence": (field.evidence or "")[:300],
            "page_number": field.page_number,
            "source_type": field.source_type,
            "scope": field.scope,
            "confidence": round(field.confidence, 4),
            "is_explicit": field.is_explicit,
            "is_historical": field.is_historical,
            "notes": field.notes,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        self._buffer.append(record)

        if len(self._buffer) >= self._flush_threshold:
            self.flush()

    def flush(self) -> None:
        """Buffer'ı diske yaz."""
        if not self._buffer:
            return
        try:
            with open(self.audit_path, "a", encoding="utf-8") as f:
                for rec in self._buffer:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str))
                    f.write("\n")
            self._buffer.clear()
        except Exception as e:
            logger.error("Audit yazma hatası: %s", e)

    def close(self) -> None:
        """Kalan buffer'ı yaz."""
        self.flush()

    @property
    def path(self) -> str:
        return str(self.audit_path)
