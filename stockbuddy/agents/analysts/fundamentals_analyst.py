from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
import os
from stockbuddy.agents.utils.agent_utils import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_insider_sentiment, get_insider_transactions
from stockbuddy.dataflows.config import get_config
from stockbuddy.agents.utils.hk_market_prompts import get_hk_market_prompt


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        # 根據市場選擇prompt
        default_market = os.getenv('DEFAULT_MARKET', 'HKEX')
        if default_market == 'HKEX':
            # Add HKEXnews link for Hong Kong stocks
            clean_code = ticker.replace('.HK', '').replace('.HKG', '')
            if clean_code.isdigit():
                hkex_code = clean_code.zfill(5)
                hkexnews_link = f"https://www1.hkexnews.hk/search/titlesearch.xhtml?stock={hkex_code}"
                system_message = get_hk_market_prompt('fundamentals')
                system_message += f"\n\n**重要資源**：請在報告中提醒用戶查看披露易（HKEXnews）的官方公告：{hkexnews_link}\n這是香港交易所的官方披露平台，包含所有上市公司的公告、財報、股權變動等重要信息。"
            else:
                system_message = get_hk_market_prompt('fundamentals')
        else:
            system_message = (
                "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
                + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
                + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements.",
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
                    "For your reference, the current date is {current_date}. The company we want to look at is {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
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
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
