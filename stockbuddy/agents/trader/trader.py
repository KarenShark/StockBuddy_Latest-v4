import functools
import time
import json
import os
from stockbuddy.agents.utils.hk_market_prompts import get_hk_market_prompt


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
        }

        # 根據市場選擇prompt
        default_market = os.getenv('DEFAULT_MARKET', 'HKEX')
        if default_market == 'HKEX':
            system_prompt = get_hk_market_prompt('trader')
            system_content = system_prompt + f"\n\n過去類似情況的經驗教訓：\n{past_memory_str}"
        else:
            system_content = f"""You are a trader analyzing market data to make investment decisions. End with exactly one token: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, or SELL. Always conclude with 'FINAL TRANSACTION PROPOSAL: **<TOKEN>**' (five-way scale). Use past reflections: {past_memory_str}"""

        messages = [
            {
                "role": "system",
                "content": system_content,
            },
            context,
        ]

        result = llm.invoke(messages)

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
