"""Şehir & Yaşam Rehberi — TÜİK & YÖK Kanonik Veri Sağlayıcısı.

TÜİK ADNKS nüfusları, YÖK İstatistikleri ve ÖSYM Kılavuz verilerini
deterministik ve kanıtlı olarak sağlar.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static_data"


class TuikYokCanonicalProvider:
    """TÜİK ve YÖK kanonik veri sağlayıcısı."""

    def __init__(self):
        self._tuik_data = self._load("tuik_adnks.json")
        self._climate_data = self._load("mgm_climate.json")
        self._earthquake_data = self._load("afad_earthquake.json")

    def _load(self, filename: str) -> dict:
        path = STATIC_DIR / filename
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Statik veri yüklenemedi (%s): %s", filename, e)
            return {}

    def get_city_canonical_data(self, sehir_id: str) -> dict[str, Any]:
        """Bir şehir için resmî TÜİK, MGM ve AFAD verilerini döndür."""
        res: dict[str, Any] = {}
        sid = str(sehir_id).strip()

        # TÜİK
        tuik = self._tuik_data.get(sid, {})
        if tuik:
            res["nufus"] = tuik.get("nufus")
            res["rakim"] = tuik.get("rakim")
            res["deniz"] = tuik.get("deniz")

        # MGM
        mgm = self._climate_data.get(sid, {})
        if mgm:
            res["iklim"] = mgm.get("iklim")
            res["kis"] = mgm.get("kis")
            res["yaz"] = mgm.get("yaz")

        # AFAD
        afad = self._earthquake_data.get(sid)
        if afad is not None:
            res["deprem"] = afad

        return res
