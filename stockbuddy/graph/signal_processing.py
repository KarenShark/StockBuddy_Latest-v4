# StockBuddy/graph/signal_processing.py

from langchain_openai import ChatOpenAI

from stockbuddy.graph.signal_vocab import coerce_llm_action_token


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: ChatOpenAI):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> str:
        """
        Map final_trade_decision text to one of five canonical actions (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL).
        """
        messages = [
            (
                "system",
                "Extract the single investment stance. Reply with exactly ONE token from this closed set, uppercase, no punctuation, no explanation:\n"
                "BUY | OVERWEIGHT | HOLD | UNDERWEIGHT | SELL\n"
                "BUY = strong long / add materially; OVERWEIGHT = modestly bullish / tilt long; "
                "HOLD = neutral / no change; UNDERWEIGHT = modestly bearish / trim; "
                "SELL = strong short / exit. If the text is only weakly directional, prefer OVERWEIGHT or UNDERWEIGHT over BUY/SELL.",
            ),
            ("human", full_signal),
        ]
        raw = self.quick_thinking_llm.invoke(messages).content
        return coerce_llm_action_token(str(raw or ""), full_signal)
 