"""
Tier-1 pilot aggregates: behavior, risk/gates, process+lineage reliability.
Reads batch `decisions.jsonl` + per-run `decision.json` / `lineage.json` on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LINEAGE_KEYS_REQUIRED = (
    "report_paths",
    "signal_raw",
    "parsed_action_pre_gate",
    "parsed_action_post_gate",
    "gate_triggers",
    "order_spec_path",
)

CORE_ARTIFACTS = ("decision.json", "full_state.json", "lineage.json")


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_action_jsonl(a: Any) -> Optional[str]:
    if a is None:
        return None
    t = str(a).strip().upper()
    if t in ("BUY", "SELL", "HOLD"):
        return t
    return None


def _evaluate_run_process(run_dir: Path, lineage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    core = {name: (run_dir / name).is_file() for name in CORE_ARTIFACTS}
    order_spec_ok = (run_dir / "order_spec.json").is_file()
    lineage_keys_ok: Dict[str, bool] = {}
    report_hits = 0
    report_miss: List[str] = []
    if lineage:
        for k in LINEAGE_KEYS_REQUIRED:
            lineage_keys_ok[k] = k in lineage
        rp = lineage.get("report_paths")
        if isinstance(rp, dict) and rp:
            for _k, rel in rp.items():
                p = run_dir / str(rel)
                if p.is_file():
                    report_hits += 1
                else:
                    report_miss.append(str(rel))
    lineage_score = (
        sum(1 for v in lineage_keys_ok.values() if v) / len(LINEAGE_KEYS_REQUIRED)
        if lineage_keys_ok
        else 0.0
    )
    n_reports = len(lineage.get("report_paths") or {}) if lineage else 0
    report_coverage = 1.0 if n_reports == 0 else report_hits / max(n_reports, 1)
    return {
        "core_artifacts": core,
        "core_artifacts_complete": all(core.values()),
        "order_spec_present": order_spec_ok,
        "lineage_keys_present": lineage_keys_ok,
        "lineage_key_score": lineage_score,
        "report_paths_listed": n_reports,
        "report_files_found": report_hits,
        "report_paths_missing": report_miss,
        "report_file_score": report_coverage,
    }


def _evaluate_one_row(
    row: Dict[str, Any],
    *,
    pipeline_profile: str,
) -> Dict[str, Any]:
    exp = row.get("experiment_dir")
    run_dir = Path(str(exp)) if exp else Path(".")
    dj = row.get("decision_json")
    dec_path = Path(str(dj)) if dj else run_dir / "decision.json"
    status = row.get("status")
    err = row.get("error")

    jsonl_action = _parse_action_jsonl(row.get("action"))
    malformed_jsonl_action = jsonl_action is None and row.get("action") is not None

    dec = _load_json(dec_path) if dec_path.is_file() else None
    decision_parse_ok = dec is not None
    dec_action = _parse_action_jsonl(dec.get("action")) if dec else None
    mismatch = (
        decision_parse_ok
        and jsonl_action is not None
        and dec_action is not None
        and jsonl_action != dec_action
    )

    triggers: List[str] = []
    pre = post = None
    risk_n = 0
    buy_to_hold = False
    any_gate_hit = False
    if dec:
        triggers = list(dec.get("gate_triggers") or [])
        if not isinstance(triggers, list):
            triggers = []
        any_gate_hit = len(triggers) > 0
        pre = dec.get("parsed_action_pre_gate")
        post = dec.get("parsed_action_post_gate")
        if isinstance(pre, str) and isinstance(post, str):
            buy_to_hold = pre.upper() == "BUY" and post.upper() == "HOLD"
        rf = dec.get("risk_flags")
        if isinstance(rf, list):
            risk_n = len(rf)

    lin_path = run_dir / "lineage.json"
    lineage = _load_json(lin_path) if lin_path.is_file() else None
    proc = _evaluate_run_process(run_dir, lineage)

    return {
        "run_id": row.get("run_id"),
        "analysis_date": row.get("analysis_date"),
        "jsonl_status": status,
        "jsonl_error": err,
        "run_success_jsonl": status == "ok",
        "jsonl_action": jsonl_action,
        "malformed_jsonl_action": malformed_jsonl_action,
        "decision_path": str(dec_path),
        "decision_parse_ok": decision_parse_ok,
        "decision_action": dec_action,
        "jsonl_vs_decision_action_mismatch": mismatch,
        "gate_triggers": triggers,
        "any_gate_triggered": any_gate_hit,
        "buy_to_hold_via_gate": buy_to_hold,
        "risk_flags_count": risk_n,
        "process": proc,
    }


def evaluate_batch_dir(batch_dir: Path) -> Dict[str, Any]:
    bd = Path(batch_dir)
    meta_path = bd / "batch_meta.json"
    meta = _load_json(meta_path) if meta_path.is_file() else {}
    profile = str(meta.get("pipeline_profile") or "unknown")
    ticker = str(meta.get("ticker") or "unknown")
    jsonl_path = bd / "decisions.jsonl"
    if not jsonl_path.is_file():
        return {
            "batch_dir": str(bd.resolve()),
            "batch_id": meta.get("batch_id"),
            "ticker": ticker,
            "pipeline_profile": profile,
            "error": "missing_decisions_jsonl",
        }

    rows = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    per_run = [_evaluate_one_row(r, pipeline_profile=profile) for r in rows]

    n = len(per_run)
    n_ok = sum(1 for x in per_run if x["run_success_jsonl"])
    n_mal = sum(1 for x in per_run if x["malformed_jsonl_action"])
    n_dec_fail = sum(1 for x in per_run if not x["decision_parse_ok"])
    n_mm = sum(1 for x in per_run if x["jsonl_vs_decision_action_mismatch"])

    act_c = Counter(x["jsonl_action"] for x in per_run if x["jsonl_action"])

    gate_counter: Counter[str] = Counter()
    for x in per_run:
        for g in x["gate_triggers"]:
            if isinstance(g, str):
                gate_counter[g] += 1

    buy_to_hold_n = sum(1 for x in per_run if x["buy_to_hold_via_gate"])
    any_gate_n = sum(1 for x in per_run if x["any_gate_triggered"])
    risk_counts = [x["risk_flags_count"] for x in per_run]

    proc_scores = [x["process"]["lineage_key_score"] for x in per_run]
    core_ok_frac = sum(1 for x in per_run if x["process"]["core_artifacts_complete"]) / n if n else 0.0

    return {
        "batch_dir": str(bd.resolve()),
        "batch_id": meta.get("batch_id"),
        "ticker": ticker,
        "pipeline_profile": profile,
        "n_runs": n,
        "behavior": {
            "action_counts_jsonl": dict(act_c),
            "buy_ratio": (act_c.get("BUY", 0) / n) if n else 0.0,
            "sell_ratio": (act_c.get("SELL", 0) / n) if n else 0.0,
            "hold_ratio": (act_c.get("HOLD", 0) / n) if n else 0.0,
            "null_or_malformed_ratio": (n_mal / n) if n else 0.0,
        },
        "risk": {
            "runs_with_any_gate_trigger": any_gate_n,
            "gate_trigger_rate_per_run": (any_gate_n / n) if n else 0.0,
            "gate_breakdown": dict(gate_counter),
            "buy_to_hold_after_gate_count": buy_to_hold_n,
            "risk_flags_per_decision": {
                "mean": sum(risk_counts) / n if n else 0.0,
                "max": max(risk_counts) if risk_counts else 0,
            },
        },
        "process_reliability": {
            "run_success_rate_jsonl": (n_ok / n) if n else 0.0,
            "decision_json_parse_failures": n_dec_fail,
            "jsonl_vs_decision_action_mismatch_count": n_mm,
            "core_artifacts_all_present_rate": core_ok_frac,
            "mean_lineage_key_score": sum(proc_scores) / n if n else 0.0,
        },
        "runs": per_run,
    }


def tier1_from_snapshot(snapshot_path: Path) -> Dict[str, Any]:
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    cells = snap.get("cells") or []
    batches = [Path(c["batch_dir"]) for c in cells if c.get("batch_dir")]
    return tier1_from_batch_dirs(batches, source_snapshot=str(snapshot_path.resolve()))


def tier1_from_batch_dirs(
    batch_dirs: List[Path],
    *,
    source_snapshot: Optional[str] = None,
) -> Dict[str, Any]:
    by_batch = [evaluate_batch_dir(bd) for bd in batch_dirs]

    total_runs = sum(b.get("n_runs", 0) or 0 for b in by_batch if "n_runs" in b)
    agg_act: Counter[str] = Counter()
    gate_all: Counter[str] = Counter()
    ok_runs = 0
    mal_runs = 0
    dec_fail = 0
    mm = 0
    any_gate_runs = 0
    b2h = 0
    risk_sum = 0.0
    lineage_scores: List[float] = []
    core_frac_sum = 0.0
    n_batches = len(by_batch)

    for b in by_batch:
        if b.get("error"):
            continue
        beh = b.get("behavior") or {}
        for k, v in (beh.get("action_counts_jsonl") or {}).items():
            agg_act[k] += int(v)
        rk = b.get("risk") or {}
        for g, c in (rk.get("gate_breakdown") or {}).items():
            gate_all[g] += int(c)
        n = int(b.get("n_runs") or 0)
        pr = b.get("process_reliability") or {}
        runs = b.get("runs") or []
        ok_runs += sum(1 for r in runs if r.get("run_success_jsonl"))
        mal_runs += sum(1 for r in runs if r.get("malformed_jsonl_action"))
        dec_fail += int(pr.get("decision_json_parse_failures") or 0)
        mm += int(pr.get("jsonl_vs_decision_action_mismatch_count") or 0)
        any_gate_runs += int(rk.get("runs_with_any_gate_trigger") or 0)
        b2h += int(rk.get("buy_to_hold_after_gate_count") or 0)
        rf = rk.get("risk_flags_per_decision") or {}
        risk_sum += float(rf.get("mean", 0)) * n
        lineage_scores.append(float(pr.get("mean_lineage_key_score") or 0))
        core_frac_sum += float(pr.get("core_artifacts_all_present_rate") or 0)

    return {
        "tier": "process_behavior_risk_tier1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": source_snapshot,
        "aggregate": {
            "n_batches": n_batches,
            "n_runs_total": total_runs,
            "behavior": {
                "action_counts_jsonl": dict(agg_act),
                "buy_ratio": (agg_act.get("BUY", 0) / total_runs) if total_runs else 0.0,
                "sell_ratio": (agg_act.get("SELL", 0) / total_runs) if total_runs else 0.0,
                "hold_ratio": (agg_act.get("HOLD", 0) / total_runs) if total_runs else 0.0,
                "malformed_jsonl_action_runs": mal_runs,
            },
            "risk": {
                "runs_with_any_gate_trigger": any_gate_runs,
                "gate_trigger_rate_per_run": (any_gate_runs / total_runs) if total_runs else 0.0,
                "gate_breakdown": dict(gate_all),
                "buy_to_hold_after_gate_count": b2h,
                "mean_risk_flags_per_decision": (risk_sum / total_runs) if total_runs else 0.0,
            },
            "process_reliability": {
                "run_success_rate_jsonl": (ok_runs / total_runs) if total_runs else 0.0,
                "decision_json_parse_failures": dec_fail,
                "jsonl_vs_decision_action_mismatch_count": mm,
                "mean_batch_core_artifact_rate": (core_frac_sum / n_batches) if n_batches else 0.0,
                "mean_batch_lineage_key_score": (sum(lineage_scores) / n_batches)
                if n_batches
                else 0.0,
            },
        },
        "by_profile": _rollup_by_profile(by_batch),
        "batches": by_batch,
    }


def _rollup_by_profile(batches: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in batches:
        if b.get("error"):
            continue
        by_p[str(b.get("pipeline_profile"))].append(b)
    out: Dict[str, Any] = {}
    for prof, lst in by_p.items():
        nr = sum(int(x.get("n_runs") or 0) for x in lst)
        ac: Counter[str] = Counter()
        for x in lst:
            for k, v in (x.get("behavior") or {}).get("action_counts_jsonl", {}).items():
                ac[k] += int(v)
        g: Counter[str] = Counter()
        ag = 0
        b2h = 0
        for x in lst:
            rk = x.get("risk") or {}
            ag += int(rk.get("runs_with_any_gate_trigger") or 0)
            b2h += int(rk.get("buy_to_hold_after_gate_count") or 0)
            for gg, c in (rk.get("gate_breakdown") or {}).items():
                g[gg] += int(c)
        out[prof] = {
            "n_batches": len(lst),
            "n_runs": nr,
            "action_counts": dict(ac),
            "gate_breakdown": dict(g),
            "runs_with_any_gate": ag,
            "buy_to_hold_count": b2h,
        }
    return out


def export_sensitivity_report_tables(
    sensitivity_json_path: Path,
    *,
    out_csv: Path,
    out_json: Path,
) -> Dict[str, Any]:
    """
    Wide table: one row per (ticker, profile); columns hold3/5/10 × return|mdd|trades.
    For report / slides; no re-fetch.
    """
    raw = json.loads(Path(sensitivity_json_path).read_text(encoding="utf-8"))
    rows = raw.get("rows") or []
    wide: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in rows:
        tk = str(r.get("ticker", ""))
        pr = str(r.get("profile", ""))
        key = (tk, pr)
        if key not in wide:
            wide[key] = {"ticker": tk, "profile": pr}
        h = int(r["hold_sessions"])
        prefix = f"hold_{h}"
        if r.get("error"):
            wide[key][f"{prefix}_total_return"] = None
            wide[key][f"{prefix}_max_drawdown"] = None
            wide[key][f"{prefix}_num_trades"] = None
            wide[key][f"{prefix}_error"] = r.get("error")
        else:
            wide[key][f"{prefix}_total_return"] = r.get("total_return")
            wide[key][f"{prefix}_max_drawdown"] = r.get("max_drawdown")
            wide[key][f"{prefix}_num_trades"] = r.get("num_trades")

    ordered = sorted(wide.values(), key=lambda x: (x["ticker"], x["profile"]))
    headers = ["ticker", "profile"]
    for h in (3, 5, 10):
        headers.extend(
            [
                f"hold_{h}_total_return",
                f"hold_{h}_max_drawdown",
                f"hold_{h}_num_trades",
            ]
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        import csv

        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for row in ordered:
            w.writerow({k: row.get(k, "") for k in headers})

    payload = {
        "source": str(sensitivity_json_path.resolve()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "description_zh": "协议敏感性：同一 decisions.jsonl，仅持有 3/5/10 个港股交易日后平仓；列可直接进 report。",
        "columns": headers,
        "rows": ordered,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_protocol_sensitivity(
    snapshot_path: Path,
    hold_sessions: Tuple[int, ...] = (3, 5, 10),
    *,
    config_merge: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from stockbuddy.evaluation.timeline_backtest import run_timeline_backtest
    from stockbuddy.experiments.formal_eval_v1 import formal_eval_v1_merged_config

    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    cells = snap.get("cells") or []
    cfg = formal_eval_v1_merged_config(config_merge or {})

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows: List[Dict[str, Any]] = []
    for cell in cells:
        bd = Path(cell["batch_dir"])
        ticker = cell.get("ticker")
        profile = cell.get("profile")
        for h in hold_sessions:
            sub = f"sens_hold{h}_{stamp}_{ticker}_{profile}"
            try:
                bt = run_timeline_backtest(
                    batch_dir=bd,
                    config=cfg,
                    exit_lag_sessions=h,
                    output_subdir=sub,
                )
                m = json.loads(bt.metrics_path.read_text(encoding="utf-8"))
                rows.append(
                    {
                        "ticker": ticker,
                        "profile": profile,
                        "hold_sessions": h,
                        "batch_dir": str(bd.resolve()),
                        "backtest_dir": str(bt.output_dir),
                        "metrics_path": str(bt.metrics_path),
                        "total_return": m.get("total_return"),
                        "num_trades": m.get("num_trades"),
                        "max_drawdown": m.get("max_drawdown"),
                        "num_signals_ignored_by_protocol": m.get(
                            "num_signals_ignored_by_protocol"
                        ),
                    }
                )
            except Exception as e:
                rows.append(
                    {
                        "ticker": ticker,
                        "profile": profile,
                        "hold_sessions": h,
                        "batch_dir": str(bd.resolve()),
                        "error": repr(e),
                    }
                )

    return {
        "kind": "protocol_sensitivity_hold_sessions",
        "hold_sessions_tried": list(hold_sessions),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": str(snapshot_path.resolve()),
        "rows": rows,
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Pilot tier1 + protocol sensitivity")
    sub = p.add_subparsers(dest="cmd", required=True)

    t1 = sub.add_parser("tier1", help="Behavior + risk + process from snapshot")
    t1.add_argument("--snapshot", type=Path, required=True)
    t1.add_argument("--out", type=Path, help="Write JSON here")

    s2 = sub.add_parser("sensitivity", help="Re-backtest same decisions.jsonl with 3/5/10 sessions")
    s2.add_argument("--snapshot", type=Path, required=True)
    s2.add_argument("--out", type=Path, required=True)
    s2.add_argument(
        "--holds",
        type=str,
        default="3,5,10",
        help="Comma-separated hold session counts (HK trading days)",
    )

    st = sub.add_parser(
        "sensitivity-table",
        help="Export wide CSV+JSON from existing protocol_sensitivity JSON",
    )
    st.add_argument("--in-json", type=Path, required=True, dest="in_json")
    st.add_argument("--out-csv", type=Path, required=True)
    st.add_argument("--out-json", type=Path, required=True)

    args = p.parse_args(argv)
    if args.cmd == "tier1":
        report = tier1_from_snapshot(args.snapshot)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(args.out)
        else:
            print(text)
        return 0

    if args.cmd == "sensitivity":
        holds = tuple(int(x.strip()) for x in args.holds.split(",") if x.strip())
        rep = run_protocol_sensitivity(args.snapshot, hold_sessions=holds)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(args.out)
        return 0

    if args.cmd == "sensitivity-table":
        export_sensitivity_report_tables(
            args.in_json,
            out_csv=args.out_csv,
            out_json=args.out_json,
        )
        print(args.out_csv)
        print(args.out_json)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
