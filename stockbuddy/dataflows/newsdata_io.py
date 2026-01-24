"""
Newsdata.io API Integration
免费新闻聚合 API，支持多语言新闻
官网: https://newsdata.io
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time


def get_newsdata_client():
    """获取 Newsdata.io API Key"""
    api_key = os.getenv('NEWSDATA_API_KEY', 'pub_7d04211707814b72aa50a11f7ea9859c')
    return api_key


def get_newsdata_news(
    query: str,
    language: str = "zh",  # zh = 中文
    country: Optional[str] = None,  # cn, hk, tw
    category: Optional[List[str]] = None,  # business, technology
    days_back: int = 7,
    max_results: int = 10
) -> str:
    """
    从 Newsdata.io 获取新闻
    
    Args:
        query: 搜索关键词（如公司名、股票代码）
        language: 语言代码 (zh=中文, en=英文)
        country: 国家代码 (cn=中国, hk=香港, tw=台湾)
        category: 新闻类别列表 (business, technology, etc.)
        days_back: 回溯天数
        max_results: 最大返回结果数
        
    Returns:
        格式化的新闻报告（Markdown）
    """
    api_key = get_newsdata_client()
    
    # 构建请求参数
    params = {
        'apikey': api_key,
        'q': query,
        'language': language,
    }
    
    # 添加国家筛选
    if country:
        params['country'] = country
    
    # 添加分类筛选
    if category:
        params['category'] = ','.join(category)
    
    # 日期范围（免费版可能不支持，但可以尝试）
    # from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    # params['from_date'] = from_date
    
    # 限制结果数量
    params['size'] = min(max_results, 10)  # 免费版限制为10
    
    try:
        # 发送请求
        response = requests.get(
            'https://newsdata.io/api/1/news',
            params=params,
            timeout=10
        )
        
        if response.status_code != 200:
            return f"❌ Newsdata.io API 请求失败: HTTP {response.status_code}"
        
        data = response.json()
        
        if data.get('status') != 'success':
            error_msg = data.get('results', {}).get('message', 'Unknown error')
            return f"❌ Newsdata.io API 错误: {error_msg}"
        
        results = data.get('results', [])
        total_results = data.get('totalResults', 0)
        
        if not results:
            return f"⚠️ 未找到关于 '{query}' 的新闻"
        
        # 格式化输出
        report = f"# 📰 Newsdata.io 新闻搜索\n\n"
        report += f"**搜索关键词**: {query}\n"
        report += f"**语言**: {language}\n"
        if country:
            report += f"**国家/地区**: {country}\n"
        report += f"**找到**: {total_results} 条新闻 (显示 {len(results)} 条)\n"
        report += f"**数据来源**: Newsdata.io\n\n"
        report += "---\n\n"
        
        # 格式化每条新闻
        for i, article in enumerate(results, 1):
            title = article.get('title', 'N/A')
            description = article.get('description', '')
            link = article.get('link', '')
            source = article.get('source_name', 'Unknown')
            pub_date = article.get('pubDate', 'N/A')
            category_list = article.get('category', [])
            
            # 格式化发布时间
            try:
                if pub_date != 'N/A':
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    pub_date_formatted = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    pub_date_formatted = pub_date
            except:
                pub_date_formatted = pub_date
            
            report += f"## {i}. {title}\n\n"
            report += f"**来源**: {source} | **时间**: {pub_date_formatted}\n"
            
            if category_list:
                report += f"**分类**: {', '.join(category_list)}\n"
            
            if description:
                report += f"\n{description}\n"
            
            if link:
                report += f"\n**链接**: {link}\n"
            
            report += "\n---\n\n"
        
        # 添加使用提示
        report += "## ℹ️ 使用说明\n\n"
        report += "- 数据来源: Newsdata.io API\n"
        report += "- 免费版限制: 每次最多 10 条新闻\n"
        report += "- 完整内容需要付费版 (PAID PLANS)\n"
        report += "- 情绪分析需要专业版 (PROFESSIONAL PLANS)\n"
        
        return report
        
    except requests.RequestException as e:
        return f"❌ Newsdata.io 请求异常: {str(e)}"
    except Exception as e:
        return f"❌ Newsdata.io 处理失败: {str(e)}"


def get_newsdata_hk_stock_news(
    ticker_symbol: str,
    company_name: str = "",
    days_back: int = 7,
    max_results: int = 10
) -> str:
    """
    获取港股公司新闻（专门优化）
    
    Args:
        ticker_symbol: 港股代码（如 0700, 9988）
        company_name: 公司中文名称
        days_back: 回溯天数
        max_results: 最大结果数
        
    Returns:
        格式化的新闻报告
    """
    # 构建搜索词
    query = company_name if company_name else ticker_symbol
    
    # 如果有公司名，也包含股票代码
    if company_name and ticker_symbol:
        query = f"{company_name} OR {ticker_symbol}"
    
    # 获取中文新闻（来自中国、香港、台湾）
    report = get_newsdata_news(
        query=query,
        language="zh",
        country="cn,hk,tw",  # 中国大陆 + 香港 + 台湾
        category=["business", "technology"],
        days_back=days_back,
        max_results=max_results
    )
    
    return report


def get_newsdata_market_news(
    query: str = "港股 OR 恒生指数 OR 香港股市",
    days_back: int = 3,
    max_results: int = 10
) -> str:
    """
    获取港股市场整体新闻
    
    Args:
        query: 搜索关键词（默认为港股相关）
        days_back: 回溯天数
        max_results: 最大结果数
        
    Returns:
        格式化的新闻报告
    """
    report = get_newsdata_news(
        query=query,
        language="zh",
        country="cn,hk,tw",
        category=["business"],
        days_back=days_back,
        max_results=max_results
    )
    
    return report


# 测试函数
if __name__ == "__main__":
    print("=" * 80)
    print("测试 Newsdata.io API")
    print("=" * 80)
    
    # 测试1: 搜索腾讯新闻
    print("\n测试1: 搜索'腾讯'新闻\n")
    result1 = get_newsdata_news("腾讯", language="zh", max_results=5)
    print(result1)
    
    # 测试2: 港股新闻
    print("\n" + "=" * 80)
    print("\n测试2: 港股新闻（0700 腾讯）\n")
    result2 = get_newsdata_hk_stock_news("0700", "腾讯", max_results=5)
    print(result2)
    
    # 测试3: 市场新闻
    print("\n" + "=" * 80)
    print("\n测试3: 港股市场新闻\n")
    result3 = get_newsdata_market_news(max_results=5)
    print(result3)
