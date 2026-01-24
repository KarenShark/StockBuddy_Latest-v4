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
) -> str:
    """
    【专业金融新闻】从 Finnhub API 获取公司新闻
    
    Finnhub 优势：
    - ⭐ 专业金融数据API，数据质量高
    - ⭐ 支持全球股市（包括港股、美股、A股等）
    - ⭐ 多语言新闻源
    - ⭐ 实时更新
    - ⭐ 免费额度充足
    
    返回内容：
    - 新闻标题、摘要、来源
    - 发布时间（精确到秒）
    - 新闻链接（可直接访问）
    - 新闻分类（业绩、监管、并购等）
    
    适用场景：
    - 获取港股公司的专业财经新闻
    - 补充 Google News 的内容
    - 需要高质量、权威的新闻源
    
    港股使用：
    - 输入如 '0700'、'9988' 会自动转换为 '0700.HK'、'9988.HK'
    - 支持 .HK 后缀的标准格式
    """
    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    end_date_str = end_date.strftime("%Y-%m-%d")
    start_date_str = start_date.strftime("%Y-%m-%d")
    
    # 调用 Finnhub API
    result = get_finnhub_company_news(
        ticker_symbol=ticker_symbol,
        start_date=start_date_str,
        end_date=end_date_str
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
