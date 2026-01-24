# Multi-Agent AI Trading Assistant for Hong Kong Retail Traders

> 🎉 **StockBuddy** - Your intelligent trading companion powered by multi-agent LLM framework.

[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue)](https://github.com/KarenShark/StockBuddy_Latest-v4.git)

A multi-agent collaborative framework powered by large language models, featuring 13 specialized agents that work together to analyze stocks and generate trading decisions.

## Core Features

- **13 Specialized Agents**: Market Analyst, News Analyst, Fundamentals Analyst, Social Media Analyst, Bull/Bear Researchers, Research Manager, Trader, Aggressive/Conservative/Neutral Risk Analysts, Risk Manager, Portfolio Manager
- **Multi-Market Support**: Hong Kong Stock Exchange (HKEX) and US markets, with automatic ticker recognition
- **Multiple Data Sources**: yfinance, Alpha Vantage, Google News, Finnhub, Newsdata.io
- **Multiple LLM Support**: OpenAI, Anthropic, Google, OpenRouter, Ollama
- **Intelligent Debate Mechanism**: Agents optimize trading strategies through structured debates
- **Comprehensive Reports**: Generates technical analysis, news analysis, fundamental analysis, sentiment analysis, investment plans, and final trading decisions

## Quick Start

### 1. Requirements

- Python 3.10+
- OpenAI API Key (required)
- Conda (recommended) or venv

### 2. Installation

```bash
# Clone the project
cd "StockBuddy v4"

# Create conda environment
conda create -n stockbuddy python=3.10 -y
conda activate stockbuddy

# Install dependencies
pip install -r requirements.txt

# Install project (optional, for development)
pip install -e .
```

### 3. Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Then edit `.env` with your API keys:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key

# Optional: Data source API keys
ALPHA_VANTAGE_API_KEY=your_key
FINNHUB_API_KEY=your_key
NEWSDATA_API_KEY=your_key

# Optional: Market configuration (default: HKEX)
DEFAULT_MARKET=HKEX  # or US
DEFAULT_LANGUAGE=zh_TW  # traditional Chinese, or en
```

### 4. Run

**Method 1: Using convenience script (recommended)**
```bash
bash start_cli.sh
```

**Method 2: CLI interactive interface**
```bash
conda activate stockbuddy
python -m cli.main
```

**Method 3: Command line script**
```bash
# Interactive mode
python main.py

# Direct arguments
python main.py --ticker 0700 --date 2026-01-24
```

**Method 4: Python API**
```python
from stockbuddy.graph.trading_graph import StockBuddyGraph
from stockbuddy.default_config import DEFAULT_CONFIG

# Initialize
ta = StockBuddyGraph(debug=True, config=DEFAULT_CONFIG.copy())

# Run analysis (HKEX tickers are automatically recognized, e.g., 0700 → 0700.HK)
final_state, decision = ta.propagate("0700", "2026-01-24")
print(decision)
```

## Output Results

Analysis results are saved in `results/[ticker]/[date]/reports/`:

- `market_report.md` - Technical analysis report
- `news_report.md` - News impact analysis
- `fundamentals_report.md` - Fundamental analysis
- `sentiment_report.md` - Social media sentiment analysis
- `investment_plan.md` - Research team investment recommendation
- `trader_investment_plan.md` - Detailed trading plan from trader
- `final_trade_decision.md` - Final trading decision (BUY/SELL/HOLD)

## Configuration

Main configuration is in `stockbuddy/default_config.py`:

```python
{
    "llm_provider": "openai",           # LLM provider
    "deep_think_llm": "gpt-4o-mini",    # Deep thinking model
    "quick_think_llm": "gpt-4o-mini",    # Quick thinking model
    "max_debate_rounds": 1,              # Research team debate rounds
    "max_risk_discuss_rounds": 1,        # Risk management team discussion rounds
    "data_vendors": {
        "core_stock_apis": "yfinance",      # Stock data source
        "technical_indicators": "yfinance", # Technical indicators data source
        "fundamental_data": "yfinance",     # Fundamental data source
        "news_data": "google",               # News data source
    }
}
```

## Project Structure

```
stockbuddy/
├── agents/              # Agent implementations
│   ├── analysts/        # Analyst team
│   ├── researchers/    # Research team
│   ├── trader/         # Trader
│   ├── managers/       # Management team
│   └── risk_mgmt/      # Risk management team
├── graph/              # LangGraph orchestration
├── dataflows/          # Data source integrations
└── default_config.py   # Default configuration

cli/                    # CLI interactive interface
main.py                 # Command line script entry
start_cli.sh           # Convenience startup script
```

## References

[1] arXiv, "arXiv:2412.20138," arXiv.org, preprint. https://arxiv.org/abs/2412.20138

[2] Tauric Research, "TradingAgents," GitHub repository (source code). https://github.com/TauricResearch/TradingAgents

[3] Open-Finance-Lab, "AgenticTrading," GitHub repository (source code). https://github.com/Open-Finance-Lab/AgenticTrading

[4] ValueCell-ai, "valuecell," GitHub repository (source code). https://github.com/ValueCell-ai/valuecell.git

[5] R. Ran Aroussi, "yfinance," GitHub repository (source code). https://github.com/ranaroussi/yfinance

[6] NewsData.io, "NewsData.io Documentation," NewsData.io (official documentation). https://newsdata.io/documentation

[7] Finnhub, "Finnhub API Documentation," Finnhub (official documentation). https://finnhub.io/docs/api

[8] Hong Kong Exchanges and Clearing Limited, "HKEXnews," HKEXnews (official information dissemination website). https://www.hkexnews.hk/

[9] Alpha Vantage Inc., "Alpha Vantage API Documentation," Alpha Vantage (official documentation). https://www.alphavantage.co/documentation/

[10] LangChain, "Introduction | LangChain Documentation," LangChain (official documentation). https://python.langchain.com/docs/introduction/

[11] LangGraph, "LangGraph Documentation," LangChain Docs (official documentation). https://docs.langchain.com/langgraph

[12] Backtrader, "Backtrader: Python Backtesting," Backtrader (official website). https://www.backtrader.com/

[13] Textualize, "Rich Documentation," Read the Docs (official documentation). https://rich.readthedocs.io/en/stable/

[14] Hong Kong Exchanges and Clearing Limited, "HKEX," HKEX (official corporate website). https://www.hkex.com.hk/

[15] Hong Kong Exchanges and Clearing Limited, "Trading Mechanism," HKEX (official information page). https://www.hkex.com.hk/Services/Trading/Securities/Overview/Trading-Mechanism

[16] Hong Kong Exchanges and Clearing Limited, "Volatility Control Mechanism in Hong Kong's Securities Market," HKEX (official PDF). https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Overview/Trading-Mechanism/Trading-Mechanism-for-VCM_E.pdf

## Disclaimer

This system is for research and educational purposes only. Trading performance may vary based on many factors, including the chosen language models, model temperature, trading periods, data quality, and other non-deterministic factors. **It is not intended as financial, investment, or trading advice.**
