from dotenv import load_dotenv
load_dotenv()

from stockbuddy.default_config import DEFAULT_CONFIG
from stockbuddy.experiments import run_pilot, write_report_md_files
from datetime import datetime
import argparse
import sys
import os
from pathlib import Path



def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="StockBuddy - 港股智能交易分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  python main.py --ticker 0700 --date 2026-01-22
  python main.py --ticker 9988
  python main.py --terminal-mode trace --ticker 0700 --date 2024-06-03
  python main.py  （交互式输入）

终端模式（本脚本 main.py）：
  quiet（默认）  invoke 跑图，不打印每步 Ai/Human/Tool 边框；关闭 vendor DEBUG 行
  trace         stream + pretty_print（旧版「==== Ai Message ====」观感）；打开 vendor DEBUG

终端 Rich 看板（Typer，cli/main.py）：
  stockbuddy analyze  或  python -m cli.main analyze
  python -m cli.main  （无子命令：欢迎页后直接进入问卷 + Live 看板）
根目录 python main.py --ticker … 仍为 pilot 写报告；无 --ticker 则走上述 CLI 启动器。
        """
    )

    parser.add_argument(
        "--terminal-mode",
        choices=("quiet", "trace"),
        default="quiet",
        help="quiet=简洁终端；trace=完整图追踪+vendor 调试（旧行为）",
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
    graph_debug = args.terminal_mode == "trace"

    if args.ticker is None:
        from cli.main import run_mode_launcher

        run_mode_launcher()
        return

    ticker = args.ticker
    if os.getenv("DEFAULT_MARKET") == "HKEX":
        from stockbuddy.dataflows.smart_ticker_resolver import (
            normalize_ticker_with_confirmation,
        )

        resolved = normalize_ticker_with_confirmation(ticker, interactive=False)
        if resolved:
            ticker = resolved
        else:
            print(f"❌ 错误：无法识别股票代码 {ticker}")
            sys.exit(1)

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
    print(
        f"🖥️  终端模式：{args.terminal_mode}（Rich 看板：stockbuddy analyze）"
    )
    print("=" * 60 + "\n")

    # Create a custom config
    config = DEFAULT_CONFIG.copy()
    config["terminal_vendor_logs"] = graph_debug
    # Let default_config.py / .env handle these, or override here ONLY if needed
    # config["deep_think_llm"] = "gpt-4o-mini"
    # config["quick_think_llm"] = "gpt-4o-mini"
    # config["max_debate_rounds"] = 1

    # Configure data vendors (优化为港股配置)
    config["data_vendors"] = {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",  # 港股使用yfinance更好
        "news_data": "google",           # 使用Google News（已增强港股搜索）
    }

    # Canonical experiment bundle + legacy results dir
    results_dir = Path(config.get("results_dir", "results")) / ticker / analysis_date
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"

    print(f"📁 旧版报告目录：{results_dir}")

    try:
        pilot = run_pilot(
            ticker,
            analysis_date,
            config,
            debug=graph_debug,
            entry="main",
        )
        final_state = pilot.final_state
        decision = pilot.decision

        report_sections = {
            "market_report": "市场分析报告",
            "sentiment_report": "情绪分析报告",
            "news_report": "新闻分析报告",
            "fundamentals_report": "基本面分析报告",
            "investment_plan": "投资计划",
            "trader_investment_plan": "交易计划",
            "final_trade_decision": "最终交易决策",
        }
        saved_keys = write_report_md_files(report_dir, final_state)
        saved_reports = [report_sections[k] for k in saved_keys if k in report_sections]

        print("\n" + "=" * 60)
        print("📊 分析完成！最终决策：")
        print("=" * 60)
        print(decision)
        print("\n" + "=" * 60)
        print(f"📂 可复现实验目录：{pilot.run_dir}")
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
