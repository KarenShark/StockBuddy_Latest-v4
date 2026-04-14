from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
import os
from stockbuddy.agents.utils.agent_utils import get_news, get_global_news
from stockbuddy.dataflows.config import get_config
from stockbuddy.agents.utils.hk_market_prompts import get_hk_market_prompt
from stockbuddy.agents.utils.hk_news_tools import get_hk_stock_news_links, get_hk_market_news_links
from stockbuddy.agents.utils.hk_news_fetcher import get_hk_news_content, get_hk_market_news_content
from stockbuddy.agents.utils.finnhub_news_tools import get_finnhub_news, get_finnhub_sentiment
from stockbuddy.dataflows.google import get_company_chinese_name


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 根據市場選擇工具和prompt
        config = get_config()
        default_market = config.get('DEFAULT_MARKET', 'HK')
        
        if default_market == 'HKEX':
            # 港股市場：優先使用港股專用新聞工具
            # 工具順序很重要：LLM會優先考慮列表前面的工具
            tools = [
                get_news,              # EODHD 多源歷史新聞，回測最可靠
                get_hk_news_content,   # Finnhub + HKEXnews 補充
                get_global_news,       # 宏觀新聞
                get_finnhub_sentiment,
                get_hk_market_news_content,
                get_finnhub_news,
                get_hk_stock_news_links,
                get_hk_market_news_links,
            ]
            system_message = get_hk_market_prompt('news')
        else:
            # 美股市場：使用原有工具
            tools = [
                get_news,
                get_global_news,
            ]
            system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(query, start_date, end_date) for company-specific or targeted news searches, and get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL (BUY|OVERWEIGHT|HOLD|UNDERWEIGHT|SELL) or deliverable,"
                    " prefix your response with that five-way token so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. We are looking at the company {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # 為港股市場準備額外的上下文信息
        additional_context = ""
        if default_market == 'HKEX':
            try:
                company_chinese_name = get_company_chinese_name(ticker)
                if company_chinese_name and company_chinese_name != "N/A":
                    additional_context = f"\n\n**重要提示**：此為港股 {ticker}（{company_chinese_name}）的分析。請優先使用 `get_news` 獲取歷史新聞（start_date = current_date 前 7-14 天，end_date = current_date）。如需補充可用 `get_hk_news_content`（必須傳 analysis_date = current_date）。"
                else:
                    additional_context = f"\n\n**重要提示**：此為港股 {ticker} 的分析。請優先使用 `get_news` 獲取歷史新聞，如需補充可用 `get_hk_news_content`（必須傳 analysis_date）。"
            except Exception as e:
                print(f"獲取公司中文名稱時出錯: {e}")
                additional_context = f"\n\n**重要提示**：請優先使用 `get_news` 獲取歷史新聞，如需補充可用 `get_hk_news_content`（必須傳 analysis_date）。"
        
        prompt = prompt.partial(system_message=system_message + additional_context)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
