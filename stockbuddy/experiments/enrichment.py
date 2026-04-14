"""
Post-hoc decision enrichment: LLM summary + confidence + risk_flags, or heuristic fallback.
confidence is only set when LLM path succeeds (never heuristic fake scores).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI


def _make_quick_llm(config: Dict[str, Any]) -> Optional[ChatOpenAI]:
    provider = str(config.get("llm_provider", "")).lower()
    if provider not in ("openai", "ollama", "openrouter"):
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    extra_headers = {}
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        extra_headers = {
            "HTTP-Referer": "https://github.com/KarenShark/StockBuddy_Latest-v4",
            "X-Title": "StockBuddy",
        }
    if not api_key:
        return None
    return ChatOpenAI(
        model=config["quick_think_llm"],
        base_url=config["backend_url"],
        api_key=api_key,
        default_headers=extra_headers,
        temperature=0,
    )


def _extract_json_object(text: str) -> Dict[str, Any]:
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
        if m:
            t = m.group(1).strip()
    return json.loads(t)


def _two_sentence_summary(text: str, max_chars: int = 480) -> Optional[str]:
    if not text or not text.strip():
        return None
    s = text.strip()
    parts = re.split(r"(?<=[。！？!?])\s*|\n+", s)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.append(p)
        if len(out) >= 2:
            break
    if not out:
        return s[:max_chars]
    joined = " ".join(out) if all(ord(c) < 128 for c in "".join(out)[:80]) else "".join(out)
    return joined[:max_chars]


def enrich_decision_fields(
    config: Dict[str, Any],
    final_state: Dict[str, Any],
    signal_str: str,
    parsed_action: Optional[str],
) -> Dict[str, Any]:
    """
    Returns keys: rationale_summary, confidence, risk_flags, no_trade_reason,
    enrichment_mode (llm|heuristic), enrichment_error (optional).
    """
    de = config.get("decision_enrichment")
    if not isinstance(de, dict):
        de = {}
    enabled = de.get("enabled", True)
    final_txt = (final_state.get("final_trade_decision") or "").strip()

    if not enabled:
        h = _heuristic_core(final_txt, parsed_action)
        h["enrichment_mode"] = "heuristic"
        h["enrichment_error"] = None
        return h

    llm = _make_quick_llm(config)
    if llm is None:
        h = _heuristic_core(final_txt, parsed_action)
        h["enrichment_mode"] = "heuristic"
        h["enrichment_error"] = "llm_unavailable"
        return h

    prompt = f"""You evaluate a trading decision memo. Output ONLY a JSON object with keys:
- rationale_summary: string, 2-4 short sentences (not copy-paste of full text)
- confidence: number between 0 and 1 (your confidence that the stated action matches the memo)
- risk_flags: array of short snake_case strings (e.g. liquidity, macro, data_gap), can be empty
- no_trade_reason: null or short string if the memo implies no clear trade / stay flat

Stance must be one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL (TradingAgents-style five levels).
Extracted action from signal line (may be wrong): {parsed_action!r}
Signal processor output: {signal_str!r}

Memo:
{final_txt[:12000]}
"""
    try:
        raw = llm.invoke(
            [
                ("system", "Reply with JSON only, no markdown."),
                ("human", prompt),
            ]
        )
        content = raw.content if hasattr(raw, "content") else str(raw)
        data = _extract_json_object(content)
        conf = data.get("confidence")
        conf_f: Optional[float] = None
        if isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0:
            conf_f = float(conf)
        flags = data.get("risk_flags")
        rf: List[str] = []
        if isinstance(flags, list):
            rf = [str(x) for x in flags if x is not None]
        rs = data.get("rationale_summary")
        rs_s = str(rs).strip() if rs is not None else None
        ntr = data.get("no_trade_reason")
        ntr_s = str(ntr).strip() if ntr is not None else None
        if not ntr_s:
            ntr_s = None
        return {
            "rationale_summary": rs_s,
            "confidence": conf_f,
            "risk_flags": rf,
            "no_trade_reason": ntr_s,
            "enrichment_mode": "llm",
            "enrichment_error": None,
        }
    except Exception as e:
        h = _heuristic_core(final_txt, parsed_action)
        h["enrichment_mode"] = "heuristic"
        h["enrichment_error"] = str(e)
        return h


def _heuristic_core(final_txt: str, parsed_action: Optional[str]) -> Dict[str, Any]:
    ntr: Optional[str] = None
    if parsed_action is None:
        ntr = "signal_unparsed"
    return {
        "rationale_summary": _two_sentence_summary(final_txt),
        "confidence": None,
        "risk_flags": [],
        "no_trade_reason": ntr,
    }
