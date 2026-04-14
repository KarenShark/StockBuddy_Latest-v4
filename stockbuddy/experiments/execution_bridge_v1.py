"""
execution bridge v1: decision.json -> execution_spec + order_spec v2 (opt-in, no pipeline hook).
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXECUTION_SPEC_SCHEMA_VERSION = "1.0"

# HK board lot hints; override via ExecutionBridgeInput.lot_size. Unknown -> 100.
HK_BOARD_LOT_BY_TICKER: Dict[str, int] = {
    "0700": 100,
    "00700": 100,
    "0941": 500,
    "00941": 500,
    "1299": 200,
    "01299": 200,
    "9988": 100,
    "09988": 100,
}


def _norm_ticker_key(t: str) -> str:
    s = str(t).strip().upper().replace(".HK", "")
    return s.lstrip("0") or s


def resolve_hk_lot_size(ticker: str, override: Optional[int]) -> int:
    if override is not None and override > 0:
        return int(override)
    k = _norm_ticker_key(ticker)
    for cand in (k, k.zfill(5) if k.isdigit() else k):
        if cand in HK_BOARD_LOT_BY_TICKER:
            return HK_BOARD_LOT_BY_TICKER[cand]
    if k.isdigit():
        z5 = k.zfill(5)
        if z5 in HK_BOARD_LOT_BY_TICKER:
            return HK_BOARD_LOT_BY_TICKER[z5]
    return 100


def floor_shares_to_lot(raw_shares: float, lot_size: int) -> int:
    if lot_size <= 0:
        return int(math.floor(raw_shares))
    if raw_shares <= 0:
        return 0
    return int(math.floor(raw_shares / lot_size)) * lot_size


def deterministic_position_fraction(
    *,
    action: Optional[str],
    confidence: Optional[float],
    risk_flags: Optional[List[str]],
    blocked_by_risk_gate: bool,
) -> Tuple[float, str]:
    flags = risk_flags or []
    n_flags = len(flags)
    act = (action or "").strip().upper()

    if blocked_by_risk_gate:
        return 0.0, "blocked_by_risk_gate;size=0"
    if act == "HOLD":
        return 0.0, "action_hold;no_new_risk"
    if act == "SELL":
        return 0.0, "action_sell;long_only_v1_no_add;exit_is_portfolio_state"
    if act != "BUY":
        return 0.0, f"action_{act or 'missing'};no_size"

    c = 0.55 if confidence is None else float(confidence)
    c = max(0.0, min(1.0, c))
    if c < 0.5:
        base = 0.10 + (c / 0.5) * 0.05
    else:
        base = 0.15 + ((c - 0.5) / 0.5) * 0.35
    penalty = min(0.20, n_flags * 0.04)
    frac = base - penalty
    frac = max(0.05, min(0.50, frac))
    reason = (
        f"buy;conf={c:.3f};base={base:.3f};risk_flags={n_flags}"
        f"({','.join(flags) if flags else '-'});penalty={penalty:.3f};frac={frac:.3f}"
    )
    return round(frac, 4), reason


def execution_action_for(
    *,
    action: Optional[str],
    blocked_by_risk_gate: bool,
    position_fraction: float,
) -> str:
    if blocked_by_risk_gate:
        return "SKIP_RISK_GATE"
    act = (action or "").strip().upper()
    if act == "HOLD":
        return "NO_TRADE"
    if act == "SELL":
        return "EXIT_SIGNAL"
    if act == "BUY" and position_fraction > 0:
        return "BUY_NEXT_OPEN"
    if act == "BUY":
        return "NO_TRADE"
    return "NO_TRADE"


@dataclass
class ExecutionBridgeInput:
    """Caller-supplied sizing context; not read from decision.json (no AI sizing)."""

    account_notional_hkd: float = 100_000.0
    ref_price_hkd: Optional[float] = None
    lot_size: Optional[int] = None
    execution_tier: str = "backtest_shadow"


def build_execution_spec(
    decision: Dict[str, Any],
    inp: Optional[ExecutionBridgeInput] = None,
) -> Dict[str, Any]:
    inp = inp or ExecutionBridgeInput()
    ticker = decision.get("ticker")
    analysis_date = decision.get("analysis_date")
    run_id = decision.get("run_id")
    action = decision.get("action")
    conf = decision.get("confidence")
    blocked = bool(decision.get("blocked_by_risk_gate", False))
    risk_flags = decision.get("risk_flags") or []

    pos_frac, sizing_reason = deterministic_position_fraction(
        action=action,
        confidence=conf if isinstance(conf, (int, float)) else None,
        risk_flags=risk_flags if isinstance(risk_flags, list) else [],
        blocked_by_risk_gate=blocked,
    )
    exec_action = execution_action_for(
        action=action,
        blocked_by_risk_gate=blocked,
        position_fraction=pos_frac,
    )

    notional = round(float(inp.account_notional_hkd) * pos_frac, 2)
    lot = resolve_hk_lot_size(str(ticker or ""), inp.lot_size)

    raw_shares: Optional[float]
    adj_shares: Optional[int]
    px = inp.ref_price_hkd
    if px is not None and float(px) > 0 and notional > 0 and exec_action == "BUY_NEXT_OPEN":
        raw_shares = notional / float(px)
        adj_shares = floor_shares_to_lot(raw_shares, lot)
    else:
        raw_shares = None
        adj_shares = None

    entry_rule = "NEXT_OPEN" if action == "BUY" and not blocked else "NONE"
    exit_rule = "TIME_EXIT" if action == "BUY" and not blocked else "NONE"

    return {
        "schema_version": EXECUTION_SPEC_SCHEMA_VERSION,
        "ticker": ticker,
        "analysis_date": analysis_date,
        "decision_action": action,
        "execution_action": exec_action,
        "position_fraction": pos_frac,
        "target_notional": notional,
        "entry_rule": entry_rule,
        "exit_rule": exit_rule,
        "lot_size": lot,
        "target_shares_raw": raw_shares,
        "target_shares_lot_adjusted": adj_shares,
        "execution_tier": inp.execution_tier,
        "sizing_reason": sizing_reason,
        "source_run_id": run_id,
    }


def load_or_synthesize_execution_spec(
    row: Dict[str, Any],
    *,
    initial_cash_hkd: float,
    ref_price_hkd: Optional[float],
) -> Optional[Dict[str, Any]]:
    """Prefer on-disk execution_spec / order_spec.v2; else decision.json + ref close."""
    raw = row.get("experiment_dir")
    if not raw:
        return None
    base = Path(str(raw))
    if not base.is_dir():
        return None
    for name in ("execution_spec.json", "order_spec.v2.json"):
        p = base / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    dec_path = base / "decision.json"
    if (
        dec_path.is_file()
        and ref_price_hkd is not None
        and float(ref_price_hkd) > 0
    ):
        decision = json.loads(dec_path.read_text(encoding="utf-8"))
        inp = ExecutionBridgeInput(
            account_notional_hkd=float(initial_cash_hkd),
            ref_price_hkd=float(ref_price_hkd),
            execution_tier="backtest_shadow",
        )
        return build_execution_spec(decision, inp)
    return None


def build_order_spec_v2(
    decision: Dict[str, Any],
    inp: Optional[ExecutionBridgeInput] = None,
) -> Dict[str, Any]:
    """Superset of legacy order_spec.json keys + execution fields for handoff/backtest."""
    ex = build_execution_spec(decision, inp)
    action = decision.get("action")
    blocked = bool(decision.get("blocked_by_risk_gate", False))
    is_buy = action == "BUY" and not blocked
    legacy = {
        "ticker": decision.get("ticker"),
        "analysis_date": decision.get("analysis_date"),
        "action": action,
        "confidence": decision.get("confidence"),
        "position_fraction": ex["position_fraction"],
        "entry_rule": ex["entry_rule"],
        "exit_rule": ex["exit_rule"],
        "stop_loss": 0.95 if is_buy else None,
        "take_profit": 1.10 if is_buy else None,
        "max_holding_days": 5 if is_buy else None,
        "blocked_by_risk_gate": blocked,
        "gate_reason": decision.get("gate_reason"),
        "rationale_summary": decision.get("rationale_summary"),
        "run_id": decision.get("run_id"),
    }
    out = {**legacy, **ex}
    out["schema_version"] = EXECUTION_SPEC_SCHEMA_VERSION
    return out


def smoke_timeline_execution_modes() -> None:
    """Two backtest runs on one batch: default signal path vs execution_bridge_v1."""
    root = Path(__file__).resolve().parents[2]
    batches_root = root / "experiments" / "batches"
    jsonl: Optional[Path] = None
    if batches_root.is_dir():
        for pth in sorted(batches_root.glob("*/decisions.jsonl")):
            for line in pth.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                ed = r.get("experiment_dir")
                if ed and Path(str(ed)).is_dir():
                    jsonl = pth
                    break
            if jsonl:
                break
    if jsonl is None:
        print("smoke_timeline_execution_modes: SKIP (no decisions.jsonl with valid experiment_dir)")
        return

    from stockbuddy.evaluation.timeline_backtest import run_timeline_backtest

    bd = jsonl.parent
    a = run_timeline_backtest(batch_dir=bd, execution_mode="signal_only")
    b = run_timeline_backtest(batch_dir=bd, execution_mode="execution_bridge_v1")
    ma = json.loads(a.metrics_path.read_text(encoding="utf-8"))
    mb = json.loads(b.metrics_path.read_text(encoding="utf-8"))
    print("--- smoke: same batch, two modes ---")
    print(f"batch_dir={bd}")
    print(
        f"signal_only: num_trades={ma.get('num_trades')} "
        f"execution_mode={ma.get('execution_mode')} dir={a.output_dir.name}"
    )
    print(
        f"execution_bridge_v1: num_trades={mb.get('num_trades')} "
        f"execution_mode={mb.get('execution_mode')} dir={b.output_dir.name} "
        f"bridge={mb.get('bridge_execution')}"
    )


def _smoke() -> None:
    root = Path(__file__).resolve().parents[2]
    sample = root / "experiments" / "20260327T173925Z_630e8b7a4375" / "decision.json"
    if not sample.is_file():
        sample = root / "experiments" / "20260327T174318Z_4f8d1e7ce686" / "decision.json"
    decision = json.loads(sample.read_text(encoding="utf-8"))
    inp = ExecutionBridgeInput(
        account_notional_hkd=100_000.0,
        ref_price_hkd=52.3,
        execution_tier="smoke",
    )
    ex = build_execution_spec(decision, inp)
    v2 = build_order_spec_v2(decision, inp)
    print("--- execution_spec ---")
    print(json.dumps(ex, ensure_ascii=False, indent=2))
    print("--- order_spec_v2 (merge) ---")
    print(json.dumps(v2, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="Build execution_spec / order_spec_v2 from decision.json")
    p.add_argument("decision_json", nargs="?", help="Path to decision.json (default: smoke sample)")
    p.add_argument("--account-notional", type=float, default=100_000.0)
    p.add_argument("--ref-price", type=float, default=None)
    p.add_argument("--lot-size", type=int, default=None)
    p.add_argument("--tier", type=str, default="cli")
    p.add_argument("--write-dir", type=str, default=None, help="If set, write execution_spec.json + order_spec.v2.json")
    p.add_argument(
        "--smoke-backtest",
        action="store_true",
        help="Run signal_only vs execution_bridge_v1 timeline backtest on a sample batch",
    )
    args = p.parse_args()
    if args.smoke_backtest:
        smoke_timeline_execution_modes()
        return
    if not args.decision_json:
        _smoke()
        return
    path = Path(args.decision_json)
    decision = json.loads(path.read_text(encoding="utf-8"))
    inp = ExecutionBridgeInput(
        account_notional_hkd=args.account_notional,
        ref_price_hkd=args.ref_price,
        lot_size=args.lot_size,
        execution_tier=args.tier,
    )
    ex = build_execution_spec(decision, inp)
    v2 = build_order_spec_v2(decision, inp)
    print(json.dumps({"execution_spec": ex, "order_spec_v2": v2}, ensure_ascii=False, indent=2))
    if args.write_dir:
        wd = Path(args.write_dir)
        wd.mkdir(parents=True, exist_ok=True)
        (wd / "execution_spec.json").write_text(
            json.dumps(ex, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (wd / "order_spec.v2.json").write_text(
            json.dumps(v2, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
