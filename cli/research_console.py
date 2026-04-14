"""
StockBuddy Research Console — task-focused terminal UI.

Usage:
    python -m cli.research_console <ticker> [date] [--profile single_agent|full_system]
    python -m cli.research_console --replay [run_dir]   # follow-up only, no API

Replay pack: experiments/demo_runs/research_console_demo (follow-up still needs API key for LLM).
Live: 0700 2024-06-03 --profile full_system
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Frozen replay pack (0700, full_system, G3 BUY→HOLD, full reports)
DEMO_REPLAY_REL = Path("experiments/demo_runs/research_console_demo")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ── rich imports ──────────────────────────────────────────────────────────────
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

import questionary

from cli.utils import QUESTIONARY_CYAN_MENU_STYLE, QUESTIONARY_CYAN_TEXT_STYLE

console = Console()

# ── Stage map: LangGraph node → (stage_key, friendly_label) ──────────────────
STAGE_MAP: Dict[str, tuple[str, str]] = {
    "Market Analyst":         ("market",       "Market Analysis"),
    "tools_market":           ("market",       "Market Analysis"),
    "Msg Clear Market":       ("market",       "Market Analysis"),
    "Fundamentals Analyst":   ("fundamentals", "Fundamentals Analysis"),
    "tools_fundamentals":     ("fundamentals", "Fundamentals Analysis"),
    "Msg Clear Fundamentals": ("fundamentals", "Fundamentals Analysis"),
    "Bull Researcher":        ("debate",       "Investment Debate"),
    "Bear Researcher":        ("debate",       "Investment Debate"),
    "Research Manager":       ("debate",       "Investment Debate"),
    "Trader":                 ("trade_plan",   "Trade Plan"),
    "Risky Analyst":          ("risk",         "Risk Assessment"),
    "Neutral Analyst":        ("risk",         "Risk Assessment"),
    "Safe Analyst":           ("risk",         "Risk Assessment"),
    "Risk Judge":             ("risk",         "Risk Assessment"),
}

STAGE_ORDER = ["market", "fundamentals", "debate", "trade_plan", "risk", "artifacts"]
STAGE_LABELS = {
    "market":       "Market Analysis",
    "fundamentals": "Fundamentals Analysis",
    "debate":       "Investment Debate",
    "trade_plan":   "Trade Plan",
    "risk":         "Risk Assessment",
    "artifacts":    "Artifacts",
}

ACTION_COLOR = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}


# ── Shared run state (updated from callback thread) ───────────────────────────
class RunState:
    def __init__(self, ticker: str, analysis_date: str, profile: str):
        self.ticker = ticker
        self.analysis_date = analysis_date
        self.profile = profile
        self.stages_done: set[str] = set()
        self.current_stage: Optional[str] = None
        self.nodes_seen: List[str] = []
        self.provisional_signal: Optional[str] = None
        self.risk_flags: List[str] = []
        self.gate_triggers: List[str] = []
        self.final_signal: Optional[str] = None
        self.artifacts_written = False
        self.run_dir: Optional[Path] = None
        self.error: Optional[str] = None
        self.done = False
        self._lock = threading.Lock()

    def on_node(self, node_name: str, partial_state: dict) -> None:
        with self._lock:
            stage_key, _ = STAGE_MAP.get(node_name, (None, node_name))
            if stage_key:
                self.stages_done.add(stage_key)
                self.current_stage = stage_key
            self.nodes_seen.append(node_name)
            # Extract provisional signal from trader/risk outputs
            ftd = partial_state.get("final_trade_decision") or ""
            if ftd and not self.final_signal:
                sig = _parse_signal(ftd)
                if sig:
                    self.provisional_signal = sig

    def finalize(self, run_dir: Path, decision: dict) -> None:
        with self._lock:
            self.run_dir = run_dir
            self.final_signal = decision.get("action")
            self.risk_flags = decision.get("risk_flags") or []
            self.gate_triggers = decision.get("gate_triggers") or []
            self.stages_done.add("artifacts")
            self.artifacts_written = True
            self.done = True


def _parse_signal(text: str) -> Optional[str]:
    t = text.strip().upper()
    for s in ("BUY", "SELL", "HOLD"):
        if s in t[:80]:
            return s
    return None


# ── Rich UI builders ──────────────────────────────────────────────────────────

def _build_header(state: RunState) -> Panel:
    status = "[bold green]COMPLETE[/]" if state.done else "[bold yellow]RUNNING[/]"
    txt = (
        f"[bold cyan]StockBuddy Research Console[/]   "
        f"[white]Ticker:[/] [bold]{state.ticker}.HK[/]   "
        f"[white]Date:[/] [bold]{state.analysis_date}[/]   "
        f"[white]Profile:[/] [bold magenta]{state.profile}[/]   "
        f"{status}"
    )
    return Panel(txt, border_style="cyan", padding=(0, 1))


def _build_stages(state: RunState, profile: str) -> Panel:
    # Only show relevant stages for profile
    if profile == "buy_and_hold":
        visible = ["artifacts"]
    elif profile == "single_agent":
        visible = ["market", "artifacts"]
    else:
        visible = STAGE_ORDER

    rows = []
    for key in visible:
        label = STAGE_LABELS[key]
        if key in state.stages_done:
            icon = "[bold green]✓[/]"
            style = "green"
            note = "complete"
        elif key == state.current_stage:
            icon = "[bold yellow]⟳[/]"
            style = "yellow"
            note = "running…"
        else:
            icon = "[dim]○[/]"
            style = "dim"
            note = "waiting"
        rows.append(f"  {icon}  [{style}]{label:<26}[/]  [{style}]{note}[/]")

    body = "\n".join(rows) if rows else "  [dim]No LLM stages (buy_and_hold)[/]"
    return Panel(body, title="[bold]Stage Progress[/]", border_style="blue", padding=(0, 1))


def _build_stance(state: RunState) -> Panel:
    lines: List[str] = []

    # Pre-gate provisional
    if state.provisional_signal:
        c = ACTION_COLOR.get(state.provisional_signal, "white")
        lines.append(f"  Pre-gate signal : [{c}][bold]{state.provisional_signal}[/][/]")
    else:
        lines.append("  Pre-gate signal : [dim]pending…[/]")

    # Post-gate / final
    if state.final_signal:
        c = ACTION_COLOR.get(state.final_signal, "white")
        was_blocked = (
            state.provisional_signal
            and state.final_signal != state.provisional_signal
            and state.gate_triggers
        )
        note = f"  ← blocked by [{', '.join(state.gate_triggers)}]" if was_blocked else ""
        lines.append(f"  Final decision  : [{c}][bold]{state.final_signal}[/][/]{note}")
    else:
        lines.append("  Final decision  : [dim]pending…[/]")

    # Risk flags
    if state.risk_flags:
        flags = "  ".join(f"[yellow]{f}[/]" for f in state.risk_flags)
        lines.append(f"\n  Risk flags : {flags}")
    elif state.done:
        lines.append("\n  Risk flags : [dim]none[/]")

    # Gate triggers
    if state.gate_triggers:
        gates = "  ".join(f"[red]{g}[/]" for g in state.gate_triggers)
        lines.append(f"  Gates fired: {gates}")
    elif state.done:
        lines.append("  Gates fired: [green]none — signal passed all gates[/]")

    return Panel("\n".join(lines), title="[bold]Signal & Risk[/]", border_style="magenta", padding=(0, 1))


def _build_artifacts(state: RunState) -> Panel:
    ARTIFACTS = [
        ("market_report.md",       "Market Report"),
        ("fundamentals_report.md", "Fundamentals Report"),
        ("decision.json",          "Decision"),
        ("lineage.json",           "Lineage"),
        ("order_spec.json",        "Order Spec"),
    ]
    lines = []
    for fname, label in ARTIFACTS:
        if state.run_dir and (state.run_dir / fname).is_file():
            lines.append(f"  [green]✓[/]  {label:<28} [dim]{fname}[/]")
        else:
            lines.append(f"  [dim]○  {label:<28} {fname}[/]")
    return Panel("\n".join(lines), title="[bold]Artifacts[/]", border_style="green", padding=(0, 1))


def _render_layout(state: RunState, profile: str) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(_build_header(state), name="header", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(_build_stages(state, profile), name="stages"),
        Layout(name="right"),
    )
    layout["right"].split_column(
        Layout(_build_stance(state), name="stance"),
        Layout(_build_artifacts(state), name="artifacts"),
    )
    return layout


# ── Follow-up mode ────────────────────────────────────────────────────────────

def _load_artifact(run_dir: Path, name: str) -> Optional[Any]:
    p = run_dir / name
    if not p.is_file():
        return None
    try:
        if name.endswith(".json"):
            return json.loads(p.read_text(encoding="utf-8"))
        return p.read_text(encoding="utf-8")
    except Exception:
        return None


def _followup_select_instruction() -> str:
    # Same wording pattern as cli.utils select_research_depth / analyst menus
    return "\n- Use arrow keys to navigate\n- Press Enter to select"


def _build_research_context(
    run_dir: Path,
    decision: dict,
    *,
    ticker: str,
    analysis_date: str,
    profile: str,
    max_chars: int = 36000,
) -> str:
    """Single bundle for LLM: meta + JSON artifacts + reports/*.md + full_state excerpt."""
    parts: List[str] = []
    meta = {
        "ticker": ticker,
        "analysis_date": analysis_date,
        "pipeline_profile": profile,
        "run_dir": str(run_dir.resolve()),
    }
    parts.append("=== RUN CONTEXT ===\n" + json.dumps(meta, ensure_ascii=False, indent=2))
    parts.append(
        "\n=== decision.json ===\n"
        + json.dumps(decision, ensure_ascii=False, indent=2, default=str)
    )

    lin = _load_artifact(run_dir, "lineage.json")
    if isinstance(lin, dict):
        parts.append(
            "\n=== lineage.json ===\n"
            + json.dumps(lin, ensure_ascii=False, indent=2, default=str)
        )

    spec = _load_artifact(run_dir, "order_spec.json")
    if spec is not None:
        parts.append(
            "\n=== order_spec.json ===\n"
            + json.dumps(spec, ensure_ascii=False, indent=2, default=str)
        )

    rdir = run_dir / "reports"
    if rdir.is_dir():
        for p in sorted(rdir.glob("*.md")):
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            parts.append(f"\n=== reports/{p.name} ===\n{txt}")

    fs = _load_artifact(run_dir, "full_state.json")
    if isinstance(fs, dict):
        keys = (
            "market_report",
            "fundamentals_report",
            "sentiment_report",
            "news_report",
            "investment_plan",
            "trader_investment_plan",
            "final_trade_decision",
            "investment_debate_state",
            "risk_debate_state",
        )
        slim: Dict[str, Any] = {}
        for k in keys:
            if k not in fs:
                continue
            v = fs[k]
            if isinstance(v, str) and len(v) > 14000:
                slim[k] = v[:14000] + "\n... [truncated]"
            else:
                slim[k] = v
        parts.append(
            "\n=== full_state.json (selected keys) ===\n"
            + json.dumps(slim, ensure_ascii=False, indent=2, default=str)
        )

    sm = _load_artifact(run_dir, "summary.md")
    if isinstance(sm, str) and sm.strip():
        parts.append("\n=== summary.md ===\n" + sm)

    blob = "\n".join(parts)
    if len(blob) > max_chars:
        blob = blob[:max_chars] + "\n\n[CONTEXT TRUNCATED — see on-disk artifacts for full text]"
    return blob


def _followup_llm_answer(question: str, context: str, *, ticker: str, adate: str) -> str:
    """Every follow-up goes through LLM; context is the research bundle only."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_repo_root() / ".env")
    except ImportError:
        pass

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return (
            "Follow-up answers require `OPENROUTER_API_KEY` or `OPENAI_API_KEY` in your environment."
        )

    system = (
        "You are StockBuddy's research assistant. The user just finished a pipeline run.\n"
        "Answer ONLY using the research bundle below (decision, lineage, reports, full_state excerpts). "
        "If the bundle does not contain the answer, say so briefly. "
        "Cite which section you used (e.g. reports/market_report.md). "
        "Be concise; prefer bullets for multi-part answers. Max ~400 words."
    )
    user_msg = (
        f"Ticker: {ticker}.HK  Analysis date: {adate}\n\n"
        f"--- RESEARCH BUNDLE ---\n{context}\n--- END BUNDLE ---\n\n"
        f"User question:\n{question}"
    )

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        is_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
        llm = ChatOpenAI(
            model="openai/gpt-4o-mini" if is_openrouter else "gpt-4o-mini",
            base_url="https://openrouter.ai/api/v1" if is_openrouter else None,
            api_key=api_key,
            max_tokens=1200,
            timeout=90,
            default_headers={
                "HTTP-Referer": "https://github.com/KarenShark/StockBuddy",
                "X-Title": "StockBuddy",
            }
            if is_openrouter
            else {},
        )
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user_msg)])
        return str(resp.content or "").strip() or "(empty model response)"
    except Exception as e:
        return f"LLM error: {e}"


def _generate_suggested_questions(run_dir: Path, decision: dict, profile: str) -> List[str]:
    """Build context-aware follow-up questions from artifact content."""
    qs: List[str] = []
    gates = decision.get("gate_triggers") or []
    action = decision.get("action", "")
    pre_gate = decision.get("parsed_action_pre_gate", "")
    risk_flags = decision.get("risk_flags") or []

    if gates:
        qs.append(f"Why did gate {gates[0]} block the signal?")
    if action == "HOLD" and pre_gate == "BUY":
        qs.append("What would the order look like if the gate hadn't fired?")
    if risk_flags:
        qs.append(f"What triggered the risk flag '{risk_flags[0]}'?")

    mkt = _load_artifact(run_dir, "market_report.md")
    if mkt:
        qs.append("What was the market analyst's key argument?")

    fund = _load_artifact(run_dir, "fundamentals_report.md")
    if fund:
        qs.append("What did the fundamentals analysis show?")

    lin = _load_artifact(run_dir, "lineage.json")
    if lin and isinstance(lin, dict):
        qs.append("Walk me through the decision lineage.")

    if profile == "full_system":
        qs.append("How did the debate affect the final stance?")

    qs.append("What is the order spec?")

    # Deduplicate, cap at 6
    seen = set()
    final = []
    for q in qs:
        if q not in seen:
            seen.add(q)
            final.append(q)
        if len(final) == 6:
            break
    return final


# ── Replay-only (stable demo, no API) ─────────────────────────────────────────

def run_replay_followup(replay_dir: Path) -> None:
    """Skip pipeline; open artifact-grounded follow-up from an existing run_dir."""
    replay_dir = replay_dir.resolve()
    if not replay_dir.is_dir():
        console.print(f"[red]Not a directory:[/red] {replay_dir}")
        return
    meta_path = replay_dir / "run_meta.json"
    if not meta_path.is_file():
        console.print(f"[red]Missing run_meta.json under[/red] {replay_dir}")
        return

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    cfg_snap = _load_artifact(replay_dir, "config_snapshot.json")
    profile = "full_system"
    if isinstance(cfg_snap, dict):
        profile = str(cfg_snap.get("pipeline_profile") or profile)

    decision = _load_artifact(replay_dir, "decision.json") or {}
    ticker = str(meta.get("ticker") or "?")
    adate = str(meta.get("analysis_date") or "?")

    state = RunState(ticker, adate, profile)
    state.run_dir = replay_dir
    state.final_signal = decision.get("action")
    pre = decision.get("parsed_action_pre_gate")
    if pre:
        state.provisional_signal = str(pre).upper() if isinstance(pre, str) else pre
    state.risk_flags = decision.get("risk_flags") or []
    state.gate_triggers = decision.get("gate_triggers") or []
    for k in STAGE_ORDER:
        state.stages_done.add(k)
    state.artifacts_written = True
    state.done = True

    console.print()
    console.print(Panel(
        f"[bold cyan]Replay mode[/bold cyan] — no LLM run; artifacts from disk.\n"
        f"  [bold]{ticker}.HK[/bold]  ·  {adate}  ·  [magenta]{profile}[/magenta]\n"
        f"  [dim]{replay_dir}[/dim]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()
    run_followup_mode(state)


# ── Follow-up REPL ────────────────────────────────────────────────────────────

def run_followup_mode(state: RunState) -> None:
    run_dir = state.run_dir
    if not run_dir or not run_dir.is_dir():
        console.print("[red]No run directory found — cannot enter follow-up mode.[/red]")
        return

    decision = _load_artifact(run_dir, "decision.json") or {}
    profile = state.profile

    console.print()
    console.print(Rule("[bold cyan]Research Complete — Follow-up[/bold cyan]", style="cyan"))
    console.print()

    action = decision.get("action", "?")
    pre_gate = decision.get("parsed_action_pre_gate", "?")
    gates = decision.get("gate_triggers") or []
    c = ACTION_COLOR.get(str(action), "white")

    summary_parts = [f"  Final decision: [{c}][bold]{action}[/bold][/]"]
    if gates:
        summary_parts.append(
            f"  (pre-gate was [bold]{pre_gate}[/bold], blocked by [red]{', '.join(gates)}[/red])"
        )
    else:
        summary_parts.append("  (passed all gates)")
    console.print("\n".join(summary_parts))
    console.print(f"  Artifacts in: [dim]{run_dir}[/dim]")
    console.print()

    try:
        from dotenv import load_dotenv
        load_dotenv(_repo_root() / ".env")
    except ImportError:
        pass
    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        console.print(
            Panel(
                "[yellow]Follow-up Q&A needs OPENROUTER_API_KEY or OPENAI_API_KEY[/yellow] "
                "(same as main StockBuddy CLI).\n"
                f"Artifacts are on disk:\n[dim]{run_dir}[/dim]",
                border_style="yellow",
                title="[bold]Skipping LLM follow-up[/bold]",
            )
        )
        return

    context = _build_research_context(
        run_dir,
        decision,
        ticker=state.ticker,
        analysis_date=state.analysis_date,
        profile=profile,
    )

    console.print(
        Panel(
            "[dim]Menus match main CLI: [bold cyan]↑↓[/bold cyan] navigate, [bold cyan]Enter[/bold cyan] confirm. "
            "Each answer is from an LLM that only sees this run’s research bundle (reports + JSON).[/dim]",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()

    suggested = _generate_suggested_questions(run_dir, decision, profile)
    _CUSTOM = "__custom__"
    _QUIT = "__quit__"

    while True:
        choices: List[questionary.Choice] = [
            questionary.Choice(q, value=q) for q in suggested
        ]
        choices.append(questionary.Choice("✎ Type a custom question…", value=_CUSTOM))
        choices.append(questionary.Choice("Quit session", value=_QUIT))

        sel = questionary.select(
            "Select a follow-up question:",
            choices=choices,
            instruction=_followup_select_instruction(),
            style=QUESTIONARY_CYAN_MENU_STYLE,
        ).ask()

        if sel is None or sel == _QUIT:
            console.print("[dim]Session ended.[/dim]")
            break

        if sel == _CUSTOM:
            raw = questionary.text(
                "Your question:",
                style=QUESTIONARY_CYAN_TEXT_STYLE,
            ).ask()
            if not raw or not str(raw).strip():
                continue
            question = str(raw).strip()
        else:
            question = str(sel)

        console.print()
        console.print(Rule(f"[bold]{question}[/bold]", style="blue"))
        console.print()

        with console.status("[cyan]LLM (research bundle only)…[/cyan]", spinner="dots"):
            answer = _followup_llm_answer(
                question,
                context,
                ticker=state.ticker,
                adate=state.analysis_date,
            )

        try:
            console.print(Markdown(answer))
        except Exception:
            console.print(answer)
        console.print()


# ── Main research runner ──────────────────────────────────────────────────────

def run_research(ticker: str, analysis_date: str, profile: str) -> None:
    """Full pipeline: live UI → artifact writing → follow-up mode."""
    from dotenv import load_dotenv
    load_dotenv(_repo_root() / ".env")

    from stockbuddy.default_config import DEFAULT_CONFIG
    from stockbuddy.experiments.artifacts import (
        new_run_id,
        experiments_root_path,
        write_buy_and_hold_experiment_bundle,
    )
    from stockbuddy.experiments.pilot import run_pilot

    cfg: Dict[str, Any] = {
        **DEFAULT_CONFIG,
        "memory_enabled": False,
        "pipeline_profile": profile,
    }

    state = RunState(ticker, analysis_date, profile)
    result_holder: Dict[str, Any] = {}

    def callback(node_name: str, partial_state: dict) -> None:
        state.on_node(node_name, partial_state)

    def _run() -> None:
        try:
            if profile == "buy_and_hold":
                run_id = new_run_id()
                root = experiments_root_path(cfg)
                run_dir = root / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                started = datetime.now(timezone.utc).isoformat()
                write_buy_and_hold_experiment_bundle(
                    run_dir=run_dir,
                    run_id=run_id,
                    ticker=ticker,
                    analysis_date=analysis_date,
                    config=cfg,
                    entry="research_console",
                    started_at=started,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    is_first_timeline_date=True,
                )
                result_holder["run_dir"] = run_dir
                dec_path = run_dir / "decision.json"
                result_holder["decision"] = (
                    json.loads(dec_path.read_text(encoding="utf-8"))
                    if dec_path.is_file()
                    else {}
                )
            else:
                analysts = ["market", "fundamentals"]
                result = run_pilot(
                    ticker,
                    analysis_date,
                    cfg,
                    selected_analysts=analysts,
                    entry="research_console",
                    stream_callback=callback,
                )
                result_holder["run_dir"] = result.run_dir
                dec_path = result.run_dir / "decision.json"
                result_holder["decision"] = (
                    json.loads(dec_path.read_text(encoding="utf-8")) if dec_path.is_file() else {}
                )
        except Exception as e:
            import traceback
            result_holder["error"] = traceback.format_exc()
            state.error = str(e)
        finally:
            state.done = True

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    with Live(console=console, refresh_per_second=4, screen=False) as live:
        while not state.done:
            live.update(_render_layout(state, profile))
            threading.Event().wait(0.25)

        if result_holder.get("run_dir"):
            state.finalize(result_holder["run_dir"], result_holder.get("decision", {}))
        elif state.error:
            state.done = True

        live.update(_render_layout(state, profile))

    thread.join(timeout=5)

    if state.error:
        console.print(f"\n[red]Pipeline error:[/red] {state.error}")
        return

    # Enter follow-up mode
    run_followup_mode(state)


# ── CLI entry ─────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        demo_default = _repo_root() / DEMO_REPLAY_REL
        console.print(
            "[bold cyan]StockBuddy Research Console[/bold cyan]\n\n"
            "Usage:\n"
            "  [bold]python -m cli.research_console <ticker> [date] [--profile P][/bold]\n"
            "  [bold]python -m cli.research_console --replay [run_dir][/bold]\n\n"
            "  ticker   HK ticker (e.g. 0700)\n"
            "  date     Analysis date YYYY-MM-DD (default: today)\n"
            "  --profile  buy_and_hold | single_agent | full_system (default: full_system)\n\n"
            "[bold]Stable demo (no API, follow-up only):[/bold]\n"
            f"  python -m cli.research_console --replay\n"
            f"  → uses [dim]{demo_default}[/dim]\n\n"
            "[bold]Live full pipeline (needs OPENROUTER_API_KEY):[/bold]\n"
            "  python -m cli.research_console 0700 2024-06-03 --profile full_system\n\n"
            "[bold]Smoke (no API, instant BUY baseline):[/bold]\n"
            "  python -m cli.research_console 0700 2024-06-03 --profile buy_and_hold\n"
        )
        return 0

    if argv[0] == "--replay":
        rd = argv[1] if len(argv) > 1 else str(_repo_root() / DEMO_REPLAY_REL)
        run_replay_followup(Path(rd).expanduser())
        return 0

    ticker = argv[0] if len(argv[0]) <= 4 and argv[0].isdigit() else argv[0]

    analysis_date = date.today().isoformat()
    profile = "full_system"

    i = 1
    while i < len(argv):
        if argv[i] == "--profile" and i + 1 < len(argv):
            profile = argv[i + 1]
            i += 2
        elif not argv[i].startswith("--"):
            analysis_date = argv[i]
            i += 1
        else:
            i += 1

    if profile not in ("buy_and_hold", "single_agent", "full_system"):
        console.print(f"[red]Unknown profile: {profile}[/red]")
        return 1

    console.print()
    console.print(Panel(
        f"[bold cyan]StockBuddy Research Console[/bold cyan]\n"
        f"  Ticker [bold]{ticker}.HK[/bold]  ·  Date [bold]{analysis_date}[/bold]  ·  Profile [bold magenta]{profile}[/bold magenta]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()

    run_research(ticker, analysis_date, profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
