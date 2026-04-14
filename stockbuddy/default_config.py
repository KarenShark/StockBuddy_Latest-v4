import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("STOCKBUDDY_RESULTS_DIR", "./results"),
    "experiments_dir": os.getenv("STOCKBUDDY_EXPERIMENTS_DIR", "./experiments"),
    "data_dir": os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # Hong Kong Market Settings (读取.env中的配置)
    "DEFAULT_MARKET": os.getenv("DEFAULT_MARKET", "HKEX"),  # 默认改为港股
    "DEFAULT_LANGUAGE": os.getenv("DEFAULT_LANGUAGE", "zh_TW"),  # 默认改为繁体中文
    # LLM settings
    "llm_provider": os.getenv("LLM_PROVIDER", "openrouter"),
    "deep_think_llm": os.getenv("DEEP_THINK_LLM", "openai/o1-mini"),
    "quick_think_llm": os.getenv("QUICK_THINK_LLM", "openai/gpt-4o-mini"),
    "backend_url": os.getenv("BACKEND_URL", "https://openrouter.ai/api/v1"),
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: yfinance, alpha_vantage, local
        "technical_indicators": "yfinance",  # Options: yfinance, alpha_vantage, local
        "fundamental_data": "yfinance",      # Options: yfinance, alpha_vantage, openai, local (yfinance best for HK stocks)
        "news_data": "merged",
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        "get_news": "merged",
        # google first: RSS window bounded; openai/live only when end >= today (UTC)
        "get_global_news": "google,openai,local",
    },
    # Chroma memory + embeddings; set False or STOCKBUDDY_DISABLE_MEMORY=1 to skip retrieval
    "memory_enabled": os.getenv("STOCKBUDDY_DISABLE_MEMORY", "").lower() not in ("1", "true", "yes"),
    # decision.json enrichment (post-graph LLM); heuristic fallback never sets confidence
    "decision_enrichment": {
        "enabled": True,
    },
    # Optional overrides: backtest_fee_schedule["hk_equity"]["stamp_duty"] = {"rate": 0.001}
    "backtest_fee_schedule": {},
    # True: route_to_vendor DEBUG 行；main.py trace 模式会打开
    "terminal_vendor_logs": os.getenv("STOCKBUDDY_VENDOR_LOGS", "").lower()
    in ("1", "true", "yes"),
}
