import time
import json
import os
from stockbuddy.agents.utils.hk_market_prompts import get_hk_market_prompt


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        # 根據市場選擇prompt
        default_market = os.getenv('DEFAULT_MARKET', 'HKEX')
        if default_market == 'HKEX':
            base_prompt = get_hk_market_prompt('risk_judge')
            prompt = f"""{base_prompt}

---

**交易員原始計劃：**
{trader_plan}

**分析師辯論歷史：**
{history}

**過去類似情況的經驗教訓：**
{past_memory_str}

---

請基於以上信息，做出明確、果斷、可操作的決策。用繁體中文撰寫專業的風險管理決策報告。
"""
        else:
            prompt = f"""As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Risky, Neutral, and Safe/Conservative—and determine the best course of action for the trader. Your decision must be exactly one of these five English tokens: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL (BUY=strong long, OVERWEIGHT=modest long, HOLD=neutral, UNDERWEIGHT=modest reduce, SELL=strong exit/short). Choose HOLD only if strongly justified. Strive for clarity.

Guidelines for Decision-Making:
1. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
2. **Provide Rationale**: Support your recommendation with direct quotes and counterarguments from the debate.
3. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.
4. **Learn from Past Mistakes**: Use lessons from **{past_memory_str}** to address prior misjudgments and improve the decision you are making now.

Deliverables:
- A clear recommendation: one of BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL.
- Detailed reasoning anchored in the debate and past reflections.

---

**Analysts Debate History:**  
{history}

---

Focus on actionable insights and continuous improvement. Build on past lessons, critically evaluate all perspectives, and ensure each decision advances better outcomes."""

        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "risky_history": risk_debate_state["risky_history"],
            "safe_history": risk_debate_state["safe_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state["current_risky_response"],
            "current_safe_response": risk_debate_state["current_safe_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return risk_manager_node
