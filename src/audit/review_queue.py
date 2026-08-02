"""Manuel inceleme kuyruğu — düşük confidence'lı alanları saklar ve yönetir."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_QUEUE_FILE_NAME = "review_queue.jsonl"


class ReviewItem(BaseModel):
    """Manuel inceleme bekleyen tek bir alan."""

    item_id: str
    university_id: str
    university_name: str
    program_name: str
    field_name: str
    proposed_value: Optional[object] = None
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    scope: str = "unknown"
    confidence: float = 0.0
    status: str = "pending"   # "pending" | "approved" | "rejected"
    approved_value: Optional[object] = None


class ReviewQueue:
    """JSONL tabanlı manuel inceleme kuyruğu."""

    def __init__(self, queue_path: str | Path):
        self.queue_path = Path(queue_path)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, item: ReviewItem) -> None:
        """Kuyruğa yeni öğe ekle."""
        try:
            with open(self.queue_path, "a", encoding="utf-8") as f:
                f.write(item.model_dump_json())
                f.write("\n")
        except Exception as e:
            logger.error("ReviewQueue yazma hatası: %s", e)

    def add_field(
        self,
        university_id: str,
        university_name: str,
        program_name: str,
        field_name: str,
        field,  # ExtractedField
    ) -> ReviewItem:
        """ExtractedField'dan ReviewItem oluştur ve ekle."""
        item = ReviewItem(
            item_id=str(uuid.uuid4())[:8],
            university_id=university_id,
            university_name=university_name,
            program_name=program_name,
            field_name=field_name,
            proposed_value=field.value,
            source_url=field.source_url,
            evidence=(field.evidence or "")[:300],
            scope=field.scope,
            confidence=field.confidence,
        )
        self.add(item)
        return item

    def get_pending(self) -> list[ReviewItem]:
        """Bekleyen öğeleri döndür."""
        if not self.queue_path.exists():
            return []
        items = []
        try:
            with open(self.queue_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    item = ReviewItem(**data)
                    if item.status == "pending":
                        items.append(item)
        except Exception as e:
            logger.error("ReviewQueue okuma hatası: %s", e)
        return items

    def _update_item(self, item_id: str, updates: dict) -> bool:
        """Öğeyi güncelle (satırı yeniden yaz)."""
        if not self.queue_path.exists():
            return False
        lines = self.queue_path.read_text(encoding="utf-8").splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("item_id") == item_id:
                    data.update(updates)
                    updated = True
                new_lines.append(json.dumps(data, ensure_ascii=False, default=str))
            except Exception:
                new_lines.append(line)

        if updated:
            self.queue_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return updated

    def approve(self, item_id: str, approved_value: object) -> bool:
        return self._update_item(item_id, {
            "status": "approved",
            "approved_value": approved_value,
        })

    def reject(self, item_id: str) -> bool:
        return self._update_item(item_id, {"status": "rejected"})

    @property
    def path(self) -> str:
        return str(self.queue_path)
