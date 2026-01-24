"""
港股新闻工具 - 为agents提供新闻搜索功能
策略：生成精准的新闻搜索链接 + 提供新闻源摘要
"""

from typing import Annotated
from datetime import datetime, timedelta
import urllib.parse
from langchain_core.tools import tool


@tool
def get_hk_stock_news_links(
    ticker_symbol: Annotated[str, "港股代码，如'0700'或'9988'"],
    company_name: Annotated[str, "公司中文名称"] = "",
    days_back: Annotated[int, "回溯天数"] = 7,
) -> str:
    """
    【港股专用】获取指定股票的新闻搜索链接 - 优先使用此工具！
    
    功能：为指定港股生成精准的新闻搜索链接，覆盖所有主流港股专业新闻源
    
    适用场景：
    - 分析港股（.HK后缀）的新闻时必须使用
    - 查找公司特定新闻、公告、分析报告
    - 了解市场对该股票的最新评论
    
    返回内容：
    1. AAStocks、HKET、HKEJ、ET Net等专业港股新闻源的精准搜索链接
    2. Google News定制搜索链接（包含公司中文名+股票代码）
    3. HKEXnews（披露易）官方公告链接
    4. 每个新闻源的特点和使用建议
    
    优势：
    - 覆盖港股专业新闻源，内容最准确
    - 永不失效，无需担心抓取问题
    - 提供直接可点击的链接，分析师可立即访问
    
    参数说明：
    - ticker_symbol: 必填，港股代码（如'0700'、'9988'）
    - company_name: 可选，公司中文名称（如'腾讯控股'，留空会自动获取）
    - days_back: 可选，回溯天数，默认7天
    """
    # 标准化ticker
    ticker_clean = ticker_symbol.replace('.HK', '').zfill(4)
    ticker_display = f"{ticker_clean}.HK"
    
    # 日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # 生成报告
    report = f"# 🔍 港股新闻搜索指南 - {ticker_display}\n\n"
    
    if company_name and company_name != "N/A":
        report += f"**公司名称**：{company_name}\n"
    
    report += f"**搜索日期**：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}\n"
    report += f"**天数范围**：{days_back}天\n\n"
    report += "---\n\n"
    
    # 1. Google News 搜索链接
    report += "## 1️⃣ Google News 综合搜索\n\n"
    
    google_queries = []
    
    # Query 1: 公司名 + 港股关键词
    if company_name and company_name != "N/A":
        q1 = f'"{company_name}" (港股 OR 股價 OR 業績 OR 公告)'
        google_queries.append(("公司新闻综合", q1))
    
    # Query 2: 股票代码 + 专业网站
    q2 = f'{ticker_clean} (site:aastocks.com OR site:hket.com OR site:hkej.com OR site:etnet.com.hk)'
    google_queries.append(("专业财经媒体", q2))
    
    # Query 3: 公司 + 分析评级
    if company_name and company_name != "N/A":
        q3 = f'"{company_name}" (分析 OR 評級 OR 目標價 OR 投資建議)'
        google_queries.append(("分析师评级", q3))
    
    for query_name, query in google_queries:
        encoded_query = urllib.parse.quote(query)
        date_filter = f"cdr:1,cd_min:{start_date.strftime('%m/%d/%Y')},cd_max:{end_date.strftime('%m/%d/%Y')}"
        google_url = f"https://www.google.com/search?q={encoded_query}&tbs={date_filter}&tbm=nws"
        
        report += f"### 🔗 {query_name}\n"
        report += f"**搜索词**：`{query}`\n\n"
        report += f"**链接**：[点击搜索]({google_url})\n\n"
    
    report += "---\n\n"
    
    # 2. 专业港股新闻网站直达链接
    report += "## 2️⃣ 专业港股新闻网站\n\n"
    
    news_sites = [
        {
            "name": "AAStocks 阿斯达克",
            "description": "港股专业财经网站，实时新闻、股价、技术分析",
            "url": f"https://www.aastocks.com/tc/stocks/quote/detail-quote.aspx?symbol={ticker_clean}",
            "特点": "✅ 港股专业 ✅ 实时更新 ✅ 技术分析"
        },
        {
            "name": "香港经济日报 (HKET)",
            "description": "香港主流财经媒体，深度报道和市场分析",
            "url": f"https://invest.hket.com/article/search?q={company_name if company_name and company_name != 'N/A' else ticker_clean}",
            "特点": "✅ 深度报道 ✅ 市场分析 ✅ 即时新闻"
        },
        {
            "name": "信报财经 (HKEJ)",
            "description": "香港财经权威媒体，专业投资分析",
            "url": f"https://search.hkej.com/?q={company_name if company_name and company_name != 'N/A' else ticker_clean}",
            "特点": "✅ 权威分析 ✅ 深度解读 ✅ 投资观点"
        },
        {
            "name": "经济通 (ET Net)",
            "description": "港股实时资讯和财经新闻",
            "url": f"https://www.etnet.com.hk/www/tc/stocks/realtime/quote.php?code={ticker_clean}",
            "特点": "✅ 实时资讯 ✅ 公司公告 ✅ 分析评论"
        },
        {
            "name": "披露易 (HKEXnews)",
            "description": "**官方公告平台**，上市公司必读",
            "url": f"https://www1.hkexnews.hk/search/titlesearch.xhtml?stock={ticker_clean.zfill(5)}",
            "特点": "⭐ 官方权威 ⭐ 最新公告 ⭐ 监管文件"
        }
    ]
    
    for site in news_sites:
        report += f"### 📰 {site['name']}\n"
        report += f"{site['description']}\n\n"
        report += f"**特点**：{site['特点']}\n\n"
        report += f"**链接**：[访问 {site['name']}]({site['url']})\n\n"
    
    report += "---\n\n"
    
    # 3. 搜索建议
    report += "## 3️⃣ 搜索建议\n\n"
    report += "### 📌 关键词推荐\n\n"
    report += "**业绩相关**：\n"
    report += "- 業績、盈利、營收、財報\n"
    report += "- Q1/Q2/Q3/Q4業績、年報、中期報告\n\n"
    
    report += "**股价动态**：\n"
    report += "- 股價、升/跌、突破、回調\n"
    report += "- 成交量、資金流向、大戶動向\n\n"
    
    report += "**公司动态**：\n"
    report += "- 公告、重組、收購、合併\n"
    report += "- 管理層變動、戰略調整\n\n"
    
    report += "**分析评级**：\n"
    report += "- 分析師評級、目標價、投資建議\n"
    report += "- 增持、減持、買入、賣出\n\n"
    
    report += "### 💡 使用技巧\n\n"
    report += "1. **优先查看披露易（HKEXnews）**：官方权威公告\n"
    report += "2. **结合多个来源**：交叉验证信息真实性\n"
    report += "3. **关注时效性**：优先查看最新7天内的新闻\n"
    report += "4. **注意新闻来源可信度**：官方 > 主流媒体 > 论坛\n\n"
    
    report += "---\n\n"
    report += f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
    
    return report


@tool
def get_hk_market_news_links(days_back: Annotated[int, "回溯天数"] = 3) -> str:
    """
    【港股专用】获取港股市场整体新闻搜索链接 - 宏观分析必用！
    
    功能：生成港股市场、恒生指数、港股通等宏观新闻的搜索链接
    
    适用场景：
    - 分析港股市场整体趋势和情绪
    - 获取恒生指数、国企指数相关新闻
    - 了解北水南下、港股通资金流向
    - 追踪影响港股的宏观政策和地缘政治
    
    覆盖主题：
    - 恒生指数
    - 港股通
    - 市场监管
    - 行业板块
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    report = "# 🌏 港股市场新闻搜索指南\n\n"
    report += f"**日期范围**：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}\n\n"
    report += "---\n\n"
    
    # 市场主题搜索
    market_topics = [
        {
            "topic": "恒生指数动态",
            "query": "恒生指數 OR HSI (升 OR 跌 OR 突破 OR 回調)",
            "keywords": "开盘、收盘、涨跌幅、成交额"
        },
        {
            "topic": "港股通北水南下",
            "query": "港股通 OR 北水南下 OR 南向資金",
            "keywords": "净流入、净流出、资金动向、重点买入"
        },
        {
            "topic": "市场监管政策",
            "query": "港交所 OR 證監會 OR HKEX OR SFC (監管 OR 政策 OR 改革)",
            "keywords": "新规、改革、IPO、监管动态"
        },
        {
            "topic": "科技股动态",
            "query": "香港科技股 OR 恒生科技指數 (科技 OR 互聯網 OR AI)",
            "keywords": "腾讯、阿里、美团、小米"
        }
    ]
    
    for topic_info in market_topics:
        encoded_query = urllib.parse.quote(topic_info["query"])
        date_filter = f"cdr:1,cd_min:{start_date.strftime('%m/%d/%Y')},cd_max:{end_date.strftime('%m/%d/%Y')}"
        google_url = f"https://www.google.com/search?q={encoded_query}&tbs={date_filter}&tbm=nws"
        
        report += f"## 📊 {topic_info['topic']}\n\n"
        report += f"**搜索词**：`{topic_info['query']}`\n\n"
        report += f"**相关关键词**：{topic_info['keywords']}\n\n"
        report += f"**链接**：[Google News搜索]({google_url})\n\n"
        report += "---\n\n"
    
    # 主要港股资讯网站
    report += "## 🔗 港股资讯门户\n\n"
    
    portals = [
        ("AAStocks 市场总览", "https://www.aastocks.com/tc/default.aspx"),
        ("香港经济日报 投资频道", "https://invest.hket.com/"),
        ("信报财经 港股版块", "https://www2.hkej.com/instantnews/hongkong"),
        ("经济通 港股频道", "https://www.etnet.com.hk/www/tc/stocks/index.php"),
    ]
    
    for name, url in portals:
        report += f"- [{name}]({url})\n"
    
    report += "\n---\n\n"
    report += f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
    
    return report


# 测试函数
if __name__ == "__main__":
    print("🧪 测试港股新闻链接生成器\n")
    print("=" * 60)
    
    # 测试1：腾讯
    print("\n📰 测试1：腾讯（0700）")
    result1 = get_hk_stock_news_links("0700", "腾讯控股", 7)
    print(result1[:1000])
    print("...")
    
    # 测试2：市场新闻
    print("\n\n📊 测试2：港股市场新闻")
    result2 = get_hk_market_news_links(3)
    print(result2[:800])
    print("...")
    
    print("\n✅ 测试完成！")
