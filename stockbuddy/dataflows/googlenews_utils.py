"""
Google News Scraper
Updated: 2026-01-23
Supports new Google News HTML structure
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import random
import urllib.parse
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
)


def is_rate_limited(response):
    """Check if the response indicates rate limiting (status code 429)"""
    return response.status_code == 429


@retry(
    retry=(retry_if_result(is_rate_limited)),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
)
def make_request(url, headers):
    """Make a request with retry logic for rate limiting"""
    # Random delay before each request to avoid detection
    time.sleep(random.uniform(2, 6))
    response = requests.get(url, headers=headers, timeout=15)
    return response


def getNewsData(query, start_date, end_date):
    """
    Scrape Google News search results for a given query and date range.
    
    Updated for 2026 Google News HTML structure.
    
    Args:
    query: str - search query
    start_date: str - start date in the format yyyy-mm-dd or mm/dd/yyyy
    end_date: str - end date in the format yyyy-mm-dd or mm/dd/yyyy
        
    Returns:
        list of dict: Each dict contains title, link, snippet, date, source
    """
    # 转换日期格式
    if "-" in start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        start_date = start_date.strftime("%m/%d/%Y")
    if "-" in end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        end_date = end_date.strftime("%m/%d/%Y")

    # 更新 User-Agent 为更新的版本
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    news_results = []
    page = 0
    max_pages = 3  # 限制最多3页，避免被封

    while page < max_pages:
        offset = page * 10
        url = (
            f"https://www.google.com/search?q={query}"
            f"&tbs=cdr:1,cd_min:{start_date},cd_max:{end_date}"
            f"&tbm=nws&start={offset}"
        )

        try:
            response = make_request(url, headers)
            
            if response.status_code != 200:
                print(f"⚠️ Google News 请求失败: HTTP {response.status_code}")
                break
            
            # 使用 response.text 而不是 response.content
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 调试：保存 HTML
            if page == 0:
                with open('/Users/hesiyu/Desktop/StockBuddy/google_news_function_debug.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)  # 直接保存 response.text
                print(f"💾 HTML 已保存到: google_news_function_debug.html (response.text)")
            
            # 新的选择器：查找新闻容器
            # 注意：第一个 div.Gx5Zad 通常是筛选器，从第二个开始才是新闻
            main_containers = soup.select("div.Gx5Zad")
            
            # 调试输出
            print(f"🔍 找到 {len(main_containers)} 个 div.Gx5Zad 容器")
            
            # 尝试备用选择器
            if not main_containers:
                print("  尝试备用选择器...")
                # 直接查找新闻项
                news_items_direct = soup.select("div.X7NTVe")
                print(f"  直接找到 {len(news_items_direct)} 个 div.X7NTVe")
                
                if news_items_direct:
                    main_containers = [soup]  # 使用整个页面作为容器
                else:
                    print(f"⚠️ 未找到新闻容器 (页面 {page})")
                    break
            
            if not main_containers:
                print(f"⚠️ 未找到新闻容器 (页面 {page})")
                break
            
            # 跳过第一个容器（筛选器），从第二个开始
            news_container = main_containers[1] if len(main_containers) > 1 else main_containers[0]
            
            # 每条新闻在 div.X7NTVe 中
            news_items = news_container.select("div.X7NTVe")
            
            if not news_items:
                # 备用选择器：直接查找所有新闻项
                news_items = soup.select("div.X7NTVe")
            
            if not news_items:
                print(f"⚠️ 未找到新闻项 (页面 {page})")
                break

            print(f"✅ 找到 {len(news_items)} 条新闻 (页面 {page})")

            for el in news_items:
                try:
                    # 提取链接
                    link_tag = el.find("a", class_="tHmfQe")
                    if not link_tag or not link_tag.get("href"):
                        continue
                    
                    href = link_tag["href"]
                    
                    # 解析 Google 重定向链接
                    if "/url?" in href:
                        try:
                            parsed = urllib.parse.urlparse(href)
                            params = urllib.parse.parse_qs(parsed.query)
                            actual_url = params.get("url", [href])[0]
                        except:
                            actual_url = href
                    else:
                        actual_url = href
                    
                    # 提取标题
                    h3_tag = el.find("h3")
                    if not h3_tag:
                        continue
                    title = h3_tag.get_text().strip()
                    
                    # 提取来源
                    source_tag = el.select_one("span.MDvRSc.KogRLb")
                    source = source_tag.get_text().strip() if source_tag else "Unknown"
                    
                    # 提取时间
                    date_tag = el.select_one("span.UK5aid.MDvRSc")
                    date = date_tag.get_text().strip() if date_tag else "Unknown"
                    
                    # 提取摘要（如果有）
                    # 新版 Google News 通常不在列表视图中显示摘要
                    snippet = ""
                    snippet_tag = el.select_one("div.GI74Re")
                    if snippet_tag:
                        snippet = snippet_tag.get_text().strip()
                    
                    # 如果没有摘要，尝试获取所有文本作为替代
                    if not snippet:
                        all_text = el.get_text()
                        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                        # 找到最长的一行作为摘要（排除标题和来源）
                        for line in lines:
                            if len(line) > 50 and line != title and source not in line:
                                snippet = line[:200]  # 限制长度
                                break
                    
                    # 如果还是没有摘要，使用标题
                    if not snippet:
                        snippet = title
                    
                    news_results.append(
                        {
                            "link": actual_url,
                            "title": title,
                            "snippet": snippet,
                            "date": date,
                            "source": source,
                        }
                    )
                    
                except Exception as e:
                    print(f"⚠️ 解析新闻项失败: {e}")
                    continue

            # 检查是否还有更多页面
            next_link = soup.find("a", id="pnnext")
            if not next_link or len(news_items) == 0:
                break

            page += 1

        except Exception as e:
            print(f"❌ 抓取失败 (页面 {page}): {e}")
            break

    print(f"✅ 总共抓取到 {len(news_results)} 条新闻")
    return news_results
