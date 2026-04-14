"""
智能股票代码识别器
使用LLM来识别和确认用户输入的股票代码
"""

import os
import yfinance as yf
from typing import List, Dict, Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


def search_hk_stocks(query: str) -> List[Dict[str, str]]:
    """
    搜索港股，返回可能的匹配结果
    
    Args:
        query: 用户输入的查询（可能是数字代码、公司名称等）
    
    Returns:
        匹配的股票列表，每个包含 {code, name, symbol}
    """
    candidates = []
    seen_codes = set()  # 避免重复
    
    # 清理输入：移除常见的标点符号和空格
    cleaned_query = query.strip()
    # 移除常见的标点符号（顿号、逗号、句号等）
    cleaned_query = cleaned_query.replace('、', '').replace(',', '').replace('.', '').replace('，', '').replace('。', '').strip()
    
    # 如果输入是纯数字，尝试不同的填充方式
    if cleaned_query.isdigit():
        raw_number = cleaned_query
        
        # 港股代码通常是4位数字
        padded = raw_number.zfill(4)
        ticker_symbol = f"{padded}.HK"
        
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            info = ticker_obj.info
            
            # 检查是否是有效的股票
            if info and info.get('symbol') and info.get('exchange') in ['HKG', 'HKD']:
                code = padded
                if code not in seen_codes:
                    candidates.append({
                        'code': code,
                        'name': info.get('longName', info.get('shortName', 'Unknown')),
                        'symbol': ticker_symbol,
                        'currency': info.get('currency', 'HKD'),
                        'exchange': info.get('exchange', 'HKG')
                    })
                    seen_codes.add(code)
        except Exception as e:
            pass
    
    # 也可以尝试直接搜索（如果用户输入的是公司名称）
    else:
        # 移除常见的后缀和标点符号
        clean_query = cleaned_query.replace('.HK', '').replace('.HKG', '').strip()
        
        # 如果是数字+字母组合，直接尝试
        if clean_query:
            try:
                ticker_symbol = f"{clean_query}.HK"
                ticker_obj = yf.Ticker(ticker_symbol)
                info = ticker_obj.info
                
                if info and info.get('symbol'):
                    candidates.append({
                        'code': clean_query,
                        'name': info.get('longName', info.get('shortName', 'Unknown')),
                        'symbol': ticker_symbol,
                        'currency': info.get('currency', 'HKD'),
                        'exchange': info.get('exchange', 'HKG')
                    })
            except Exception as e:
                pass
    
    return candidates


def llm_resolve_ticker(user_input: str, candidates: List[Dict[str, str]], market: str = 'HKEX') -> Optional[str]:
    """
    使用LLM来帮助用户选择正确的股票
    
    Args:
        user_input: 用户原始输入
        candidates: 候选股票列表
        market: 市场类型
    
    Returns:
        确认后的股票代码，或None（如果用户取消）
    """
    if not candidates:
        return None
    
    # 如果只有一个候选，直接使用
    if len(candidates) == 1:
        return candidates[0]['symbol'].replace('.HK', '').replace('.HKG', '')
    
    # 多个候选时，让LLM帮助选择
    try:
        # 检查是否有OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Warning: OPENAI_API_KEY not set, using first candidate")
            return candidates[0]['code']
        
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=api_key,
        )
        
        candidates_text = "\n".join([
            f"{i+1}. code: {c['code']}, name: {c['name']}, exchange: {c['exchange']}"
            for i, c in enumerate(candidates)
        ])
        
        system_prompt = f"""You help map user input to the correct Hong Kong listing.

User typed: "{user_input}"

Candidates:
{candidates_text}

Pick the best match. If the input is ambiguous (e.g. a short digit), prefer the most liquid / well-known listing.

Reply with ONLY the option number (1, 2, 3, ...), no other text.
If unsure, reply "1".
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"User input: {user_input}")
        ]
        
        response = llm.invoke(messages)
        choice = response.content.strip()
        
        # 解析LLM的选择
        try:
            index = int(choice) - 1
            if 0 <= index < len(candidates):
                return candidates[index]['code']
        except:
            pass
        
        # 默认返回第一个
        return candidates[0]['code']
        
    except Exception as e:
        print(f"LLM resolution failed: {e}")
        # Fallback到第一个候选
        return candidates[0]['code']


def smart_ticker_input(user_input: str, interactive: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    智能股票代码输入和确认
    
    Args:
        user_input: 用户输入的股票代码
        interactive: 是否使用交互式确认
    
    Returns:
        (确认后的代码, 公司名称) 或 (None, None)
    """
    market = os.getenv('DEFAULT_MARKET', 'HK')
    
    # 对于美股，直接使用原输入
    if market != 'HKEX':
        return user_input.upper(), None
    
    print(f"\n🔍 Looking up ticker: {user_input}...")
    candidates = search_hk_stocks(user_input)
    
    if not candidates:
        print(f"❌ No HKEX match for: {user_input}")
        return None, None
    
    if len(candidates) == 1:
        stock = candidates[0]
        print(f"\n✅ Match found:")
        print(f"   Code: {stock['code']}")
        print(f"   Name: {stock['name']}")
        print(f"   Exchange: {stock['exchange']}")
        return stock['code'], stock['name']
    
    print(f"\n🤔 {len(candidates)} possible matches:")
    for i, stock in enumerate(candidates, 1):
        print(f"   {i}. {stock['code']} - {stock['name']} ({stock['exchange']})")
    
    if interactive:
        while True:
            choice = input(
                f"\nChoose [1-{len(candidates)}] or q to cancel: "
            ).strip()
            
            if choice.lower() == 'q':
                print("Cancelled.")
                return None, None
            
            try:
                index = int(choice) - 1
                if 0 <= index < len(candidates):
                    selected = candidates[index]
                    print(f"\n✅ Selected: {selected['code']} - {selected['name']}")
                    return selected['code'], selected['name']
                else:
                    print(f"❌ Enter a number from 1 to {len(candidates)}")
            except ValueError:
                print("❌ Enter a valid number")
    else:
        resolved = llm_resolve_ticker(user_input, candidates, market)
        if resolved:
            for stock in candidates:
                if stock['code'] == resolved:
                    print(f"\n🤖 LLM picked: {stock['code']} - {stock['name']}")
                    return stock['code'], stock['name']
        
        # Fallback
        return candidates[0]['code'], candidates[0]['name']


def normalize_ticker_with_confirmation(user_input: str, interactive: bool = True) -> Optional[str]:
    """
    标准化ticker代码，带智能确认
    
    这是主要的入口函数，整合了搜索、确认和标准化
    
    Args:
        user_input: 用户输入
        interactive: 是否交互式确认
    
    Returns:
        标准化后的ticker代码（如 "0700"），或None
    """
    code, name = smart_ticker_input(user_input, interactive)
    
    if code:
        # 确保是4位数格式（港股）
        market = os.getenv('DEFAULT_MARKET', 'HK')
        if market == 'HKEX' and code.isdigit():
            return code.zfill(4)
        return code
    
    return None
