"""
Generate downstream executable order specifications from decision artifacts.
"""

from typing import Any, Dict, Optional


def generate_order_spec_from_decision(decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Translates a decision.json record into an execution-ready order specification.
    Long-only v1: entry hints for BUY / OVERWEIGHT when not blocked.
    """
    action = decision.get("action")
    blocked = decision.get("blocked_by_risk_gate", False)

    conf = decision.get("confidence")
    fraction = 0.0
    long_side = action in ("BUY", "OVERWEIGHT") and not blocked
    if long_side:
        base = conf if conf is not None else 0.5
        scale = 0.5 if action == "BUY" else 0.35
        fraction = round(base * scale, 2)
        lo = 0.05 if action == "OVERWEIGHT" else 0.1
        fraction = max(lo, min(fraction, 1.0))

    spec = {
        "ticker": decision.get("ticker"),
        "analysis_date": decision.get("analysis_date"),
        "action": action,
        "direction_score": decision.get("direction_score"),
        "confidence": conf,
        "position_fraction": fraction,
        "entry_rule": "NEXT_OPEN" if long_side else "NONE",
        "exit_rule": "TIME_EXIT" if long_side else "NONE",
        "stop_loss": 0.95 if long_side else None,
        "take_profit": 1.10 if long_side else None,
        "max_holding_days": 5,                               # Aligned with formal_eval_v1
        "blocked_by_risk_gate": blocked,
        "gate_reason": decision.get("gate_reason"),
        "rationale_summary": decision.get("rationale_summary"),
        "run_id": decision.get("run_id"),
    }
    return spec
