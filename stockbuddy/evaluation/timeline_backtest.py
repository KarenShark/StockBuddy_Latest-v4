"""
Timeline backtest: BUY-only, fixed 5-session hold, exit 6th session open; fees from fee_schedule.
"""

from __future__ import annotations

import csv
import json
import math
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from stockbuddy.default_config import DEFAULT_CONFIG
from stockbuddy.experiments.execution_bridge_v1 import load_or_synthesize_execution_spec

from stockbuddy.evaluation.fee_schedule import (
    FEE_SNAPSHOT_AS_OF,
    FEE_SNAPSHOT_VERSION,
    merge_fee_models_for_metrics,
    per_side_fee,
    resolve_fee_components,
)
from stockbuddy.evaluation.prices import (
    date_range_covering_signals,
    exit_open_after_hold,
    fetch_ohlc,
    next_trading_day_open,
    normalize_hk_symbol,
    trading_days_index,
)


EXIT_LAG_SESSIONS = 5


@dataclass
class PlannedTrade:
    run_id: str
    signal_date: date
    asset_type_raw: str
    entry_date: date
    exit_date: date
    entry_open: float
    exit_open: float
    fee_components: Dict[str, Dict[str, Any]]
    schedule_key: str
    sizing_mode: str = "signal_only"
    position_fraction: float = 1.0
    target_shares_lot_adjusted: Optional[int] = None
    lot_size: int = 1
    execution_action: Optional[str] = None


@dataclass
class TimelineBacktestResult:
    output_dir: Path
    trades_path: Path
    metrics_path: Path
    equity_curve_path: Path
    summary_path: Path


def _parse_analysis_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _parse_action(a: Any) -> Optional[str]:
    if a is None:
        return None
    t = str(a).strip().upper()
    if t in ("BUY", "SELL", "HOLD"):
        return t
    return None


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _ref_close_for_sizing(ohlc: Any, sig_day: date) -> Optional[float]:
    if sig_day in ohlc.index:
        return float(ohlc.loc[sig_day]["Close"])
    for d in reversed(list(ohlc.index)):
        if d <= sig_day:
            return float(ohlc.loc[d]["Close"])
    return None


def run_timeline_backtest(
    *,
    batch_dir: Path | None = None,
    decisions_jsonl: Path | None = None,
    initial_cash: float = 100_000.0,
    config: Dict[str, Any] | None = None,
    execution_mode: Optional[str] = None,
    exit_lag_sessions: int = EXIT_LAG_SESSIONS,
    output_subdir: str | None = None,
) -> TimelineBacktestResult:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    mode = execution_mode if execution_mode is not None else cfg.get("execution_mode", "signal_only")
    if mode not in ("signal_only", "execution_bridge_v1"):
        raise ValueError(f"execution_mode must be signal_only or execution_bridge_v1, got {mode!r}")
    hold_n = int(cfg.get("timeline_backtest_hold_sessions", exit_lag_sessions))
    if hold_n < 1:
        raise ValueError("timeline backtest hold sessions must be >= 1")

    if decisions_jsonl is not None:
        jsonl_path = Path(decisions_jsonl)
        bd = jsonl_path.parent
    elif batch_dir is not None:
        bd = Path(batch_dir)
        jsonl_path = bd / "decisions.jsonl"
    else:
        raise ValueError("Provide batch_dir or decisions_jsonl")

    if not jsonl_path.is_file():
        raise FileNotFoundError(jsonl_path)

    rows = _load_jsonl(jsonl_path)
    ticker = rows[0].get("ticker") if rows else None
    if not ticker:
        raise ValueError("decisions.jsonl missing ticker")

    symbol = normalize_hk_symbol(str(ticker))

    # --- signal statistics
    n_buy = n_sell = n_hold = n_null = 0
    n_overlap_skip = 0
    n_data_skip = 0
    unknown_fallback_signals = 0
    unknown_fallback_trades = 0

    parsed_rows: List[Dict[str, Any]] = []
    for row in rows:
        act = _parse_action(row.get("action"))
        if act == "BUY":
            n_buy += 1
        elif act == "SELL":
            n_sell += 1
        elif act == "HOLD":
            n_hold += 1
        else:
            n_null += 1

        at = row.get("asset_type")
        if at is None or str(at).lower() == "unknown":
            unknown_fallback_signals += 1

        parsed_rows.append(
            {
                "row": row,
                "action": act,
                "analysis_date": row.get("analysis_date"),
                "run_id": row.get("run_id"),
                "asset_type": at,
            }
        )

    parsed_rows.sort(key=lambda x: (x["analysis_date"] or "", x["run_id"] or ""))

    signal_dates: List[date] = []
    for p in parsed_rows:
        if p["analysis_date"]:
            signal_dates.append(_parse_analysis_date(p["analysis_date"]))

    start_d, end_d = date_range_covering_signals(signal_dates, hold_n)
    ohlc = fetch_ohlc(symbol, start_d, end_d)
    if ohlc.empty:
        raise RuntimeError(f"No OHLC data for {symbol}")

    planned: List[PlannedTrade] = []
    busy_until: Optional[date] = None
    n_bridge_skip_spec = 0
    n_bridge_skip_exec_action = 0
    n_bridge_skip_sizing = 0

    for p in parsed_rows:
        act = p["action"]
        if act != "BUY":
            continue

        sig_day = _parse_analysis_date(p["analysis_date"])
        if busy_until is not None and sig_day < busy_until:
            n_overlap_skip += 1
            continue

        nxt = next_trading_day_open(ohlc, sig_day)
        if nxt is None:
            n_data_skip += 1
            continue
        entry_day, entry_open = nxt

        ex = exit_open_after_hold(ohlc, entry_day, exit_lag_sessions=hold_n)
        if ex is None:
            n_data_skip += 1
            continue
        exit_day, exit_open = ex

        raw_at = p.get("asset_type")
        raw_s = str(raw_at).lower() if raw_at is not None else "unknown"
        sk, components, fb = resolve_fee_components(
            raw_s if raw_s in ("hk_equity", "hk_etf", "unknown") else "unknown", cfg
        )
        if fb:
            unknown_fallback_trades += 1

        sizing_mode = "signal_only"
        pos_frac = 1.0
        tgt_lot: Optional[int] = None
        lot_sz = 1
        exec_act: Optional[str] = None

        if mode == "execution_bridge_v1":
            ref_px = _ref_close_for_sizing(ohlc, sig_day)
            exspec = load_or_synthesize_execution_spec(
                p["row"],
                initial_cash_hkd=float(initial_cash),
                ref_price_hkd=ref_px,
            )
            if exspec is None:
                n_bridge_skip_spec += 1
                continue
            exec_act = str(exspec.get("execution_action") or "")
            if exec_act != "BUY_NEXT_OPEN":
                n_bridge_skip_exec_action += 1
                continue
            pos_frac = float(exspec.get("position_fraction") or 0.0)
            raw_tgt = exspec.get("target_shares_lot_adjusted")
            tgt_lot = int(raw_tgt) if raw_tgt is not None else None
            lot_sz = int(exspec.get("lot_size") or 1)
            if lot_sz < 1:
                lot_sz = 1
            if pos_frac <= 0 and (tgt_lot is None or tgt_lot <= 0):
                n_bridge_skip_sizing += 1
                continue
            sizing_mode = "execution_bridge_v1"

        planned.append(
            PlannedTrade(
                run_id=str(p["run_id"]),
                signal_date=sig_day,
                asset_type_raw=raw_s,
                entry_date=entry_day,
                exit_date=exit_day,
                entry_open=entry_open,
                exit_open=exit_open,
                fee_components=components,
                schedule_key=sk,
                sizing_mode=sizing_mode,
                position_fraction=pos_frac,
                target_shares_lot_adjusted=tgt_lot,
                lot_size=lot_sz,
                execution_action=exec_act,
            )
        )
        busy_until = exit_day

    num_ignored = n_sell + n_hold + n_null + n_overlap_skip + n_data_skip

    # --- merge default components for metrics (resolved defaults, not per-trade overrides)
    _, eq_c, _ = resolve_fee_components("hk_equity", cfg)
    _, etf_c, _ = resolve_fee_components("hk_etf", cfg)
    fee_model_meta = merge_fee_models_for_metrics(eq_c, etf_c)

    # --- simulate
    cash = float(initial_cash)
    shares = 0.0
    trades_out: List[Dict[str, Any]] = []
    trade_id = 0
    n_entry_skip_zero = 0

    days = trading_days_index(ohlc)

    q = deque(planned)
    active: Optional[PlannedTrade] = None

    equity_rows: List[Dict[str, Any]] = []

    for d in days:
        if active is not None and d == active.exit_date:
            notional_s = shares * active.exit_open
            fee_ex = per_side_fee(notional_s, active.fee_components)
            cash += notional_s - fee_ex
            gross = shares * (active.exit_open - active.entry_open)
            fee_en = per_side_fee(shares * active.entry_open, active.fee_components)
            trade_id += 1
            trades_out.append(
                {
                    "trade_id": trade_id,
                    "run_id": active.run_id,
                    "signal_date": active.signal_date.isoformat(),
                    "asset_type": active.asset_type_raw,
                    "entry_date": active.entry_date.isoformat(),
                    "exit_date": active.exit_date.isoformat(),
                    "entry_price_open": active.entry_open,
                    "exit_price_open": active.exit_open,
                    "shares": shares,
                    "gross_pnl": gross,
                    "fee_entry": fee_en,
                    "fee_exit": fee_ex,
                    "fees": fee_en + fee_ex,
                    "execution_action": active.execution_action,
                    "sizing_mode": active.sizing_mode,
                    "target_shares_lot_adjusted": active.target_shares_lot_adjusted,
                    "position_fraction_spec": active.position_fraction,
                }
            )
            shares = 0.0
            active = None

        if not q and active is None:
            pass
        elif q and active is None and d == q[0].entry_date:
            tr = q.popleft()
            rate_sum = sum(float(m["rate"]) for m in tr.fee_components.values())
            denom = tr.entry_open * (1.0 + rate_sum)
            if denom <= 0:
                continue
            if tr.sizing_mode == "execution_bridge_v1":
                cap_sh = cash / denom
                lot = max(1, tr.lot_size)
                if tr.target_shares_lot_adjusted is not None and tr.target_shares_lot_adjusted > 0:
                    sh = min(
                        float(tr.target_shares_lot_adjusted),
                        math.floor(cap_sh / lot) * lot,
                    )
                else:
                    sh = (cash * tr.position_fraction) / denom
            else:
                sh = cash / denom
            if sh <= 0:
                n_entry_skip_zero += 1
                continue
            notional_b = sh * tr.entry_open
            fee_en = per_side_fee(notional_b, tr.fee_components)
            cash -= notional_b + fee_en
            shares = sh
            active = tr

        close_px = float(ohlc.loc[d]["Close"]) if d in ohlc.index else None
        if close_px is None:
            eq = cash
        else:
            eq = cash + shares * close_px
        equity_rows.append(
            {
                "date": d.isoformat(),
                "equity": eq,
                "cash": cash,
                "position_shares": shares,
                "close": close_px,
            }
        )

    final_equity = equity_rows[-1]["equity"] if equity_rows else cash
    ret = (final_equity - initial_cash) / initial_cash if initial_cash else 0.0

    wins = sum(1 for t in trades_out if t["gross_pnl"] > 0)
    ntr = len(trades_out)
    win_rate = wins / ntr if ntr else None

    # max drawdown on equity series
    peak = float("-inf")
    mdd = 0.0
    for er in equity_rows:
        eq = float(er["equity"])
        peak = max(peak, eq)
        if peak > 0:
            dd = (peak - eq) / peak
            mdd = max(mdd, dd)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if output_subdir:
        sub = output_subdir
    elif mode == "execution_bridge_v1":
        sub = f"bt_exec_bridge_v1_{ts}"
    else:
        sub = f"bt_{ts}"
    out_dir = bd / "backtest" / sub
    out_dir.mkdir(parents=True, exist_ok=True)

    trades_path = out_dir / "trades.csv"
    with open(trades_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "trade_id",
                "run_id",
                "signal_date",
                "asset_type",
                "entry_date",
                "exit_date",
                "entry_price_open",
                "exit_price_open",
                "shares",
                "gross_pnl",
                "fee_entry",
                "fee_exit",
                "fees",
                "execution_action",
                "sizing_mode",
                "target_shares_lot_adjusted",
                "position_fraction_spec",
            ],
        )
        w.writeheader()
        for t in trades_out:
            w.writerow(t)

    bridge_execution = None
    if mode == "execution_bridge_v1":
        bridge_execution = {
            "num_buy_skipped_bridge_no_spec": n_bridge_skip_spec,
            "num_buy_skipped_bridge_execution_action": n_bridge_skip_exec_action,
            "num_buy_skipped_bridge_zero_sizing": n_bridge_skip_sizing,
            "num_entry_skipped_zero_shares": n_entry_skip_zero,
        }

    metrics: Dict[str, Any] = {
        "execution_mode": mode,
        "bridge_execution": bridge_execution,
        "fee_snapshot_version": FEE_SNAPSHOT_VERSION,
        "fee_snapshot_as_of": FEE_SNAPSHOT_AS_OF,
        "symbol": symbol,
        "initial_cash": initial_cash,
        "final_equity": final_equity,
        "total_return": ret,
        "num_trades": ntr,
        "num_buy_signals": n_buy,
        "num_sell_signals": n_sell,
        "num_hold_signals": n_hold,
        "num_null_or_other_signals": n_null,
        "num_buy_skipped_overlap": n_overlap_skip,
        "num_buy_skipped_missing_prices": n_data_skip,
        "num_signals_ignored_by_protocol": num_ignored,
        "unknown_asset_fee_fallback_signal_count": unknown_fallback_signals,
        "unknown_asset_fee_fallback_trade_count": unknown_fallback_trades,
        "win_rate": win_rate,
        "max_drawdown": mdd,
        "rules": {
            "entry": "next_trading_day_open_after_signal_date",
            "exit": f"open_after_{hold_n}_sessions_hold_then_next_open",
            "hold_sessions": hold_n,
            "exit_lag_sessions": hold_n,
            "long_only": True,
            "sell_ignored": True,
            "execution_mode": mode,
            "fractional_shares": mode == "signal_only",
            "execution_bridge_v1_note": (
                "optional branch: execution_spec / order_spec.v2 / decision.json+synthetic"
                if mode == "execution_bridge_v1"
                else None
            ),
        },
        "fee_model": fee_model_meta,
        "data_source": "yfinance",
    }

    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    eq_path = out_dir / "equity_curve.csv"
    with open(eq_path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["date", "equity", "cash", "position_shares", "close"])
        wr.writeheader()
        for er in equity_rows:
            wr.writerow(er)

    summary_path = out_dir / "backtest_summary.md"
    summary_path.write_text(
        _render_summary(
            metrics=metrics,
            fee_model=fee_model_meta,
            trades_count=ntr,
        ),
        encoding="utf-8",
    )

    return TimelineBacktestResult(
        output_dir=out_dir.resolve(),
        trades_path=trades_path.resolve(),
        metrics_path=metrics_path.resolve(),
        equity_curve_path=eq_path.resolve(),
        summary_path=summary_path.resolve(),
    )


def _render_summary(
    *,
    metrics: Dict[str, Any],
    fee_model: Dict[str, Any],
    trades_count: int,
) -> str:
    rules = metrics.get("rules") or {}
    h = int(rules.get("hold_sessions") or EXIT_LAG_SESSIONS)
    em = metrics.get("execution_mode") or "signal_only"
    lines = [
        "# Backtest summary",
        "",
        "## Execution protocol (v1)",
        "",
        f"- **execution_mode**: `{em}` (`signal_only` = formal signal-level protocol; `execution_bridge_v1` = optional branch).",
        "- Long-only; **BUY** opens; **SELL** / **HOLD** / missing action: no new position.",
        "- Entry: **next trading day open** after `analysis_date`.",
        f"- Hold **{h}** full HK sessions; exit at **open** of the **{h + 1}th** trading day after entry.",
        "- Overlapping **BUY** while still in position: skipped.",
    ]
    if em == "signal_only":
        lines.append("- Fractional shares; full cash deployment per trade; no board-lot step.")
    else:
        lines.append(
            "- **execution_bridge_v1**: plans trades only when `execution_action == BUY_NEXT_OPEN`; "
            "sizes with `target_shares_lot_adjusted` (capped by cash, floored to lot) or `position_fraction`."
        )
        be = metrics.get("bridge_execution")
        if be:
            lines.append(f"- Bridge skip counts: `{be}`.")
    lines.extend(
        [
            "",
            "## Fee model",
            "",
            f"- Snapshot: **`{metrics.get('fee_snapshot_version')}`** as of **`{metrics.get('fee_snapshot_as_of')}`** (fixed for reproducibility).",
            "- **Official-style components** (rates frozen in repo; verify against HKEX/SFC/AFRC schedules for your report): stamp duty, SFC levy, FRC/AFRC levy, exchange trading fee.",
            "- **Configurable assumption**: `broker_platform_fee` (not an exchange rule).",
            "- **hk_etf**: `stamp_duty = 0` (listed ETF secondary market exemption in snapshot).",
            "- **unknown** asset_type: fee schedule falls back to **hk_equity**; see `unknown_asset_fee_fallback_signal_count` in metrics.",
            "",
            "### Component table (equity vs ETF)",
            "",
            _fee_table(fee_model),
            "",
            "## Results",
            "",
            f"- Trades executed: **{trades_count}**",
            f"- Final equity: **{metrics.get('final_equity')}**",
            f"- Total return: **{metrics.get('total_return')}**",
            f"- Max drawdown (on daily equity): **{metrics.get('max_drawdown')}**",
            "",
            "## Limitations",
            "",
            "- Prices from **yfinance**; gaps/adjustments may differ from live brokerage.",
            "- No slippage model; open/close as reported.",
            "",
        ]
    )
    return "\n".join(lines)


def _fee_table(fee_model: Dict[str, Any]) -> str:
    blocks = []
    for label, key in (("hk_equity", "hk_equity"), ("hk_etf", "hk_etf")):
        comp = fee_model.get(key, {}).get("components", {})
        blocks.append(f"### {label}")
        for name, meta in comp.items():
            blocks.append(
                f"- **{name}**: rate={meta.get('rate')} ({meta.get('bps')} bps), "
                f"role={meta.get('role')}"
            )
    return "\n".join(blocks)
