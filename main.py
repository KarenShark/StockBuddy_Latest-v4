from stockbuddy.graph.trading_graph import StockBuddyGraph
from stockbuddy.default_config import DEFAULT_CONFIG
from dotenv import load_dotenv
from datetime import datetime
import argparse
import sys
import os
from pathlib import Path

# Load environment variables from .env file
load_dotenv()


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="StockBuddy - 港股智能交易分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  python main.py --ticker 0700 --date 2026-01-22
  python main.py --ticker 9988
  python main.py  （交互式输入）
        """
    )

    parser.add_argument(
        "--ticker",
        type=str,
        help="股票代码（如：0700, 9988, AAPL）"
    )

    parser.add_argument(
        "--date",
        type=str,
        help="分析日期（格式：YYYY-MM-DD，默认今天）"
    )

    args = parser.parse_args()

    # 获取股票代码
    if args.ticker:
        ticker = args.ticker
        # 对于港股，使用智能识别系统（非交互模式）
        if os.getenv('DEFAULT_MARKET') == 'HKEX':
            from stockbuddy.dataflows.smart_ticker_resolver import normalize_ticker_with_confirmation
            resolved = normalize_ticker_with_confirmation(ticker, interactive=False)
            if resolved:
                ticker = resolved
            else:
                print(f"❌ 错误：无法识别股票代码 {ticker}")
                sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("🎯 StockBuddy - 港股智能交易分析系统")
        print("=" * 60)

        # 交互式输入，带智能识别
        market = os.getenv('DEFAULT_MARKET', 'HK')
        example = "0700, 9988, 5" if market == 'HKEX' else "AAPL, NVDA, TSLA"
        ticker_input = input(f"\n请输入股票代码（如 {example}）: ").strip()

        if not ticker_input:
            print("❌ 错误：股票代码不能为空")
            sys.exit(1)

        # 使用智能识别系统
        if market == 'HKEX':
            from stockbuddy.dataflows.smart_ticker_resolver import normalize_ticker_with_confirmation
            resolved = normalize_ticker_with_confirmation(ticker_input, interactive=True)
            if resolved:
                ticker = resolved
            else:
                print("❌ 已取消")
                sys.exit(1)
        else:
            ticker = ticker_input.upper()

    # 获取分析日期
    if args.date:
        analysis_date = args.date
        # 验证日期格式
        try:
            datetime.strptime(analysis_date, "%Y-%m-%d")
        except ValueError:
            print(f"❌ 错误：日期格式不正确，请使用 YYYY-MM-DD 格式")
            sys.exit(1)
    else:
        default_date = datetime.now().strftime("%Y-%m-%d")
        date_input = input(f"请输入分析日期（格式：YYYY-MM-DD，直接回车使用今天 {default_date}）: ").strip()
        analysis_date = date_input if date_input else default_date

        # 验证日期格式
        try:
            datetime.strptime(analysis_date, "%Y-%m-%d")
        except ValueError:
            print(f"❌ 错误：日期格式不正确，请使用 YYYY-MM-DD 格式")
            sys.exit(1)

    print(f"\n✅ 开始分析：{ticker} | 日期：{analysis_date}")
    print("=" * 60 + "\n")

    # Create a custom config
    config = DEFAULT_CONFIG.copy()
    config["deep_think_llm"] = "gpt-4o-mini"
    config["quick_think_llm"] = "gpt-4o-mini"
    config["max_debate_rounds"] = 1

    # Configure data vendors (优化为港股配置)
    config["data_vendors"] = {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",  # 港股使用yfinance更好
        "news_data": "google",           # 使用Google News（已增强港股搜索）
    }

    # Initialize with custom config
    ta = StockBuddyGraph(debug=True, config=config)

    # 创建结果保存目录
    results_dir = Path(config.get("results_dir", "results")) / ticker / analysis_date
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 结果将保存到：{results_dir}")

    # Forward propagate
    try:
        final_state, decision = ta.propagate(ticker, analysis_date)

        # 保存各个报告段到文件
        report_sections = {
            "market_report": "市场分析报告",
            "sentiment_report": "情绪分析报告",
            "news_report": "新闻分析报告",
            "fundamentals_report": "基本面分析报告",
            "investment_plan": "投资计划",
            "trader_investment_plan": "交易计划",
            "final_trade_decision": "最终交易决策"
        }

        saved_reports = []
        for section_key, section_name in report_sections.items():
            if section_key in final_state and final_state[section_key]:
                file_path = report_dir / f"{section_key}.md"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(final_state[section_key])
                saved_reports.append(section_name)

        print("\n" + "=" * 60)
        print("📊 分析完成！最终决策：")
        print("=" * 60)
        print(decision)
        print("\n" + "=" * 60)
        print(f"✅ 已保存 {len(saved_reports)} 个报告到：{report_dir}")
        if saved_reports:
            for report_name in saved_reports:
                print(f"   • {report_name}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 分析过程中出现错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
