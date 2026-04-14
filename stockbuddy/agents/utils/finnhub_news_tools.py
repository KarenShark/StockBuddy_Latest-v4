"""
Finnhub 新闻工具 - 为 LangChain agents 提供
使用 @tool 装饰器，可直接被 agents 调用
"""

from langchain_core.tools import tool
from typing import Annotated
from datetime import datetime, timedelta
from stockbuddy.dataflows.finnhub_news import (
    get_finnhub_company_news,
    get_finnhub_news_sentiment
)


@tool
def get_finnhub_news(
    ticker_symbol: Annotated[str, "港股代码或美股代码，如'0700'、'AAPL'"],
    days_back: Annotated[int, "回溯天数"] = 7,
    analysis_date: Annotated[str, "分析基准日期 yyyy-mm-dd，不传则用今天"] = "",
) -> str:
    """
    Finnhub company news. Pass analysis_date for back-testing.
    """
    if analysis_date and analysis_date.strip():
        end_date = datetime.strptime(analysis_date.strip(), "%Y-%m-%d")
    else:
        end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    result = get_finnhub_company_news(
        ticker_symbol=ticker_symbol,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )
    return result


@tool
def get_finnhub_sentiment(
    ticker_symbol: Annotated[str, "股票代码，如'0700.HK'、'AAPL'"],
) -> str:
    """
    【新闻情绪分析】从 Finnhub 获取新闻情绪指标
    
    返回指标：
    - 📈 讨论热度 (Buzz): 本周文章数量和热度变化
    - 😊 情绪评分: 看多/看空比例
    - 📰 新闻评分: 公司新闻评分 vs 行业平均
    
    重要性：⭐⭐⭐⭐⭐
    新闻情绪是短期股价波动的重要领先指标！
    
    解读建议：
    - 热度突然上升 + 看多情绪 = 可能有重大利好
    - 热度突然上升 + 看空情绪 = 可能有风险事件
    - 新闻评分远高于行业 = 公司表现突出
    - 新闻评分远低于行业 = 需警惕负面消息
    """
    result = get_finnhub_news_sentiment(ticker_symbol=ticker_symbol)
    return result
