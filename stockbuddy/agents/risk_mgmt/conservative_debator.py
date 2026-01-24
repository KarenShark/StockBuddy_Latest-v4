from langchain_core.messages import AIMessage
import time
import json
from stockbuddy.dataflows.config import get_config


def create_safe_debator(llm):
    def safe_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        safe_history = risk_debate_state.get("safe_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
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
            prompt = f"""作為保守型/安全型風險分析師，你的首要目標是保護資產、最小化波動性並確保穩定可靠的增長。你優先考慮穩定性、安全性和風險緩解，仔細評估潛在損失、經濟衰退和市場波動。在評估交易員的決策或計劃時，批判性地審查高風險元素，指出決策可能使公司面臨不當風險的地方，以及更謹慎的替代方案如何能夠確保長期收益。以下是交易員的決策：

{trader_decision}

你的任務是積極反駁進取型和中立型分析師的論點，強調他們的觀點可能忽視潛在威脅或未能優先考慮可持續性的地方。直接回應他們的觀點，從以下數據來源中獲取證據，為交易員決策的低風險方法調整建立令人信服的理由：

市場研究報告：{market_research_report}
社交媒體情緒報告：{sentiment_report}
最新世界事務報告：{news_report}
公司基本面報告：{fundamentals_report}
以下是當前的對話歷史：{history} 以下是進取型分析師的最新回應：{current_risky_response} 以下是中立型分析師的最新回應：{current_neutral_response}。如果其他觀點沒有回應，不要虛構，只需提出你的觀點。

通過質疑他們的樂觀情緒並強調他們可能忽略的潛在下行風險來參與辯論。針對他們的每一個反對觀點，展示為什麼保守立場最終是公司資產最安全的道路。專注於辯論和批評他們的論點，以展示低風險策略相對於他們方法的優勢。以對話方式輸出，就像你在講話一樣，不要任何特殊格式。"""
        else:
            prompt = f"""As the Safe/Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains. Here is the trader's decision:

{trader_decision}

Your task is to actively counter the arguments of the Risky and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability. Respond directly to their points, drawing from the following data sources to build a convincing case for a low-risk approach adjustment to the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the risky analyst: {current_risky_response} Here is the last response from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints, do not halluncinate and just present your point.

Engage by questioning their optimism and emphasizing the potential downsides they may have overlooked. Address each of their counterpoints to showcase why a conservative stance is ultimately the safest path for the firm's assets. Focus on debating and critiquing their arguments to demonstrate the strength of a low-risk strategy over their approaches. Output conversationally as if you are speaking without any special formatting."""

        response = llm.invoke(prompt)

        argument = f"Safe Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": safe_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Safe",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return safe_node
