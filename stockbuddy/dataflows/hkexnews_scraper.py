"""
HKEXnews (披露易) Web Scraper
官方披露平台 - 所有港股上市公司公告的唯一来源
"""

from typing import Annotated, List, Dict
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time


def get_hkex_announcements(
    stock_code: Annotated[str, "Hong Kong stock code (e.g., '0700', '9988')"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    max_results: Annotated[int, "Maximum number of announcements to return"] = 50
) -> str:
    """
    从披露易(HKEXnews)获取公司公告
    
    这是港股最重要的信息来源！所有上市公司必须在此发布公告。
    
    公告类型包括：
    - 財務報告：年報、中期報告、季報
    - 股權披露：大股東增減持
    - 內幕消息：價格敏感信息
    - 通告：收購、配股、供股
    - 業績公告：盈利預告、業績報告
    """
    
    # Normalize stock code (5 digits with leading zeros)
    clean_code = stock_code.replace('.HK', '').replace('.HKG', '').zfill(5)
    
    result = f"# 披露易 (HKEXnews) 公告 - {stock_code}\n"
    result += f"# 時間範圍: {start_date} 至 {end_date}\n"
    result += f"# 股票代碼: {clean_code}\n\n"
    
    # HKEXnews search URL
    base_url = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
    search_url = f"{base_url}?stock={clean_code}"
    
    result += f"## 披露易搜索鏈接\n"
    result += f"{search_url}\n\n"
    
    # TODO: 实现实际的网页爬取
    result += "## ⚠️ 實現狀態\n\n"
    result += "### 當前階段：提供鏈接（Phase 1）\n"
    result += "- ✅ 生成正確的披露易搜索鏈接\n"
    result += "- ❌ 自動爬取公告內容（待實現）\n"
    result += "- ❌ 解析公告類型和重要性（待實現）\n\n"
    
    result += "### Phase 2 實現計劃\n"
    result += "```python\n"
    result += "# 1. 使用requests + BeautifulSoup爬取\n"
    result += "response = requests.get(search_url, headers=headers)\n"
    result += "soup = BeautifulSoup(response.content, 'html.parser')\n\n"
    result += "# 2. 解析公告列表\n"
    result += "announcements = soup.find_all('div', class_='announcement-item')\n\n"
    result += "# 3. 提取關鍵信息\n"
    result += "for ann in announcements:\n"
    result += "    title = ann.find('h3').text\n"
    result += "    date = ann.find('span', class_='date').text\n"
    result += "    category = ann.find('span', class_='category').text\n"
    result += "    link = ann.find('a')['href']\n"
    result += "```\n\n"
    
    result += "### 重要公告類型優先級\n"
    result += "| 優先級 | 公告類型 | 影響 |\n"
    result += "|--------|---------|------|\n"
    result += "| 🔴 最高 | 盈利預警、內幕消息 | 股價敏感 |\n"
    result += "| 🟠 高 | 年報/中期報告 | 基本面重要 |\n"
    result += "| 🟡 中 | 大股東增減持 | 情緒影響 |\n"
    result += "| 🟢 低 | 一般通告 | 參考信息 |\n\n"
    
    result += "### 實施建議\n"
    result += "1. **短期方案**：提供鏈接，由LLM提示用戶手動查看\n"
    result += "2. **中期方案**：實現基礎爬蟲，獲取公告標題和日期\n"
    result += "3. **長期方案**：下載PDF，提取全文內容，AI分析\n\n"
    
    result += "### 技術考量\n"
    result += "- **反爬蟲**: HKEXnews可能有rate limit，需要添加延遲\n"
    result += "- **動態加載**: 部分內容可能需要Selenium\n"
    result += "- **PDF解析**: 公告通常是PDF格式，需要PyPDF2或pdfplumber\n"
    result += "- **合規性**: 確保符合網站使用條款\n\n"
    
    # 臨時：提供一些常見公告類型的說明
    result += "## 常見公告類型說明\n\n"
    result += "### 📊 財務報告\n"
    result += "- **年度報告**: 最全面的財務信息\n"
    result += "- **中期報告**: 半年業績\n"
    result += "- **季度報告**: 部分公司提供\n\n"
    
    result += "### 💰 公司行動\n"
    result += "- **配股/供股**: 發行新股融資\n"
    result += "- **股息宣派**: 分紅公告\n"
    result += "- **股份回購**: 公司買回自己的股票\n\n"
    
    result += "### 🔔 重大事項\n"
    result += "- **收購/合併**: M&A交易\n"
    result += "- **關連交易**: 與關聯方的交易\n"
    result += "- **訴訟公告**: 法律糾紛\n"
    result += "- **高管變動**: 董事/CEO變更\n\n"
    
    return result


def get_institutional_ratings(
    stock_code: Annotated[str, "Stock code"],
    lookback_days: Annotated[int, "Number of days to look back"] = 30
) -> str:
    """
    獲取大行評級變動
    
    重要性：⭐️⭐️⭐️⭐️⭐️
    大行（投資銀行）的評級變動對港股影響巨大！
    
    主要來源：
    - 高盛 (Goldman Sachs)
    - 摩根士丹利 (Morgan Stanley)
    - 花旗 (Citigroup)
    - 瑞銀 (UBS)
    - 大摩 (JP Morgan)
    - 匯豐 (HSBC)
    - 中金 (CICC)
    """
    
    result = f"# 大行評級 - {stock_code}\n"
    result += f"# 過去{lookback_days}天\n\n"
    
    result += "## ⚠️ 功能狀態：待實現\n\n"
    
    result += "### 數據來源選項\n\n"
    result += "#### 選項1：財經媒體爬取\n"
    result += "從以下網站爬取評級新聞：\n"
    result += "- 信報 (HKEJ)\n"
    result += "- 經濟日報 (HKET)\n"
    result += "- 阿斯達克 (AAStocks)\n"
    result += "- 經濟通 (ETNet)\n\n"
    
    result += "#### 選項2：專業數據API\n"
    result += "- **TipRanks API**: 提供分析師評級\n"
    result += "- **Benzinga API**: 評級變動通知\n"
    result += "- **FactSet**: 專業但昂貴\n\n"
    
    result += "#### 選項3：社交媒體監控\n"
    result += "- Twitter/X: 搜索 `${stock_code} 評級`\n"
    result += "- 雪球: 大行評級討論\n\n"
    
    result += "### 評級影響分析\n"
    result += "| 評級變動 | 平均股價反應 | 時間窗口 |\n"
    result += "|---------|-------------|----------|\n"
    result += "| 升級 (Upgrade) | +3% ~ +8% | 1-3天 |\n"
    result += "| 降級 (Downgrade) | -5% ~ -12% | 1-3天 |\n"
    result += "| 目標價上調 | +2% ~ +5% | 1-2天 |\n"
    result += "| 目標價下調 | -3% ~ -7% | 1-2天 |\n\n"
    
    result += "### 實施優先級\n"
    result += "- 🔴 **緊急**: 對交易決策影響極大\n"
    result += "- 📊 **難度**: 中等（需要網頁爬蟲或API訂閱）\n"
    result += "- 💰 **成本**: 免費方案存在（爬蟲）或付費API\n\n"
    
    return result


def get_stock_connect_flow(
    stock_code: Annotated[str, "Stock code"],
    date: Annotated[str, "Date in yyyy-mm-dd format"]
) -> str:
    """
    獲取港股通資金流向（北水/南下資金）
    
    重要性：⭐️⭐️⭐️⭐️⭐️
    港股通是港股最重要的資金來源之一！
    
    數據說明：
    - 北水: 內地資金流入香港（買入）
    - 南水: 香港資金流入內地（較少關注）
    - 每日額度: 420億港元
    - 餘額: 當日未使用額度
    """
    
    result = f"# 港股通資金流向 - {stock_code}\n"
    result += f"# 日期: {date}\n\n"
    
    result += "## ⚠️ 功能狀態：待實現\n\n"
    
    result += "### 數據來源\n\n"
    result += "#### 官方來源（免費但需爬取）\n"
    result += "1. **港交所官網**: https://www.hkex.com.hk\n"
    result += "   - 每日公布港股通成交數據\n"
    result += "   - 需要爬蟲技術\n\n"
    
    result += "#### 第三方API（付費）\n"
    result += "1. **Wind資訊**: 專業金融數據終端\n"
    result += "2. **同花順API**: 提供港股通數據\n"
    result += "3. **Choice數據**: 東方財富旗下\n\n"
    
    result += "#### 財經媒體（免費）\n"
    result += "1. **經濟通**: 每日更新港股通數據\n"
    result += "2. **阿斯達克**: 實時港股通資金流\n\n"
    
    result += "### 關鍵指標\n"
    result += "| 指標 | 說明 | 影響 |\n"
    result += "|------|------|------|\n"
    result += "| 淨流入 | 北水買入 - 賣出 | 正值看多 |\n"
    result += "| 持股佔比 | 北水持股/總股本 | 高代表受內地追捧 |\n"
    result += "| 連續流入天數 | 持續買入 | 趨勢性信號 |\n"
    result += "| 額度使用率 | 使用額度/總額度 | 熱度指標 |\n\n"
    
    result += "### 實施建議\n"
    result += "- **短期**: 從財經媒體爬取每日匯總數據\n"
    result += "- **中期**: 接入專業API獲取個股明細\n"
    result += "- **長期**: 實時監控，建立預警系統\n\n"
    
    return result


# 使用示例
if __name__ == "__main__":
    # 測試HKEXnews
    print(get_hkex_announcements("9988", "2026-01-01", "2026-01-22"))
    print("\n" + "="*80 + "\n")
    
    # 測試大行評級
    print(get_institutional_ratings("9988"))
    print("\n" + "="*80 + "\n")
    
    # 測試港股通
    print(get_stock_connect_flow("9988", "2026-01-22"))
