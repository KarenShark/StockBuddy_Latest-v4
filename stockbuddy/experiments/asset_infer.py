"""
HK asset_type: hk_equity / hk_etf / unknown (v1 simple rules).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from stockbuddy.dataflows.hk_stock_names import get_hk_stock_chinese_name

VALID_ASSET_TYPES = frozenset({"hk_equity", "hk_etf", "unknown"})


def _normalize_hk_numeric_code(ticker: str) -> Optional[str]:
    t = ticker.strip().upper().replace(".HK", "").replace(".HKG", "").strip()
    if not t or not t.isdigit():
        return None
    if len(t) > 5:
        return None
    return t.zfill(4)


def infer_asset_type(ticker: str, config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (asset_type, source) where source is config | inferred | unknown.
    """
    override = config.get("asset_type")
    if isinstance(override, str) and override in VALID_ASSET_TYPES:
        return override, "config"

    code = _normalize_hk_numeric_code(ticker)
    if code is None:
        return "unknown", "unknown"

    name = get_hk_stock_chinese_name(ticker)
    if name:
        if "基金" in name:
            return "hk_etf", "inferred"
        return "hk_equity", "inferred"

    if re.fullmatch(r"\d{4,5}", code):
        return "hk_equity", "inferred"

    return "unknown", "unknown"
