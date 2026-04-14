import time
import json
from stockbuddy.dataflows.config import get_config


def create_risky_debator(llm):
    def risky_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        risky_history = risk_debate_state.get("risky_history", "")

        current_safe_response = risk_debate_state.get("current_safe_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        
        # 根據市場選擇語言
        config = get_config()
        default_market = config.get('DEFAULT_MARKET', 'HK')
        
        if default_market == 'HKEX':
            prompt = f"""作為進取型風險分析師，你的角色是積極倡導高回報、高風險的機會，強調大膽的策略和競爭優勢。在評估交易員的決策或計劃時，專注於潛在的上行空間、增長潛力和創新優勢——即使這些伴隨著較高的風險。使用提供的市場數據和情緒分析來加強你的論點並挑戰對立觀點。具體來說，直接回應保守派和中立派分析師提出的每一點，用數據驅動的反駁和有說服力的推理進行反擊。強調他們的謹慎可能會錯過的關鍵機會，或者他們的假設可能過於保守的地方。以下是交易員的決策：

{trader_decision}

你的任務是通過質疑和批評保守派和中立派的立場，為交易員的決策建立一個令人信服的理由，展示為什麼你的高回報視角提供了最佳的前進道路。將以下來源的見解納入你的論據：

市場研究報告：{market_research_report}
社交媒體情緒報告：{sentiment_report}
最新世界事務報告：{news_report}
公司基本面報告：{fundamentals_report}
以下是當前的對話歷史：{history} 以下是保守派分析師的最新論點：{current_safe_response} 以下是中立派分析師的最新論點：{current_neutral_response}。如果其他觀點沒有回應，不要虛構，只需提出你的觀點。

積極參與，通過解決提出的任何具體擔憂，反駁他們邏輯中的弱點，並斷言冒險的好處以超越市場規範。保持專注於辯論和說服，而不僅僅是呈現數據。挑戰每一個反對觀點，以強調為什麼高風險方法是最佳的。以對話方式輸出，就像你在講話一樣，不要任何特殊格式。"""
        else:
            prompt = f"""As the Risky Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and challenge the opposing views. Specifically, respond directly to each point made by the conservative and neutral analysts, countering with data-driven rebuttals and persuasive reasoning. Highlight where their caution might miss critical opportunities or where their assumptions may be overly conservative. Here is the trader's decision:

{trader_decision}

Your task is to create a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances to demonstrate why your high-reward perspective offers the best path forward. Incorporate insights from the following sources into your arguments:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here are the last arguments from the conservative analyst: {current_safe_response} Here are the last arguments from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints, do not halluncinate and just present your point.

Engage actively by addressing any specific concerns raised, refuting the weaknesses in their logic, and asserting the benefits of risk-taking to outpace market norms. Maintain a focus on debating and persuading, not just presenting data. Challenge each counterpoint to underscore why a high-risk approach is optimal. Output conversationally as if you are speaking without any special formatting."""

        response = llm.invoke(prompt)

        argument = f"Risky Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risky_history + "\n" + argument,
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Risky",
            "current_risky_response": argument,
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return risky_node
