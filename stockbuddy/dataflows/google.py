from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import yfinance as yf
from .googlenews_utils import getNewsData
from .hk_stock_names import get_hk_stock_chinese_name


def get_company_chinese_name(ticker: str) -> str:
    """
    获取公司名称（港股返回中文名，美股返回英文名）
    
    策略：
    1. 对于港股，优先检查硬编码映射表（手动维护，更可靠）
    2. 如果映射表中没有，再使用 yfinance API 获取公司名称
    3. 如果都失败，返回原始 ticker
    
    注意：ticker应该已经经过智能识别系统标准化
    """
    market = os.getenv('DEFAULT_MARKET', 'HK')
    
    # 标准化 ticker 格式
    clean_ticker = ticker.replace('.HK', '').replace('.HKG', '').strip()
    
    if market == 'HKEX' and clean_ticker.isdigit():
        normalized_ticker = f"{clean_ticker.zfill(4)}.HK"
    else:
        normalized_ticker = ticker if '.HK' in ticker or '.' in ticker else ticker
    
    # 对于港股，优先检查硬编码映射表（手动维护，更可靠）
    if market == 'HKEX':
        chinese_name = get_hk_stock_chinese_name(ticker)
        if chinese_name:
            return chinese_name
    
    # 如果映射表中没有，使用 yfinance API
    try:
        ticker_obj = yf.Ticker(normalized_ticker)
        info = ticker_obj.info
        
        if info and info.get('symbol'):
            # 优先返回长名称
            long_name = info.get('longName', '')
            short_name = info.get('shortName', '')
            
            # 对于港股，优先返回中文名称（如果 API 提供）
            if market == 'HKEX':
                # yfinance 有时会返回中文名称，检查是否包含中文字符
                if long_name and any('\u4e00' <= char <= '\u9fff' for char in long_name):
                    return long_name
                elif short_name and any('\u4e00' <= char <= '\u9fff' for char in short_name):
                    return short_name
            
            # 返回英文名称
            if long_name:
                return long_name
            elif short_name:
                return short_name
    except Exception as e:
        # API 调用失败，继续 fallback
        pass
    
    # 最后的 fallback: 返回原始 ticker
    return ticker


def get_google_news(
    query: Annotated[str, "Query to search with"],
    curr_date: Annotated[str, "Curr date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    # 確保query是字符串類型
    query = str(query)
    
    # 針對香港市場增強搜索
    default_market = os.getenv('DEFAULT_MARKET', 'HK')
    if default_market == 'HKEX':
        # Try to get company Chinese name if query looks like a stock code
        if query.replace('.HK', '').replace('.HKG', '').replace('0', '').isdigit():
            company_name = get_company_chinese_name(query)
            if company_name and company_name != query:
                # Add company name to query with HK-specific keywords
                query = f"{query} {company_name}"
                
                # Add more HK-specific search terms for better news coverage
                hk_keywords = [
                    "業績", "公告", "股價", "港股", 
                    "投資", "分析", "評級", "增持", "減持"
                ]
                # Add site-specific searches for major HK financial media
                hk_sites = [
                    "site:hkej.com",      # 信報
                    "site:hket.com",      # 經濟日報
                    "site:aastocks.com",  # 阿斯達克
                    "site:etnet.com.hk",  # 經濟通
                    "site:hk01.com",      # 香港01
                    "site:mingpao.com",   # 明報
                    "site:scmp.com",      # 南華早報
                ]
                
                # Enhance query with HK financial media sites
                query = f"{query} ({' OR '.join(hk_sites[:4])})"
        
        # 添加香港相關搜索詞，提高香港新聞的相關性
        elif '香港' not in query and 'Hong Kong' not in query:
            query = f"{query} (香港 OR site:.hk OR 港股)"
    
    query = query.replace(" ", "+")

    start_date = datetime.strptime(curr_date, "%Y-%m-%d")
    before = start_date - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")

    news_results = getNewsData(query, before, curr_date)

    news_str = ""

    for news in news_results:
        news_str += (
            f"### {news['title']} (source: {news['source']}) \n\n{news['snippet']}\n\n"
        )

    if len(news_results) == 0:
        return ""

    return f"## {query} Google News, from {before} to {curr_date}:\n\n{news_str}"