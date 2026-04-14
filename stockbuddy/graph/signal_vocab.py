"""
Five-way action vocabulary + parsing + ordinal direction_score.

Canonical tokens: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL.
direction_score in {-2,-1,0,1,2} for IC / Spearman; gates treat BUY+OVERWEIGHT as buy-side.
"""

from __future__ import annotations

import re
from typing import FrozenSet, Optional

VALID_ACTIONS: FrozenSet[str] = frozenset(
    {"BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"}
)

# Ordinal signal for Layer-1 Spearman IC (5 levels).
ACTION_TO_DIRECTION_SCORE: dict[str, int] = {
    "SELL": -2,
    "UNDERWEIGHT": -1,
    "HOLD": 0,
    "OVERWEIGHT": 1,
    "BUY": 2,
}

BUY_SIDE_ACTIONS: FrozenSet[str] = frozenset({"BUY", "OVERWEIGHT"})


def action_to_direction_score(action: Optional[str]) -> Optional[int]:
    if not action:
        return None
    return ACTION_TO_DIRECTION_SCORE.get(str(action).strip().upper())


def parse_action_from_signal(signal_str: str) -> Optional[str]:
    """Map free text or LLM line to one of five canonical actions."""
    if not signal_str or not str(signal_str).strip():
        return None
    s = str(signal_str).strip()
    u = s.upper()
    m = re.search(
        r"\b(BUY|SELL|HOLD|OVERWEIGHT|UNDERWEIGHT)\b",
        u,
    )
    if m:
        return m.group(1)
    # zh: order matters (UNDERWEIGHT before HOLD; OVERWEIGHT before BUY).
    if any(k in s for k in ("賣出", "卖出")):
        return "SELL"
    if any(k in s for k in ("減持", "减持", "减仓", "減倉")):
        return "UNDERWEIGHT"
    if any(k in s for k in ("持有", "觀望", "观望", "維持", "维持")):
        return "HOLD"
    if any(k in s for k in ("增持", "加倉", "加仓", "加碼", "加码")):
        return "OVERWEIGHT"
    if any(k in s for k in ("買入", "买入", "買進", "买进")):
        return "BUY"
    return None


def coerce_llm_action_token(llm_output: str, fallback_text: str) -> str:
    """First token from LLM if valid; else parse combined text; else HOLD."""
    if llm_output and str(llm_output).strip():
        tok = str(llm_output).strip().upper().split()[0]
        if tok in VALID_ACTIONS:
            return tok
    merged = (llm_output or "") + "\n" + (fallback_text or "")
    return parse_action_from_signal(merged) or "HOLD"
