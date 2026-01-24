"""
Newsdata.io News Tools for LangChain
免费新闻 API 工具
"""

from langchain_core.tools import tool
from typing import Annotated
from stockbuddy.dataflows.newsdata_io import (
    get_newsdata_news,
    get_newsdata_hk_stock_news,
    get_newsdata_market_news
)


@tool
def get_newsdata_stock_news(
    ticker_symbol: Annotated[str, "股票代码，如'0700'或'AAPL'"],
    company_name: Annotated[str, "公司名称（中文或英文）"] = "",
    days_back: Annotated[int, "回溯天数"] = 7,
) -> str:
    """
    【推荐】使用 Newsdata.io 获取股票相关新闻
    
    功能：
    - 支持中文新闻搜索
    - 覆盖中国大陆、香港、台湾新闻源
    - 专业财经新闻分类
    - 免费 API，稳定可靠
    
    优势：
    - 不需要爬虫，直接 API 调用
    - 支持多语言（中文、英文等）
    - 新闻来源广泛（百度新闻等）
    - 返回标题、摘要、链接、来源、时间
    
    使用场景：
    - 港股公司新闻分析
    - 美股公司新闻分析
    - 中文财经新闻获取
    
    示例：
    - get_newsdata_stock_news("0700", "腾讯")
    - get_newsdata_stock_news("AAPL", "Apple")
    """
    # 判断是否为港股
    is_hk = ticker_symbol.replace('.HK', '').replace('.HKG', '').isdigit()
    
    if is_hk:
        # 港股专用
        return get_newsdata_hk_stock_news(
            ticker_symbol=ticker_symbol,
            company_name=company_name,
            days_back=days_back,
            max_results=10
        )
    else:
        # 通用搜索
        query = f"{ticker_symbol} {company_name}" if company_name else ticker_symbol
        return get_newsdata_news(
            query=query,
            language="en" if not company_name else "zh",
            category=["business", "technology"],
            days_back=days_back,
            max_results=10
        )


@tool
def get_newsdata_hk_market(
    days_back: Annotated[int, "回溯天数"] = 3,
) -> str:
    """
    【港股专用】使用 Newsdata.io 获取港股市场整体新闻
    
    功能：
    - 获取港股市场、恒生指数相关新闻
    - 覆盖港股通、北水南下等话题
    - 中文新闻，易于理解
    
    关键词涵盖：
    - 港股市场动态
    - 恒生指数走势
    - 港股通资金流向
    - 香港股市监管政策
    
    示例：
    - get_newsdata_hk_market(days_back=3)
    """
    return get_newsdata_market_news(
        query="港股 OR 恒生指数 OR 香港股市 OR 港股通",
        days_back=days_back,
        max_results=10
    )


@tool
def get_newsdata_general(
    query: Annotated[str, "搜索关键词"],
    language: Annotated[str, "语言代码 (zh=中文, en=英文)"] = "zh",
    days_back: Annotated[int, "回溯天数"] = 7,
) -> str:
    """
    【通用】使用 Newsdata.io 搜索任意主题的新闻
    
    功能：
    - 灵活的关键词搜索
    - 支持多语言
    - 可自定义日期范围
    
    使用场景：
    - 行业趋势分析
    - 宏观经济新闻
    - 政策法规更新
    - 竞争对手动态
    
    示例：
    - get_newsdata_general("人工智能", "zh")
    - get_newsdata_general("Federal Reserve", "en")
    """
    return get_newsdata_news(
        query=query,
        language=language,
        days_back=days_back,
        max_results=10
    )
