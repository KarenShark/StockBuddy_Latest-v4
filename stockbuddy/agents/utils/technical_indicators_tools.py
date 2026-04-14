from langchain_core.tools import tool
from typing import Annotated, List

from stockbuddy.dataflows.interface import route_to_vendor


def _split_indicator_names(indicator: str) -> List[str]:
    raw = (indicator or "").replace(";", ",")
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


@tool
def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """
    Retrieve technical indicators for a given ticker symbol.
    Uses the configured technical_indicators vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        indicator (str): One indicator name, or comma-separated names (each fetched separately).
        curr_date (str): The current trading date you are trading on, YYYY-mm-dd
        look_back_days (int): How many days to look back, default is 30
    Returns:
        str: A formatted dataframe containing the technical indicators for the specified ticker symbol and indicator.
    """
    names = _split_indicator_names(indicator)
    if not names:
        return route_to_vendor("get_indicators", symbol, indicator, curr_date, look_back_days)
    if len(names) == 1:
        return route_to_vendor("get_indicators", symbol, names[0], curr_date, look_back_days)
    chunks = []
    for name in names:
        chunks.append(
            route_to_vendor("get_indicators", symbol, name, curr_date, look_back_days)
        )
    return "\n\n".join(str(c) for c in chunks)