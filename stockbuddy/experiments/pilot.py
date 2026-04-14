"""
Minimal pilot runner: one graph propagate + canonical experiment bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from stockbuddy.default_config import DEFAULT_CONFIG
from stockbuddy.graph.trading_graph import StockBuddyGraph

from stockbuddy.experiments.artifacts import (
    experiments_root_path,
    new_run_id,
    write_experiment_bundle,
)


@dataclass(frozen=True)
class PilotResult:
    run_dir: Path
    final_state: Dict[str, Any]
    decision: str
    run_id: str


def run_pilot(
    ticker: str,
    analysis_date: str,
    config: Dict[str, Any],
    *,
    selected_analysts: Optional[List[str]] = None,
    debug: bool = False,
    entry: str = "main",
    stream_callback=None,
) -> PilotResult:
    run_id = new_run_id()
    cfg = {**DEFAULT_CONFIG, **config}
    root = experiments_root_path(cfg)
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()

    analysts = selected_analysts or ["market", "social", "news", "fundamentals"]
    graph = StockBuddyGraph(selected_analysts=analysts, debug=debug, config=cfg)
    final_state, decision = graph.propagate(ticker, analysis_date, stream_callback=stream_callback)

    finished = datetime.now(timezone.utc).isoformat()

    write_experiment_bundle(
        run_dir=run_dir,
        run_id=run_id,
        ticker=ticker,
        analysis_date=analysis_date,
        final_state=final_state,
        signal_str=str(decision),
        config=cfg,
        entry=entry,
        started_at=started,
        finished_at=finished,
    )

    return PilotResult(
        run_dir=run_dir.resolve(),
        final_state=final_state,
        decision=str(decision),
        run_id=run_id,
    )
