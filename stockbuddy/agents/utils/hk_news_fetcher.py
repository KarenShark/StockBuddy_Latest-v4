"""
港股新闻实际内容获取工具
整合多个数据源，实际抓取新闻内容
"""

from langchain_core.tools import tool
from typing import Annotated
from datetime import datetime, timedelta, timezone
from stockbuddy.dataflows.newsdata_io import get_newsdata_hk_stock_news, get_newsdata_market_news
from stockbuddy.dataflows.hkexnews_scraper import get_hkex_announcements
from stockbuddy.dataflows.google import get_company_chinese_name
from stockbuddy.dataflows.finnhub_news import get_finnhub_company_news, get_finnhub_news_sentiment


@tool
def get_hk_news_content(
    ticker_symbol: Annotated[str, "港股代码，如'0700'或'9988'"],
    days_back: Annotated[int, "回溯天数"] = 7,
    analysis_date: Annotated[str, "分析基准日期 yyyy-mm-dd，不传则用今天"] = "",
) -> str:
    """
    HK stock news aggregator: Finnhub + Newsdata.io + HKEXnews.

    Pass analysis_date when back-testing to avoid look-ahead bias.
    """
    ticker_clean = ticker_symbol.replace('.HK', '').replace('.HKG', '').zfill(4)
    ticker_display = f"{ticker_clean}.HK"
    
    company_name = get_company_chinese_name(ticker_symbol)
    if company_name == ticker_symbol or company_name == ticker_clean:
        company_name = ""
    
    # Anchor to analysis_date when provided, else today
    if analysis_date and analysis_date.strip():
        end_date = datetime.strptime(analysis_date.strip(), "%Y-%m-%d")
    else:
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
    
    # 2. Newsdata.io (live API only — no historical date support on free tier)
    report += "## 二、财经媒体新闻（Newsdata.io API）\n\n"
    
    _is_historical = end_date.date() < datetime.now(timezone.utc).date()
    if _is_historical:
        report += "⚠️ Newsdata.io 免费版不支持历史查询，已跳过\n\n"
    else:
        try:
            newsdata_news = get_newsdata_hk_stock_news(
                ticker_symbol=ticker_clean,
                company_name=company_name,
                days_back=days_back,
                max_results=10,
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
    days_back: Annotated[int, "lookback days"] = 3,
    analysis_date: Annotated[str, "analysis date yyyy-mm-dd; defaults to today"] = "",
) -> str:
    """
    HK market: full-text style headlines/snippets via Newsdata (cn/hk/tw business).
    Sections are labeled in English; API query stays zh for recall.
    Pass analysis_date for back-testing to avoid look-ahead bias.
    """
    if analysis_date and analysis_date.strip():
        from datetime import datetime as _dt
        try:
            ad = _dt.strptime(analysis_date.strip(), "%Y-%m-%d").date()
            if ad < _dt.now().date():
                return (
                    f"⚠️ get_hk_market_news_content: analysis_date={analysis_date} is historical. "
                    "Newsdata.io has no archive — use get_news(ticker, start_date, end_date) instead."
                )
        except ValueError:
            pass

    report = f"# 📊 Hong Kong market news (snippets)\n"
    report += f"## Window: last {days_back} day(s)\n\n"
    
    # (section label EN, Newsdata q in zh — keeps HK-relevant hits)
    topics = [
        ("Hang Seng Index", "恒生指数"),
        ("HSCEI", "国企指数"),
        ("Stock Connect", "港股通"),
        ("Southbound flows", "北水南下"),
        ("Hong Kong stock market", "香港股市"),
    ]
    
    for label_en, query_zh in topics:
        report += f"### 🔍 {label_en}\n\n"
        
        try:
            news = get_newsdata_market_news(
                query=query_zh,
                days_back=days_back,
                max_results=5,
                template_lang="en",
            )
            
            if news:
                report += news + "\n\n"
            else:
                report += f"⚠️ No news found for this topic.\n\n"
                
        except Exception as e:
            report += f"⚠️ Search failed: {str(e)}\n\n"
        
        report += "---\n\n"
    
    return report
