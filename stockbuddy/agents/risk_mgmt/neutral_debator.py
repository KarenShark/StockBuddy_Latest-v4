import time
import json
from stockbuddy.dataflows.config import get_config


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_safe_response = risk_debate_state.get("current_safe_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        # 根據市場選擇語言
        config = get_config()
        default_market = config.get('DEFAULT_MARKET', 'HK')
        
        if default_market == 'HKEX':
            prompt = f"""作為中立型風險分析師，你的角色是提供平衡的視角，權衡交易員決策或計劃的潛在收益和風險。你優先考慮全面的方法，評估上行和下行空間，同時考慮更廣泛的市場趨勢、潛在的經濟變化和多樣化策略。以下是交易員的決策：

{trader_decision}

你的任務是挑戰進取型和保守型分析師，指出每個視角可能過於樂觀或過於謹慎的地方。使用以下數據來源的見解來支持調整交易員決策的溫和、可持續策略：

市場研究報告：{market_research_report}
社交媒體情緒報告：{sentiment_report}
最新世界事務報告：{news_report}
公司基本面報告：{fundamentals_report}
以下是當前的對話歷史：{history} 以下是進取型分析師的最新回應：{current_risky_response} 以下是保守型分析師的最新回應：{current_safe_response}。如果其他觀點沒有回應，不要虛構，只需提出你的觀點。

積極參與，通過批判性地分析雙方，解決進取型和保守型論點中的弱點，倡導更平衡的方法。挑戰他們的每一個觀點，以說明為什麼適度的風險策略可能提供兩全其美，在提供增長潛力的同時防範極端波動。專注於辯論而不僅僅是呈現數據，旨在表明平衡的觀點可以帶來最可靠的結果。以對話方式輸出，就像你在講話一樣，不要任何特殊格式。"""
        else:
            prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.Here is the trader's decision:

{trader_decision}

Your task is to challenge both the Risky and Safe Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the risky analyst: {current_risky_response} Here is the last response from the safe analyst: {current_safe_response}. If there are no responses from the other viewpoints, do not halluncinate and just present your point.

Engage actively by analyzing both sides critically, addressing weaknesses in the risky and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes. Output conversationally as if you are speaking without any special formatting."""

        response = llm.invoke(prompt)

        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
