"""Post-analyze follow-up: LLM-suggested questions + bundle-grounded answers (English UI/output)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import questionary
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from cli.utils import (
    CLI_ACCENT,
    CLI_BORDER,
    QUESTIONARY_CYAN_MENU_STYLE,
    QUESTIONARY_CYAN_TEXT_STYLE,
    console,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _followup_instruction() -> str:
    return "\n- ↑↓ navigate · Enter to confirm"


def build_analyze_bundle(
    final_state: Dict[str, Any],
    report_dir: Path,
    selections: Dict[str, Any],
    decision: Any,
    max_chars: int = 36000,
) -> str:
    parts: List[str] = []
    meta = {
        "ticker": selections["ticker"],
        "analysis_date": selections["analysis_date"],
        "source": "cli.analyze",
    }
    parts.append("=== RUN CONTEXT ===\n" + json.dumps(meta, ensure_ascii=False, indent=2))
    sig = {"llm_extracted_action": str(decision).strip() if decision is not None else ""}
    parts.append("\n=== signal (process_signal) ===\n" + json.dumps(sig, indent=2))

    keys = (
        "market_report",
        "sentiment_report",
        "news_report",
        "fundamentals_report",
        "investment_plan",
        "trader_investment_plan",
        "final_trade_decision",
    )
    slim: Dict[str, Any] = {}
    for k in keys:
        v = final_state.get(k)
        if not v:
            continue
        if isinstance(v, str) and len(v) > 14000:
            slim[k] = v[:14000] + "\n... [truncated]"
        else:
            slim[k] = v
    parts.append(
        "\n=== final_state (reports) ===\n"
        + json.dumps(slim, ensure_ascii=False, indent=2, default=str)
    )

    if report_dir.is_dir():
        for p in sorted(report_dir.glob("*.md")):
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            parts.append(f"\n=== {p.name} (disk) ===\n{txt}")

    blob = "\n".join(parts)
    if len(blob) > max_chars:
        blob = blob[:max_chars] + "\n\n[CONTEXT TRUNCATED]"
    return blob


def _llm_invoke(selections: Dict[str, Any], system: str, user: str, max_tokens: int) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv(_repo_root() / ".env")
    except ImportError:
        pass

    prov = str(selections.get("llm_provider", "")).lower()
    if prov == "openrouter":
        api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        base_url = (selections.get("backend_url") or "").strip() or "https://openrouter.ai/api/v1"
        headers = {
            "HTTP-Referer": "https://github.com/KarenShark/StockBuddy",
            "X-Title": "StockBuddy",
        }
    else:
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        base_url = None
        headers = {}

    if not api_key:
        raise RuntimeError("missing API key for selected provider")

    model = selections.get("shallow_thinker") or "gpt-4o-mini"

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_tokens=max_tokens,
        timeout=120,
        default_headers=headers,
    )
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return str(resp.content or "").strip()


def generate_followup_questions_llm(
    bundle: str, selections: Dict[str, Any]
) -> List[str]:
    system = (
        "You list follow-up questions after a stock research run. "
        "Output ONLY a JSON array of 4–6 short strings. Each string must be a question in English. "
        "No markdown fences, no commentary."
    )
    cap = min(28000, len(bundle))
    user = (
        "What might the user ask next? Focus on risks, contradictions between "
        "analysts, and concrete next steps. All questions in English.\n\n--- BUNDLE ---\n"
        f"{bundle[:cap]}\n--- END ---"
    )
    raw = _llm_invoke(selections, system, user, max_tokens=800)
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            out = [str(x).strip() for x in data if str(x).strip()]
            return out[:6]
    except json.JSONDecodeError:
        pass
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip().lstrip("-*").strip()
        ln = re.sub(r"^\d+[\).\s]+", "", ln)
        if len(ln) > 8:
            lines.append(ln)
    return lines[:6] if lines else _fallback_questions()


def _fallback_questions() -> List[str]:
    return [
        "Do the analyst conclusions align with the final signal? Where do they diverge?",
        "What are the main risks called out in the reports?",
        "If you could act on only one recommendation, what would it be?",
    ]


def followup_answer(
    question: str, bundle: str, selections: Dict[str, Any]
) -> str:
    ticker = selections["ticker"]
    adate = selections["analysis_date"]
    system = (
        "You are StockBuddy’s assistant (clear, direct). Answer ONLY from the research bundle. "
        "If missing, say briefly in English. Cite sections (e.g. final_trade_decision). "
        "Bullets OK. Max ~400 words. "
        "Write the entire answer in English, even if the user’s question is not in English."
    )
    user = (
        f"Ticker: {ticker}  Date: {adate}\n\n--- BUNDLE ---\n{bundle}\n--- END ---\n\nQ: {question}"
    )
    try:
        return _llm_invoke(selections, system, user, max_tokens=1200) or "(empty)"
    except Exception as e:
        return f"LLM error: {e}"


def _has_api_key(selections: Dict[str, Any]) -> bool:
    prov = str(selections.get("llm_provider", "")).lower()
    if prov == "openrouter":
        return bool((os.getenv("OPENROUTER_API_KEY") or "").strip())
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def run_analyze_followup(
    selections: Dict[str, Any],
    final_state: Dict[str, Any],
    decision: Any,
    report_dir: Path,
) -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_repo_root() / ".env")
    except ImportError:
        pass

    console.print()
    console.print(
        Rule(f"[{CLI_ACCENT}]Analysis complete · next step[/]", style=CLI_BORDER)
    )
    console.print()

    nxt = questionary.select(
        "Choose:",
        choices=[
            questionary.Choice(
                "Follow-up Q&A (English, grounded in this run’s reports)",
                value="followup",
            ),
            questionary.Choice("Exit", value="exit"),
        ],
        instruction=_followup_instruction(),
        style=QUESTIONARY_CYAN_MENU_STYLE,
    ).ask()

    if nxt != "followup":
        console.print(f"[{CLI_ACCENT}]Goodbye.[/]")
        return

    if not _has_api_key(selections):
        console.print(
            Panel(
                "Follow-up needs the same API key as the main run (OpenRouter / OpenAI).\n"
                f"Reports on disk: [dim]{report_dir}[/dim]",
                title="[bold]Skipping LLM follow-up[/bold]",
                border_style="yellow",
            )
        )
        return

    bundle = build_analyze_bundle(
        final_state, report_dir, selections, decision
    )

    suggested: List[str] = []
    with console.status(f"[{CLI_ACCENT}]Generating suggested questions…[/]", spinner="dots"):
        try:
            suggested = generate_followup_questions_llm(bundle, selections)
        except Exception:
            suggested = _fallback_questions()

    if not suggested:
        suggested = _fallback_questions()

    _CUSTOM = "__custom__"
    _QUIT = "__quit__"

    while True:
        choices: List[questionary.Choice] = [
            questionary.Choice(q, value=q) for q in suggested
        ]
        choices.append(questionary.Choice("✎ Type a custom question…", value=_CUSTOM))
        choices.append(questionary.Choice("End follow-up", value=_QUIT))

        sel = questionary.select(
            "Pick a question or type your own:",
            choices=choices,
            instruction=_followup_instruction(),
            style=QUESTIONARY_CYAN_MENU_STYLE,
        ).ask()

        if sel is None or sel == _QUIT:
            console.print(f"[{CLI_ACCENT}]Follow-up ended.[/]")
            break

        if sel == _CUSTOM:
            raw = questionary.text(
                "Your question (answer will be in English):",
                style=QUESTIONARY_CYAN_TEXT_STYLE,
            ).ask()
            if not raw or not str(raw).strip():
                continue
            question = str(raw).strip()
        else:
            question = str(sel)

        console.print()
        qdisp = question[:72] + ("…" if len(question) > 72 else "")
        console.print(Rule(f"[bold {CLI_ACCENT}]{qdisp}[/]", style=CLI_BORDER))
        console.print()

        with console.status(f"[{CLI_ACCENT}]Answering…[/]", spinner="dots"):
            answer = followup_answer(question, bundle, selections)

        try:
            console.print(Markdown(answer))
        except Exception:
            console.print(answer)
        console.print()
