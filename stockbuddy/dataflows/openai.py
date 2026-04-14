from openai import OpenAI
from .config import get_config
from .news_window_policy import analysis_end_is_historical, meta_line


def _extract_responses_text(response) -> tuple[str, str | None]:
    """Best-effort text from Responses API; (text, error_detail)."""
    out = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in out:
        for block in getattr(item, "content", None) or []:
            if getattr(block, "type", None) == "output_text":
                t = getattr(block, "text", None)
                if t:
                    chunks.append(str(t))
            elif isinstance(block, dict):
                if block.get("type") == "output_text" and block.get("text"):
                    chunks.append(str(block["text"]))
    text = "\n".join(chunks).strip()
    if text:
        return text, None
    return "", "no_output_text_blocks"


def get_stock_news_openai(query, start_date, end_date):
    config = get_config()
    client = OpenAI(base_url=config["backend_url"])

    response = client.responses.create(
        model=config["quick_think_llm"],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Can you search Social Media for {query} from {start_date} to {end_date}? Make sure you only get the data posted during that period.",
                    }
                ],
            }
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "low",
            }
        ],
        temperature=1,
        max_output_tokens=4096,
        top_p=1,
        store=True,
    )

    return response.output[1].content[0].text


def get_global_news_openai(curr_date, look_back_days=7, limit=5):
    """
    Live-only: web search cannot be bounded for historical backtests; disabled then.
    Returns STOCKBUDDY_NEWS_JSON header + body (never raises).
    """
    cd = str(curr_date).strip()
    if analysis_end_is_historical(cd):
        return (
            meta_line(
                {
                    "status": "provider_error",
                    "scope": "global",
                    "provider": "openai_web_search",
                    "detail": "disabled_in_historical_mode_unbounded_search",
                    "window": f"...{cd}",
                }
            )
            + "\n\nOpenAI web search skipped: historical analysis_date (no fabricated body)."
        )

    config = get_config()
    client = OpenAI(base_url=config["backend_url"])

    try:
        response = client.responses.create(
            model=config["quick_think_llm"],
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Search global / macro news from {look_back_days} days before "
                                f"{cd} to {cd} for trading context. "
                                f"Limit to {limit} articles. Only include items plausibly "
                                f"from that window; if uncertain, say so (do not invent URLs)."
                            ),
                        }
                    ],
                }
            ],
            text={"format": {"type": "text"}},
            reasoning={},
            tools=[
                {
                    "type": "web_search_preview",
                    "user_location": {"type": "approximate"},
                    "search_context_size": "low",
                }
            ],
            temperature=1,
            max_output_tokens=4096,
            top_p=1,
            store=True,
        )
    except Exception as e:
        return (
            meta_line(
                {
                    "status": "provider_error",
                    "scope": "global",
                    "provider": "openai_web_search",
                    "detail": str(e)[:240],
                }
            )
            + "\n\nOpenAI global news request failed (no fabricated body)."
        )

    text, err = _extract_responses_text(response)
    if err or not text:
        return (
            meta_line(
                {
                    "status": "parse_error",
                    "scope": "global",
                    "provider": "openai_web_search",
                    "detail": err or "empty_text",
                }
            )
            + "\n\nCould not parse model output (no fabricated body)."
        )

    hdr = meta_line(
        {
            "status": "ok",
            "scope": "global",
            "provider": "openai_web_search",
            "count": -1,
            "window": f"{look_back_days}d_to_{cd}",
        }
    )
    return f"{hdr}\n\n## Global news (OpenAI web search)\n\n{text}"


def get_fundamentals_openai(ticker, curr_date):
    config = get_config()
    client = OpenAI(base_url=config["backend_url"])

    response = client.responses.create(
        model=config["quick_think_llm"],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Can you search Fundamental for discussions on {ticker} during of the month before {curr_date} to the month of {curr_date}. Make sure you only get the data posted during that period. List as a table, with PE/PS/Cash flow/ etc",
                    }
                ],
            }
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "low",
            }
        ],
        temperature=1,
        max_output_tokens=4096,
        top_p=1,
        store=True,
    )

    return response.output[1].content[0].text