"""
港股新闻实际内容获取工具
整合多个数据源，实际抓取新闻内容
"""

from langchain_core.tools import tool
from typing import Annotated
from datetime import datetime, timedelta
from stockbuddy.dataflows.newsdata_io import get_newsdata_hk_stock_news, get_newsdata_market_news
from stockbuddy.dataflows.hkexnews_scraper import get_hkex_announcements
from stockbuddy.dataflows.google import get_company_chinese_name
from stockbuddy.dataflows.finnhub_news import get_finnhub_company_news, get_finnhub_news_sentiment


@tool
def get_hk_news_content(
    ticker_symbol: Annotated[str, "港股代码，如'0700'或'9988'"],
    days_back: Annotated[int, "回溯天数"] = 7,
) -> str:
    """
    【港股专用】获取实际的新闻内容 - 整合多个来源！
    
    功能：
    1. 从 Google News 抓取实际新闻内容（标题+摘要）
    2. 从披露易(HKEXnews)获取官方公告信息
    3. 自动识别公司中文名称，提高搜索准确性
    
    数据来源：
    - ✅ Google News: 阿斯达克、信报、经济日报、经济通等
    - ✅ HKEXnews: 官方公告平台
    - ✅ 自动中文名称识别
    
    返回内容：
    - 新闻标题、摘要、来源、发布日期
    - 官方公告链接和说明
    - 按时间倒序排列
    
    优势：
    - 实际内容，不只是链接
    - 多来源整合，信息全面
    - 专为港股优化
    """
    # 标准化ticker
    ticker_clean = ticker_symbol.replace('.HK', '').replace('.HKG', '').zfill(4)
    ticker_display = f"{ticker_clean}.HK"
    
    # 获取公司中文名称（优先使用 API，fallback 到映射表）
    company_name = get_company_chinese_name(ticker_symbol)
    # 如果返回的是 ticker 本身，说明没找到名称，设为空字符串
    if company_name == ticker_symbol or company_name == ticker_clean:
        company_name = ""
    
    # 日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    end_date_str = end_date.strftime("%Y-%m-%d")
    start_date_str = start_date.strftime("%Y-%m-%d")
    
    # 生成报告
    report = f"# 📰 港股新闻实际内容 - {ticker_display}\n"
    if company_name:
        report += f"## 公司: {company_name}\n"
    report += f"## 时间范围: {start_date_str} 至 {end_date_str}\n\n"
    
    report += "---\n\n"
    
    # 1. Finnhub 专业金融新闻
    report += "## 一、专业金融新闻（Finnhub API）\n\n"
    
    try:
        finnhub_news = get_finnhub_company_news(
            ticker_symbol=ticker_display,
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        if finnhub_news and "未找到相关新闻" not in finnhub_news and "获取失败" not in finnhub_news:
            report += finnhub_news + "\n\n"
        else:
            report += "⚠️ Finnhub 暂无相关新闻或API配额不足\n\n"
            
    except Exception as e:
        report += f"⚠️ Finnhub 获取失败: {str(e)}\n\n"
    
    report += "---\n\n"
    
    # 2. Newsdata.io 新闻（替代 Google News）
    report += "## 二、财经媒体新闻（Newsdata.io API）\n\n"
    
    try:
        # 调用 Newsdata.io API
        newsdata_news = get_newsdata_hk_stock_news(
            ticker_symbol=ticker_clean,
            company_name=company_name,
            days_back=days_back,
            max_results=10
        )
        
        if newsdata_news:
            report += newsdata_news + "\n\n"
        else:
            report += "⚠️ 未找到相关新闻\n\n"
            
    except Exception as e:
        report += f"⚠️ Newsdata.io 获取失败: {str(e)}\n\n"
    
    report += "---\n\n"
    
    # 3. Finnhub 新闻情绪分析
    report += "## 三、新闻情绪分析（Finnhub Sentiment）\n\n"
    
    try:
        finnhub_sentiment = get_finnhub_news_sentiment(ticker_display)
        
        if finnhub_sentiment and "暂无情绪数据" not in finnhub_sentiment and "失败" not in finnhub_sentiment:
            report += finnhub_sentiment + "\n\n"
        else:
            report += "⚠️ 暂无情绪数据\n\n"
            
    except Exception as e:
        report += f"⚠️ 情绪分析获取失败: {str(e)}\n\n"
    
    report += "---\n\n"
    
    # 4. HKEXnews 官方公告
    report += "## 四、披露易官方公告 (HKEXnews)\n\n"
    
    try:
        hkex_announcements = get_hkex_announcements(
            stock_code=ticker_clean,
            start_date=start_date_str,
            end_date=end_date_str,
            max_results=20
        )
        
        if hkex_announcements:
            report += hkex_announcements + "\n\n"
            
    except Exception as e:
        report += f"⚠️ HKEXnews 获取失败: {str(e)}\n\n"
    
    report += "---\n\n"
    
    # 5. 分析建议
    report += "## 五、新闻分析建议\n\n"
    report += "### 关注重点\n"
    report += "1. **业绩相关**: 盈利预警、业绩公告、分析师评级\n"
    report += "2. **公司动作**: 收购合并、配股供股、高管变动\n"
    report += "3. **监管消息**: 证监会处罚、上市规则变更\n"
    report += "4. **市场情绪**: 大行评级、机构持仓变化\n\n"
    
    report += "### 情绪判断\n"
    report += "- **正面信号**: 业绩超预期、评级上调、增持、政策利好\n"
    report += "- **负面信号**: 盈利预警、评级下调、减持、监管处罚\n"
    report += "- **中性信息**: 一般公告、例行披露\n\n"
    
    return report


@tool  
def get_hk_market_news_content(
    days_back: Annotated[int, "回溯天数"] = 3
) -> str:
    """
    【港股专用】获取港股市场整体新闻实际内容
    
    功能：
    - 抓取恒生指数、国企指数相关新闻
    - 港股通资金流向新闻
    - 香港宏观经济新闻
    - 中国政策对港股影响的新闻
    
    返回：实际新闻内容，不只是链接
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    report = f"# 📊 港股市场新闻 - 实际内容\n"
    report += f"## 时间范围: 近{days_back}天\n\n"
    
    # 搜索关键词列表
    keywords = [
        "恒生指数",
        "国企指数",
        "港股通",
        "北水南下",
        "香港股市"
    ]
    
    for keyword in keywords:
        report += f"### 🔍 {keyword}\n\n"
        
        try:
            # 使用 Newsdata.io 搜索市场新闻
            news = get_newsdata_market_news(
                query=keyword,
                days_back=days_back,
                max_results=5
            )
            
            if news:
                report += news + "\n\n"
            else:
                report += f"⚠️ 未找到关于 {keyword} 的新闻\n\n"
                
        except Exception as e:
            report += f"⚠️ 搜索失败: {str(e)}\n\n"
        
        report += "---\n\n"
    
    return report
