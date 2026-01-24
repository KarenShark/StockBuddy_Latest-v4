"""
Hong Kong Market Configuration
Complete configuration for adapting the trading system to Hong Kong market.
"""

import os

# Hong Kong Market Configuration
HK_MARKET_CONFIG = {
    # ============================================
    # Market Identification
    # ============================================
    "market": "HKEX",
    "market_name": "Hong Kong Stock Exchange",
    "market_name_zh": "香港交易所",
    "country": "Hong Kong",
    "currency": "HKD",
    "timezone": "Asia/Hong_Kong",
    "utc_offset": "+08:00",
    "language": "zh-Hant",  # Traditional Chinese
    
    # ============================================
    # Trading Hours (HKT - Hong Kong Time)
    # ============================================
    "trading_hours": {
        "pre_market_auction": {
            "start": "09:00",
            "end": "09:30",
            "description": "開市競價時段"
        },
        "morning_session": {
            "start": "09:30",
            "end": "12:00",
            "description": "早市"
        },
        "lunch_break": {
            "start": "12:00",
            "end": "13:00",
            "description": "午休"
        },
        "afternoon_session": {
            "start": "13:00",
            "end": "16:00",
            "description": "午市"
        },
        "closing_auction": {
            "start": "16:00",
            "end": "16:10",
            "description": "收市競價時段"
        }
    },
    
    # ============================================
    # Trading Rules
    # ============================================
    "trading_rules": {
        "settlement_cycle": "T+2",  # Trade date + 2 business days
        "short_selling_allowed": True,
        "short_selling_restrictions": "Designated securities only",
        "price_limit": None,  # No daily price limit
        "circuit_breaker": {
            "enabled": True,
            "trigger": "Market-wide volatility",
            "cooling_period": "5-60 minutes"
        },
        "minimum_price_fluctuation": "Varies by price level",  # See tick_size_table
        "board_lot_size": "Varies by stock",  # Each stock has different board lot
    },
    
    # ============================================
    # Tick Size Table (Price Spread)
    # ============================================
    "tick_size_table": [
        {"price_range": (0.01, 0.25), "tick_size": 0.001},
        {"price_range": (0.25, 0.50), "tick_size": 0.005},
        {"price_range": (0.50, 10.00), "tick_size": 0.010},
        {"price_range": (10.00, 20.00), "tick_size": 0.020},
        {"price_range": (20.00, 100.00), "tick_size": 0.050},
        {"price_range": (100.00, 200.00), "tick_size": 0.100},
        {"price_range": (200.00, 500.00), "tick_size": 0.200},
        {"price_range": (500.00, 1000.00), "tick_size": 0.500},
        {"price_range": (1000.00, 2000.00), "tick_size": 1.000},
        {"price_range": (2000.00, 5000.00), "tick_size": 2.000},
        {"price_range": (5000.00, 9995.00), "tick_size": 5.000},
    ],
    
    # ============================================
    # Transaction Costs
    # ============================================
    "transaction_costs": {
        "stamp_duty": {
            "rate": 0.0013,  # 0.13%
            "description": "印花稅",
            "applies_to": "Both buy and sell",
            "collector": "Hong Kong Government"
        },
        "trading_fee": {
            "rate": 0.00005,  # 0.005%
            "description": "交易費",
            "applies_to": "Both buy and sell",
            "collector": "HKEX"
        },
        "transaction_levy": {
            "rate": 0.0000565,  # 0.00565%
            "description": "交易徵費",
            "applies_to": "Both buy and sell",
            "collector": "SFC"
        },
        "frc_transaction_levy": {
            "rate": 0.00000015,  # 0.000015%
            "description": "財務匯報局交易徵費",
            "applies_to": "Both buy and sell",
            "collector": "FRC"
        },
        "clearing_fee": {
            "rate": 0.00002,  # 0.002%
            "min_charge": 2.00,
            "max_charge": 100.00,
            "description": "中央結算費",
            "currency": "HKD"
        },
        "brokerage": {
            "rate": 0.0003,  # Typical: 0.03% - 0.25%
            "description": "經紀佣金",
            "note": "Varies by broker, negotiable"
        },
        "estimated_total_one_way": 0.0014,  # ~0.14% minimum
        "estimated_total_round_trip": 0.0028,  # ~0.28% minimum
    },
    
    # ============================================
    # Stock Code Format
    # ============================================
    "stock_code_format": {
        "digits": 4,  # Hong Kong stocks are 4 digits
        "padding": "0",  # Pad with zeros on the left
        "suffix": ".HK",  # Yahoo Finance format
        "examples": ["0700.HK", "9988.HK", "0005.HK", "0001.HK"],
        "naming_convention": "4-digit code with leading zeros"
    },
    
    # ============================================
    # Market Indices
    # ============================================
    "market_indices": {
        "HSI": {
            "name": "Hang Seng Index",
            "name_zh": "恒生指數",
            "ticker": "^HSI",
            "description": "Main benchmark index",
            "constituents": 82  # As of recent update
        },
        "HSCEI": {
            "name": "Hang Seng China Enterprises Index",
            "name_zh": "恒生中國企業指數",
            "ticker": "^HSCE",
            "description": "H-shares index",
            "constituents": 50
        },
        "HSTECH": {
            "name": "Hang Seng TECH Index",
            "name_zh": "恒生科技指數",
            "ticker": "^HSTECH",
            "description": "Technology stocks index",
            "constituents": 30
        }
    },
    
    # ============================================
    # Data Sources Configuration
    # ============================================
    "data_sources": {
        "primary": {
            "stock_data": "yfinance",  # Yahoo Finance supports HK stocks well
            "fundamentals": "yfinance",
            "news": "hk_news_sources",  # Custom HK news module
            "technical_indicators": "yfinance"
        },
        "supplementary": {
            "company_announcements": "hkexnews",  # 披露易
            "sentiment": "lihkg",  # 連登討論區
            "insider_trading": "hkexnews",
            "market_data": "aastocks",  # 阿斯達克
        },
        "enabled_integrations": [
            "yfinance",
            "hkex_integration",
            "hk_news_sources",
            "lihkg_integration",
            "google_news_hk"
        ]
    },
    
    # ============================================
    # Regulatory Environment
    # ============================================
    "regulatory": {
        "primary_regulator": {
            "name": "Securities and Futures Commission",
            "name_zh": "證券及期貨事務監察委員會",
            "abbreviation": "SFC",
            "website": "https://www.sfc.hk"
        },
        "exchange": {
            "name": "Hong Kong Exchanges and Clearing Limited",
            "name_zh": "香港交易及結算所有限公司",
            "abbreviation": "HKEX",
            "website": "https://www.hkex.com.hk"
        },
        "disclosure_platform": {
            "name": "HKEXnews",
            "name_zh": "披露易",
            "website": "https://www.hkexnews.hk"
        },
        "listing_rules": "Main Board and GEM (Growth Enterprise Market)",
        "corporate_governance_code": "Applicable to all listed companies"
    },
    
    # ============================================
    # Market Characteristics
    # ============================================
    "market_characteristics": {
        "stock_connect": {
            "enabled": True,
            "description": "滬港通 / 深港通",
            "northbound": "Hong Kong investors buying mainland stocks",
            "southbound": "Mainland investors buying Hong Kong stocks",
            "daily_quota": "HKD 42 billion (southbound)"
        },
        "ah_premium": {
            "description": "A股H股溢價",
            "note": "Price difference between A-shares and H-shares"
        },
        "currency_peg": {
            "description": "港元與美元掛鈎",
            "rate": "~7.75-7.85 HKD per USD",
            "system": "Linked Exchange Rate System"
        },
        "market_features": [
            "International financial center",
            "Gateway to China",
            "High proportion of Chinese companies",
            "Dual-class shares allowed",
            "T+2 settlement",
            "No price limits",
            "Active derivatives market"
        ]
    },
    
    # ============================================
    # Popular Stock Categories
    # ============================================
    "stock_categories": {
        "blue_chips": {
            "description": "大藍籌",
            "examples": ["0005.HK (HSBC)", "0700.HK (Tencent)", "0941.HK (China Mobile)"]
        },
        "h_shares": {
            "description": "H股 (Chinese companies listed in HK)",
            "examples": ["0939.HK (CCB)", "0857.HK (PetroChina)"]
        },
        "red_chips": {
            "description": "紅籌股 (China-related companies incorporated outside mainland)",
            "examples": ["0267.HK (CITIC)", "0992.HK (Lenovo)"]
        },
        "tech_stocks": {
            "description": "科技股",
            "examples": ["0700.HK (Tencent)", "9988.HK (Alibaba)", "9999.HK (NetEase)"]
        },
        "property": {
            "description": "地產股",
            "examples": ["0016.HK (Sun Hung Kai)", "0012.HK (Henderson Land)"]
        },
        "finance": {
            "description": "金融股",
            "examples": ["0005.HK (HSBC)", "0939.HK (CCB)", "1299.HK (AIA)"]
        }
    },
    
    # ============================================
    # Risk Factors Specific to HK Market
    # ============================================
    "risk_factors": {
        "geopolitical": [
            "China-US relations",
            "Hong Kong political situation",
            "Cross-strait relations"
        ],
        "economic": [
            "China economic policy",
            "US interest rate changes",
            "RMB exchange rate"
        ],
        "market": [
            "High volatility",
            "Liquidity risk in small caps",
            "Corporate governance issues",
            "Connected transactions"
        ],
        "specific": [
            "老千股 (fraud stocks)",
            "Penny stock manipulation",
            "Concentration risk (large shareholders)"
        ]
    },
    
    # ============================================
    # News Sources for Hong Kong Market
    # ============================================
    "news_sources": {
        "chinese": [
            {
                "name": "信報 (HKEJ)",
                "url": "https://www.hkej.com",
                "description": "Hong Kong Economic Journal"
            },
            {
                "name": "經濟日報 (HKET)",
                "url": "https://www.hket.com",
                "description": "Hong Kong Economic Times"
            },
            {
                "name": "阿斯達克 (AAStocks)",
                "url": "https://www.aastocks.com",
                "description": "Financial portal"
            },
            {
                "name": "經濟通 (ETNet)",
                "url": "https://www.etnet.com.hk",
                "description": "Financial portal"
            },
            {
                "name": "明報",
                "url": "https://www.mingpao.com",
                "description": "Newspaper"
            }
        ],
        "english": [
            {
                "name": "South China Morning Post",
                "url": "https://www.scmp.com",
                "description": "Leading English newspaper"
            },
            {
                "name": "The Standard",
                "url": "https://www.thestandard.com.hk",
                "description": "Business newspaper"
            }
        ],
        "forums": [
            {
                "name": "連登 (LIHKG)",
                "url": "https://lihkg.com",
                "description": "Most popular discussion forum"
            },
            {
                "name": "高登 (HKGolden)",
                "url": "https://www.hkgolden.com",
                "description": "Discussion forum"
            }
        ],
        "official": [
            {
                "name": "披露易 (HKEXnews)",
                "url": "https://www.hkexnews.hk",
                "description": "Official disclosure platform"
            },
            {
                "name": "證監會 (SFC)",
                "url": "https://www.sfc.hk",
                "description": "Regulator announcements"
            }
        ]
    },
    
    # ============================================
    # Agent Configuration for HK Market
    # ============================================
    "agent_settings": {
        "use_hk_prompts": True,  # Use Hong Kong specific prompts
        "language": "zh-Hant",  # Output in Traditional Chinese
        "consider_stock_connect": True,  # Analyze Stock Connect flows
        "monitor_ah_premium": True,  # Monitor A-H share premium
        "include_forex_analysis": True,  # Include USD/HKD and USD/CNY
        "risk_focus": [
            "Corporate governance",
            "Major shareholder actions",
            "China policy changes",
            "Liquidity"
        ]
    }
}


def get_tick_size(price: float) -> float:
    """
    Get the minimum tick size for a given stock price in Hong Kong market.
    
    Args:
        price: Stock price in HKD
        
    Returns:
        Tick size in HKD
    """
    for rule in HK_MARKET_CONFIG["tick_size_table"]:
        price_range = rule["price_range"]
        if price_range[0] <= price < price_range[1]:
            return rule["tick_size"]
    
    # For prices >= 9995
    return 5.00


def calculate_transaction_cost(transaction_amount: float, brokerage_rate: float = 0.0003) -> dict:
    """
    Calculate total transaction cost for Hong Kong stock trading.
    
    Args:
        transaction_amount: Transaction amount in HKD
        brokerage_rate: Brokerage commission rate (default 0.03%)
        
    Returns:
        Dictionary with breakdown of all costs
    """
    costs = HK_MARKET_CONFIG["transaction_costs"]
    
    stamp_duty = transaction_amount * costs["stamp_duty"]["rate"]
    trading_fee = transaction_amount * costs["trading_fee"]["rate"]
    transaction_levy = transaction_amount * costs["transaction_levy"]["rate"]
    frc_levy = transaction_amount * costs["frc_transaction_levy"]["rate"]
    brokerage = transaction_amount * brokerage_rate
    
    # Clearing fee with min/max
    clearing_fee = transaction_amount * costs["clearing_fee"]["rate"]
    clearing_fee = max(costs["clearing_fee"]["min_charge"], 
                       min(clearing_fee, costs["clearing_fee"]["max_charge"]))
    
    total_cost = stamp_duty + trading_fee + transaction_levy + frc_levy + clearing_fee + brokerage
    
    return {
        "stamp_duty": round(stamp_duty, 2),
        "trading_fee": round(trading_fee, 2),
        "transaction_levy": round(transaction_levy, 2),
        "frc_levy": round(frc_levy, 2),
        "clearing_fee": round(clearing_fee, 2),
        "brokerage": round(brokerage, 2),
        "total": round(total_cost, 2),
        "percentage": round(total_cost / transaction_amount * 100, 4),
        "currency": "HKD"
    }


def normalize_hk_stock_code(code: str) -> str:
    """
    Normalize Hong Kong stock code to standard format.
    
    Args:
        code: Stock code in various formats
        
    Returns:
        Normalized code with .HK suffix
    """
    # Remove .HK suffix if present
    code = code.upper().replace('.HK', '').replace('.HKG', '')
    
    # Pad with zeros to 4 digits
    if code.isdigit():
        code = code.zfill(4)
    
    return f"{code}.HK"


def is_market_open(dt=None) -> dict:
    """
    Check if Hong Kong market is currently open.
    
    Args:
        dt: datetime object (default: current time in HKT)
        
    Returns:
        Dictionary with market status information
    """
    from datetime import datetime
    import pytz
    
    if dt is None:
        hkt = pytz.timezone('Asia/Hong_Kong')
        dt = datetime.now(hkt)
    
    # Check if weekend
    if dt.weekday() >= 5:
        return {
            "is_open": False,
            "reason": "Weekend",
            "next_session": "Monday morning"
        }
    
    # Check trading hours
    current_time = dt.time()
    
    trading_hours = HK_MARKET_CONFIG["trading_hours"]
    
    # Morning session
    morning_start = datetime.strptime(trading_hours["morning_session"]["start"], "%H:%M").time()
    morning_end = datetime.strptime(trading_hours["morning_session"]["end"], "%H:%M").time()
    
    # Afternoon session
    afternoon_start = datetime.strptime(trading_hours["afternoon_session"]["start"], "%H:%M").time()
    afternoon_end = datetime.strptime(trading_hours["afternoon_session"]["end"], "%H:%M").time()
    
    if morning_start <= current_time < morning_end:
        return {
            "is_open": True,
            "session": "Morning session (早市)",
            "ends_at": trading_hours["morning_session"]["end"]
        }
    elif afternoon_start <= current_time < afternoon_end:
        return {
            "is_open": True,
            "session": "Afternoon session (午市)",
            "ends_at": trading_hours["afternoon_session"]["end"]
        }
    else:
        return {
            "is_open": False,
            "reason": "Outside trading hours",
            "next_session": "Next trading session"
        }
