"""
Multi-date pilot: one experiments/<run_id> per date + batch index under experiments/batches/<batch_id>/.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from stockbuddy.default_config import DEFAULT_CONFIG

from stockbuddy.experiments.artifacts import (
    experiments_root_path,
    new_run_id,
    write_buy_and_hold_experiment_bundle,
)
from stockbuddy.experiments.pilot import PilotResult, run_pilot


def new_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]


@dataclass(frozen=True)
class PilotRunRecord:
    run_id: str
    analysis_date: str
    run_dir: Path
    decision_path: Path
    action: Optional[str]
    asset_type: str


@dataclass(frozen=True)
class PilotTimelineResult:
    batch_id: str
    ticker: str
    batch_dir: Path
    index_path: Path
    meta_path: Path
    runs: List[PilotRunRecord]


def run_pilot_timeline(
    ticker: str,
    analysis_dates: List[str],
    config: Dict[str, Any],
    *,
    selected_analysts: Optional[List[str]] = None,
    debug: bool = False,
    entry: str = "timeline",
    batch_id: Optional[str] = None,
    pipeline_profile: str = "full_system",
) -> PilotTimelineResult:
    if not analysis_dates:
        raise ValueError("analysis_dates must be non-empty")
    if pipeline_profile not in ("full_system", "buy_and_hold", "single_agent"):
        raise ValueError(
            "pipeline_profile must be 'full_system', 'buy_and_hold', or 'single_agent'"
        )

    cfg = {**DEFAULT_CONFIG, **config, "pipeline_profile": pipeline_profile}
    bid = batch_id or new_batch_id()
    root = experiments_root_path(cfg)
    batch_dir = root / "batches" / bid
    batch_dir.mkdir(parents=True, exist_ok=True)

    runs: List[PilotRunRecord] = []
    lines: List[Dict[str, Any]] = []

    for i, analysis_date in enumerate(analysis_dates):
        if pipeline_profile == "buy_and_hold":
            run_id = new_run_id()
            run_dir = root / run_id
            started = datetime.now(timezone.utc).isoformat()
            write_buy_and_hold_experiment_bundle(
                run_dir=run_dir,
                run_id=run_id,
                ticker=ticker,
                analysis_date=analysis_date,
                config=cfg,
                entry=entry,
                started_at=started,
                finished_at=datetime.now(timezone.utc).isoformat(),
                is_first_timeline_date=(i == 0),
            )
            decision_path = run_dir / "decision.json"
            dec = json.loads(decision_path.read_text(encoding="utf-8"))
            rec = PilotRunRecord(
                run_id=run_id,
                analysis_date=analysis_date,
                run_dir=run_dir.resolve(),
                decision_path=decision_path,
                action=dec.get("action"),
                asset_type=str(dec.get("asset_type") or "unknown"),
            )
        else:
            pr: PilotResult = run_pilot(
                ticker,
                analysis_date,
                {**config, "pipeline_profile": pipeline_profile},
                selected_analysts=selected_analysts,
                debug=debug,
                entry=entry,
            )
            decision_path = pr.run_dir / "decision.json"
            dec = json.loads(decision_path.read_text(encoding="utf-8"))
            rec = PilotRunRecord(
                run_id=pr.run_id,
                analysis_date=analysis_date,
                run_dir=pr.run_dir,
                decision_path=decision_path,
                action=dec.get("action"),
                asset_type=str(dec.get("asset_type") or "unknown"),
            )
        runs.append(rec)
        lines.append(
            {
                "batch_id": bid,
                "run_id": rec.run_id,
                "ticker": ticker,
                "analysis_date": analysis_date,
                "experiment_dir": str(rec.run_dir),
                "decision_json": str(decision_path),
                "action": dec.get("action"),
                "direction_score": dec.get("direction_score"),
                "asset_type": dec.get("asset_type"),
                "confidence": dec.get("confidence"),
                "parsed_action_pre_gate": dec.get("parsed_action_pre_gate"),
                "parsed_action_post_gate": dec.get("parsed_action_post_gate"),
                "news_status": dec.get("news_status"),
                "gate_summary": dec.get("gate_summary"),
                "blocked_by_risk_gate": dec.get("blocked_by_risk_gate"),
                "rationale_summary": dec.get("rationale_summary"),
                "status": "ok",
                "error": None,
            }
        )

    index_path = batch_dir / "decisions.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    meta_path = batch_dir / "batch_meta.json"
    meta: Dict[str, Any] = {
        "batch_id": bid,
        "ticker": ticker,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dates": list(analysis_dates),
        "entry": entry,
        "schema": "decisions.jsonl.v1",
        "pipeline_profile": pipeline_profile,
        "pipeline_version": "phase1",
    }
    snap = cfg.get("formal_eval_v1_snapshot")
    if snap:
        meta["formal_eval_v1"] = snap
    snap3 = cfg.get("formal_eval_v3_snapshot")
    if snap3:
        meta["formal_eval_v3"] = snap3
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return PilotTimelineResult(
        batch_id=bid,
        ticker=ticker,
        batch_dir=batch_dir.resolve(),
        index_path=index_path.resolve(),
        meta_path=meta_path.resolve(),
        runs=runs,
    )
