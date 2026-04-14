# StockBuddy/graph/trading_graph.py

import os
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.prebuilt import ToolNode

from stockbuddy.agents import *
from stockbuddy.default_config import DEFAULT_CONFIG
from stockbuddy.agents.utils.memory import FinancialSituationMemory
from stockbuddy.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from stockbuddy.dataflows.config import set_config

# Import the new abstract tool methods from agent_utils
from stockbuddy.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_sentiment,
    get_insider_transactions,
    get_global_news
)

# Import HK-specific news tools
from stockbuddy.agents.utils.hk_news_tools import (
    get_hk_stock_news_links,
    get_hk_market_news_links
)
from stockbuddy.agents.utils.hk_news_fetcher import (
    get_hk_news_content,
    get_hk_market_news_content
)
from stockbuddy.agents.utils.finnhub_news_tools import (
    get_finnhub_news,
    get_finnhub_sentiment
)

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class StockBuddyGraph:
    """Main class that orchestrates the StockBuddy multi-agent framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
    ):
        """Initialize the StockBuddy graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs
        llm_provider = self.config["llm_provider"].lower()
        if llm_provider in ["openai", "ollama", "openrouter"]:
            api_key = os.getenv("OPENAI_API_KEY")
            extra_headers = {}
            if llm_provider == "openrouter":
                api_key = os.getenv("OPENROUTER_API_KEY")
                extra_headers = {
                    "HTTP-Referer": "https://github.com/KarenShark/StockBuddy_Latest-v4",
                    "X-Title": "StockBuddy"
                }
            
            self.deep_thinking_llm = ChatOpenAI(
                model=self.config["deep_think_llm"], 
                base_url=self.config["backend_url"],
                api_key=api_key,
                default_headers=extra_headers,
                temperature=0,
            )
            self.quick_thinking_llm = ChatOpenAI(
                model=self.config["quick_think_llm"], 
                base_url=self.config["backend_url"],
                api_key=api_key,
                default_headers=extra_headers,
                temperature=0,
            )
        elif self.config["llm_provider"].lower() == "anthropic":
            self.deep_thinking_llm = ChatAnthropic(model=self.config["deep_think_llm"], base_url=self.config["backend_url"])
            self.quick_thinking_llm = ChatAnthropic(model=self.config["quick_think_llm"], base_url=self.config["backend_url"])
        elif self.config["llm_provider"].lower() == "google":
            self.deep_thinking_llm = ChatGoogleGenerativeAI(model=self.config["deep_think_llm"])
            self.quick_thinking_llm = ChatGoogleGenerativeAI(model=self.config["quick_think_llm"])
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config['llm_provider']}")
        
        # Initialize memories
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        self.risk_manager_memory = FinancialSituationMemory("risk_manager_memory", self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config.get("max_debate_rounds", 1),
            max_risk_discuss_rounds=self.config.get("max_risk_discuss_rounds", 1)
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.risk_manager_memory,
            self.conditional_logic,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph (single-agent = market tools only, no debate/risk subgraph)
        self.single_agent = self.config.get("pipeline_profile") == "single_agent"
        if self.single_agent:
            self.graph = self.graph_setup.setup_single_market_graph()
        else:
            self.graph = self.graph_setup.setup_graph(selected_analysts)

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_news,
                ]
            ),
            "news": ToolNode(
                [
                    # HK-specific news content tools (priority for HKEX market)
                    get_hk_news_content,  # 🔥 整合新聞內容（Google News + Finnhub + HKEXnews）
                    get_finnhub_sentiment,  # ⭐ Finnhub 情緒分析
                    get_hk_market_news_content,  # 🔥 市場新聞實際內容
                    get_finnhub_news,  # 💼 Finnhub 專業金融新聞
                    # HK-specific news links (reference)
                    get_hk_stock_news_links,
                    get_hk_market_news_links,
                    # General news and insider information
                    get_news,
                    get_global_news,
                    get_insider_sentiment,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
        }

    def propagate(self, company_name, trade_date, stream_callback=None):
        """Run the StockBuddy graph for a company on a specific date.

        stream_callback(node_name: str, partial_state: dict) is called after
        each graph node completes; used by the research console for live UI.
        """

        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date
        )
        args = self.propagator.get_graph_args()

        if stream_callback:
            # Stream mode: emit node-level progress, accumulate into final_state.
            accumulated: dict = {}
            for event in self.graph.stream(init_agent_state, stream_mode="updates", **args):
                for node_name, updates in event.items():
                    if isinstance(updates, dict):
                        accumulated.update(updates)
                    stream_callback(node_name, dict(accumulated))
            # Ensure we have the authoritative final state via invoke.
            final_state = self.graph.invoke(init_agent_state, **args)
        elif self.debug:
            # Debug mode with tracing
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)

            final_state = trace[-1]
        else:
            # Standard mode without tracing
            final_state = self.graph.invoke(init_agent_state, **args)

        if self.single_agent:
            final_state = dict(final_state)
            final_state["final_trade_decision"] = final_state.get("market_report") or ""

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and processed signal
        return final_state, self.process_signal(final_state["final_trade_decision"])

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        inv = final_state.get("investment_debate_state") or {}
        rsk = final_state.get("risk_debate_state") or {}
        if not isinstance(inv, dict):
            inv = getattr(inv, "__dict__", {}) or {}
        if not isinstance(rsk, dict):
            rsk = getattr(rsk, "__dict__", {}) or {}
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state.get("company_of_interest", ""),
            "trade_date": final_state.get("trade_date", ""),
            "market_report": final_state.get("market_report", ""),
            "sentiment_report": final_state.get("sentiment_report", ""),
            "news_report": final_state.get("news_report", ""),
            "fundamentals_report": final_state.get("fundamentals_report", ""),
            "investment_debate_state": {
                "bull_history": inv.get("bull_history", ""),
                "bear_history": inv.get("bear_history", ""),
                "history": inv.get("history", ""),
                "current_response": inv.get("current_response", ""),
                "judge_decision": inv.get("judge_decision", ""),
            },
            "trader_investment_decision": final_state.get("trader_investment_plan", ""),
            "risk_debate_state": {
                "risky_history": rsk.get("risky_history", ""),
                "safe_history": rsk.get("safe_history", ""),
                "neutral_history": rsk.get("neutral_history", ""),
                "history": rsk.get("history", ""),
                "judge_decision": rsk.get("judge_decision", ""),
            },
            "investment_plan": final_state.get("investment_plan", ""),
            "final_trade_decision": final_state.get("final_trade_decision", ""),
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/StockBuddyStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/StockBuddyStrategy_logs/full_states_log_{trade_date}.json",
            "w",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_risk_manager(
            self.curr_state, returns_losses, self.risk_manager_memory
        )

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
