"""
Finnhub API Integration for Hong Kong Stock News
优势：专业金融数据API，支持港股新闻，有免费额度
"""

import os
import finnhub
from typing import Annotated, List, Dict
from datetime import datetime, timedelta


def get_finnhub_client():
    """获取 Finnhub 客户端"""
    api_key = os.getenv('FINNHUB_API_KEY', '')
    if not api_key:
        raise ValueError("FINNHUB_API_KEY not found in environment variables")
    return finnhub.Client(api_key=api_key)


def get_finnhub_company_news(
    ticker_symbol: Annotated[str, "Stock ticker symbol (e.g., '0700.HK', 'AAPL')"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"]
) -> str:
    """
    从 Finnhub 获取公司新闻
    
    ⚠️ 重要提示：
    - Finnhub 免费账户**不支持港股**数据（.HK 后缀）
    - 支持美股、部分国际市场
    - 如需港股新闻，请使用 Google News 或 HKEXnews
    
    优势（非港股）：
    - 专业金融数据源
    - 包含新闻情绪分析
    - 多语言支持
    - 实时更新
    
    返回格式：
    - 新闻标题
    - 摘要
    - 来源
    - 发布时间
    - 情绪评分（正面/负面）
    - 相关度评分
    """
    try:
        client = get_finnhub_client()
        
        # 检测是否为港股
        is_hk_stock = False
        if ticker_symbol.replace('.', '').replace('HK', '').replace('HKG', '').isdigit():
            is_hk_stock = True
            ticker_clean = ticker_symbol.replace('.HK', '').replace('.HKG', '').zfill(4)
            ticker_formatted = f"{ticker_clean}.HK"
        else:
            ticker_formatted = ticker_symbol
        
        # 如果是港股，返回提示信息
        if is_hk_stock:
            return f"""# ⚠️ Finnhub 免费账户不支持港股

## 股票: {ticker_formatted}

Finnhub 的免费账户无法访问港股（.HK）数据。

### 建议使用以下替代方案：

1. **Google News** - 已集成，自动搜索港股专业媒体
   - 阿斯达克 (AAStocks)
   - 信报 (HKEJ)
   - 经济日报 (HKET)
   - 经济通 (ET Net)

2. **HKEXnews (披露易)** - 官方公告平台
   - 所有上市公司必须披露的信息
   - 最权威的数据来源

3. **升级 Finnhub 账户** - 如需专业港股数据
   - 访问 https://finnhub.io/pricing
   - 选择支持香港市场的套餐

---

**当前仍可使用 Finnhub 获取**：
- 美股新闻和数据
- 部分国际市场新闻
- 全球市场情绪分析

"""
        
        # 转换日期格式为 Finnhub 要求的格式（yyyy-mm-dd）
        # Finnhub API 接受 yyyy-mm-dd 格式
        
        # 获取公司新闻
        news_data = client.company_news(
            symbol=ticker_formatted,
            _from=start_date,
            to=end_date
        )
        
        if not news_data:
            return f"# Finnhub 新闻 - {ticker_formatted}\n\n⚠️ 未找到相关新闻\n\n"
        
        # 格式化输出
        report = f"# 📰 Finnhub 专业金融新闻 - {ticker_formatted}\n"
        report += f"## 时间范围: {start_date} 至 {end_date}\n"
        report += f"## 新闻数量: {len(news_data)} 条\n\n"
        report += "---\n\n"
        
        # 按日期倒序排列（最新的在前）
        news_data_sorted = sorted(news_data, key=lambda x: x.get('datetime', 0), reverse=True)
        
        for idx, article in enumerate(news_data_sorted, 1):
            # 转换时间戳
            timestamp = article.get('datetime', 0)
            if timestamp:
                publish_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            else:
                publish_time = "未知"
            
            title = article.get('headline', '无标题')
            summary = article.get('summary', '无摘要')
            source = article.get('source', '未知来源')
            url = article.get('url', '')
            category = article.get('category', '一般')
            related = article.get('related', '')
            
            report += f"### {idx}. {title}\n\n"
            report += f"**来源**: {source} | **分类**: {category} | **时间**: {publish_time}\n\n"
            
            if summary:
                report += f"**摘要**: {summary}\n\n"
            
            if url:
                report += f"**链接**: [阅读全文]({url})\n\n"
            
            if related:
                report += f"**相关**: {related}\n\n"
            
            report += "---\n\n"
        
        # 添加情绪分析提示
        report += "## 💡 使用建议\n\n"
        report += "### 新闻评估标准\n"
        report += "1. **重要性**: 标题关键词（业绩、评级、收购、监管）\n"
        report += "2. **来源权威性**: 主流财经媒体 > 普通媒体\n"
        report += "3. **时效性**: 最近24小时的新闻影响最大\n"
        report += "4. **相关性**: 是否直接提及公司名称或核心业务\n\n"
        
        report += "### 情绪判断\n"
        report += "- **正面关键词**: 超预期、上调、增持、突破、创新高\n"
        report += "- **负面关键词**: 预警、下调、减持、调查、处罚、暴跌\n"
        report += "- **中性关键词**: 公告、披露、会议、变动\n\n"
        
        return report
        
    except Exception as e:
        return f"# Finnhub 新闻获取失败\n\n❌ 错误: {str(e)}\n\n**可能原因**:\n- API Key 无效或过期\n- 网络连接问题\n- API 配额已用完\n- 股票代码格式不正确\n\n"


def get_finnhub_market_news(
    category: Annotated[str, "News category (e.g., 'general', 'forex', 'crypto')"] = "general",
    min_id: Annotated[int, "Minimum news ID (for pagination)"] = 0
) -> str:
    """
    从 Finnhub 获取市场整体新闻
    
    分类选项：
    - general: 一般市场新闻
    - forex: 外汇新闻
    - crypto: 加密货币新闻
    - merger: 并购新闻
    
    注意：这个API返回的是全球市场新闻，不限于港股
    """
    try:
        client = get_finnhub_client()
        
        # 获取市场新闻
        news_data = client.general_news(category=category, min_id=min_id)
        
        if not news_data:
            return f"# Finnhub 市场新闻 - {category}\n\n⚠️ 未找到相关新闻\n\n"
        
        # 格式化输出
        report = f"# 🌍 Finnhub 市场新闻 - {category.upper()}\n"
        report += f"## 新闻数量: {len(news_data)} 条\n\n"
        report += "---\n\n"
        
        # 只显示前15条最新新闻
        for idx, article in enumerate(news_data[:15], 1):
            timestamp = article.get('datetime', 0)
            if timestamp:
                publish_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            else:
                publish_time = "未知"
            
            title = article.get('headline', '无标题')
            summary = article.get('summary', '无摘要')
            source = article.get('source', '未知来源')
            url = article.get('url', '')
            category_tag = article.get('category', '一般')
            
            report += f"### {idx}. {title}\n\n"
            report += f"**来源**: {source} | **分类**: {category_tag} | **时间**: {publish_time}\n\n"
            
            if summary:
                # 限制摘要长度
                summary_short = summary[:300] + "..." if len(summary) > 300 else summary
                report += f"**摘要**: {summary_short}\n\n"
            
            if url:
                report += f"**链接**: [阅读全文]({url})\n\n"
            
            report += "---\n\n"
        
        return report
        
    except Exception as e:
        return f"# Finnhub 市场新闻获取失败\n\n❌ 错误: {str(e)}\n\n"


def get_finnhub_news_sentiment(
    ticker_symbol: Annotated[str, "Stock ticker symbol"]
) -> str:
    """
    获取 Finnhub 新闻情绪分析
    
    ⚠️ 重要：Finnhub 免费账户不支持港股（.HK）
    
    返回：
    - Buzz（讨论热度）
    - 情绪评分（正面/负面）
    - 文章数量统计
    """
    try:
        client = get_finnhub_client()
        
        # 检测是否为港股
        is_hk_stock = False
        if ticker_symbol.replace('.', '').replace('HK', '').replace('HKG', '').isdigit():
            is_hk_stock = True
            ticker_clean = ticker_symbol.replace('.HK', '').replace('.HKG', '').zfill(4)
            ticker_formatted = f"{ticker_clean}.HK"
        else:
            ticker_formatted = ticker_symbol
        
        # 如果是港股，返回提示
        if is_hk_stock:
            return f"# ⚠️ Finnhub 免费账户不支持港股情绪数据\n\n股票: {ticker_formatted}\n\n建议使用 Google News 或社交媒体数据进行情绪分析。\n\n"
        
        # 获取新闻情绪
        sentiment_data = client.news_sentiment(ticker_formatted)
        
        if not sentiment_data:
            return f"# Finnhub 新闻情绪 - {ticker_formatted}\n\n⚠️ 暂无情绪数据\n\n"
        
        report = f"# 📊 Finnhub 新闻情绪分析 - {ticker_formatted}\n\n"
        
        # Buzz 数据（讨论热度）
        buzz = sentiment_data.get('buzz', {})
        if buzz:
            report += "## 📈 讨论热度 (Buzz)\n\n"
            report += f"- **本周文章数**: {buzz.get('articlesInLastWeek', 0)}\n"
            report += f"- **本周热度**: {buzz.get('buzz', 0):.2f}\n"
            report += f"- **周热度变化**: {buzz.get('weeklyAverage', 0):.2f}\n\n"
        
        # 情绪评分
        sentiment = sentiment_data.get('sentiment', {})
        if sentiment:
            report += "## 😊 情绪评分\n\n"
            
            bearish = sentiment.get('bearishPercent', 0)
            bullish = sentiment.get('bullishPercent', 0)
            
            report += f"| 指标 | 数值 |\n"
            report += f"|------|------|\n"
            report += f"| 看多比例 | {bullish:.1f}% |\n"
            report += f"| 看空比例 | {bearish:.1f}% |\n"
            
            # 判断整体情绪
            if bullish > bearish + 10:
                overall = "🟢 偏向看多"
            elif bearish > bullish + 10:
                overall = "🔴 偏向看空"
            else:
                overall = "🟡 中性"
            
            report += f"\n**整体情绪**: {overall}\n\n"
        
        # 公司新闻评分
        company_score = sentiment_data.get('companyNewsScore', 0)
        sector_score = sentiment_data.get('sectorAverageNewsScore', 0)
        
        if company_score or sector_score:
            report += "## 📰 新闻评分\n\n"
            report += f"- **公司新闻评分**: {company_score:.2f}\n"
            report += f"- **行业平均评分**: {sector_score:.2f}\n\n"
            
            if company_score > sector_score:
                report += "✅ 公司新闻情绪优于行业平均\n\n"
            elif company_score < sector_score:
                report += "⚠️ 公司新闻情绪低于行业平均\n\n"
        
        report += "---\n\n"
        report += "## 💡 解读说明\n\n"
        report += "- **热度 > 1.5**: 讨论度显著增加，可能有重大事件\n"
        report += "- **看多 > 60%**: 市场情绪偏乐观\n"
        report += "- **看空 > 60%**: 市场情绪偏悲观\n"
        report += "- **新闻评分 > 0.5**: 正面新闻较多\n"
        report += "- **新闻评分 < -0.5**: 负面新闻较多\n\n"
        
        return report
        
    except Exception as e:
        return f"# Finnhub 情绪分析失败\n\n❌ 错误: {str(e)}\n\n"


# 测试函数
if __name__ == "__main__":
    # 测试港股新闻获取
    print("Testing Finnhub API...")
    print("\n1. Company News (0700.HK):")
    print(get_finnhub_company_news("0700.HK", "2026-01-15", "2026-01-23"))
    
    print("\n2. News Sentiment (0700.HK):")
    print(get_finnhub_news_sentiment("0700.HK"))
    
    print("\n3. Market News:")
    print(get_finnhub_market_news("general"))
