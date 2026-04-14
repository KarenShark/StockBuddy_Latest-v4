from typing import Annotated

# Import from vendor-specific modules
from .local import get_YFin_data, get_finnhub_news, get_finnhub_company_insider_sentiment, get_finnhub_company_insider_transactions, get_simfin_balance_sheet, get_simfin_cashflow, get_simfin_income_statements, get_reddit_global_news, get_reddit_company_news
from .y_finance import get_YFin_data_online, get_stock_stats_indicators_window, get_balance_sheet as get_yfinance_balance_sheet, get_cashflow as get_yfinance_cashflow, get_income_statement as get_yfinance_income_statement, get_insider_transactions as get_yfinance_insider_transactions, get_fundamentals as get_yfinance_fundamentals
from .google import get_google_news, get_google_global_news_tool
from .eodhd_news import get_eodhd_news
from .merged_news import get_merged_stock_news
from .openai import get_stock_news_openai, get_global_news_openai, get_fundamentals_openai
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news
)
from .alpha_vantage_common import AlphaVantageRateLimitError

# Configuration and routing logic
from .config import get_config
from .news_window_policy import (
    analysis_end_is_historical,
    meta_line,
    parse_leading_meta,
)


def _vendor_routing_verbose() -> bool:
    return bool(get_config().get("terminal_vendor_logs"))


def _vlog(msg: str) -> None:
    if _vendor_routing_verbose():
        print(msg)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News (public/insiders, original/processed)",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_sentiment",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "local",
    "yfinance",
    "openai",
    "google"
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "local": get_YFin_data,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "local": get_stock_stats_indicators_window
    },
    # fundamental_data
    "get_fundamentals": {
        "yfinance": get_yfinance_fundamentals,
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "openai": get_fundamentals_openai,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "local": get_simfin_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "local": get_simfin_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "local": get_simfin_income_statements,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "openai": get_stock_news_openai,
        "google": get_google_news,
        "merged": get_merged_stock_news,
        "eodhd": get_eodhd_news,
        "local": [get_finnhub_news, get_reddit_company_news, get_google_news],
    },
    "get_global_news": {
        "google": get_google_global_news_tool,
        "openai": get_global_news_openai,
        "local": get_reddit_global_news,
    },
    "get_insider_sentiment": {
        "local": get_finnhub_company_insider_sentiment
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "local": get_finnhub_company_insider_transactions,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

_HISTORICAL_SAFE_GLOBAL_VENDORS = frozenset({"google"})


def _route_get_global_news(*args, **kwargs):
    """
    Protocolized global news: STOCKBUDDY_NEWS_JSON on every path; never raises.
    Historical (UTC end < today): only google_rss_global (bounded RSS window).
    """
    if args:
        curr_date = args[0]
        look_back_days = args[1] if len(args) > 1 else kwargs.get("look_back_days", 7)
        limit = args[2] if len(args) > 2 else kwargs.get("limit", 5)
    else:
        curr_date = kwargs.get("curr_date", "")
        look_back_days = kwargs.get("look_back_days", 7)
        limit = kwargs.get("limit", 5)

    try:
        cd = str(curr_date).strip()
        look_back_days = int(look_back_days)
        limit = int(limit)
    except (TypeError, ValueError) as e:
        return (
            meta_line(
                {
                    "status": "parse_error",
                    "scope": "global",
                    "provider": "router",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nInvalid get_global_news arguments (no fabricated body)."
        )

    historical = analysis_end_is_historical(cd)
    category = get_category_for_method("get_global_news")
    vendor_config = get_vendor(category, "get_global_news")
    config = get_config()
    tool_tv = (config.get("tool_vendors") or {}).get("get_global_news")

    if tool_tv and "," not in str(tool_tv).strip():
        primary_vendors = [str(tool_tv).strip()]
        fallback_vendors = primary_vendors.copy()
    else:
        primary_vendors = [v.strip() for v in str(vendor_config).split(",")]
        all_available = list(VENDOR_METHODS["get_global_news"].keys())
        fallback_vendors = primary_vendors.copy()
        for vendor in all_available:
            if vendor not in fallback_vendors:
                fallback_vendors.append(vendor)

    if historical:
        filtered = [v for v in fallback_vendors if v in _HISTORICAL_SAFE_GLOBAL_VENDORS]
        if not filtered:
            filtered = ["google"] if "google" in VENDOR_METHODS["get_global_news"] else []
    else:
        filtered = fallback_vendors

    primary_str = " → ".join(primary_vendors)
    fallback_str = " → ".join(filtered)
    _vlog(
        f"DEBUG: get_global_news historical={historical} primary=[{primary_str}] "
        f"try=[{fallback_str}]"
    )

    last_out: str | None = None
    for vendor in filtered:
        if vendor not in VENDOR_METHODS["get_global_news"]:
            if vendor in primary_vendors:
                _vlog(
                    f"INFO: Vendor '{vendor}' not supported for get_global_news, skip"
                )
            continue
        impl = VENDOR_METHODS["get_global_news"][vendor]
        try:
            _vlog(f"DEBUG: get_global_news calling {impl.__name__} vendor={vendor!r}...")
            out = impl(curr_date, look_back_days, limit)
        except Exception as e:
            _vlog(f"FAILED: get_global_news {vendor}: {e}")
            last_out = (
                meta_line(
                    {
                        "status": "provider_error",
                        "scope": "global",
                        "provider": vendor,
                        "detail": str(e)[:240],
                    }
                )
                + "\n\nVendor raised (caught; no fabricated body)."
            )
            continue
        meta, _ = parse_leading_meta(out)
        st = (meta or {}).get("status")
        _vlog(f"SUCCESS: get_global_news vendor={vendor} status={st!r}")
        if st == "ok":
            return out
        last_out = out

    if last_out is not None:
        return last_out
    return (
        meta_line(
            {
                "status": "provider_error",
                "scope": "global",
                "provider": "none",
                "detail": "no_vendor_available",
            }
        )
        + "\n\nNo global news provider ran successfully (no fabricated body)."
    )


def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    if method == "get_global_news":
        return _route_get_global_news(*args, **kwargs)

    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    config = get_config()
    tool_tv = (config.get("tool_vendors") or {}).get(method)

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Single explicit tool_vendors entry (no comma): only that vendor, no multi fallback.
    if tool_tv and "," not in tool_tv.strip():
        primary_vendors = [tool_tv.strip()]
        fallback_vendors = primary_vendors.copy()
    else:
        primary_vendors = [v.strip() for v in vendor_config.split(",")]
        all_available_vendors = list(VENDOR_METHODS[method].keys())
        fallback_vendors = primary_vendors.copy()
        for vendor in all_available_vendors:
            if vendor not in fallback_vendors:
                fallback_vendors.append(vendor)

    # Debug: Print fallback ordering
    primary_str = " → ".join(primary_vendors)
    fallback_str = " → ".join(fallback_vendors)
    _vlog(f"DEBUG: {method} - Primary: [{primary_str}] | Full fallback order: [{fallback_str}]")

    # Track results and execution state
    results = []
    vendor_attempt_count = 0
    any_primary_vendor_attempted = False
    successful_vendor = None

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            if vendor in primary_vendors:
                _vlog(
                    f"INFO: Vendor '{vendor}' not supported for method '{method}', falling back to next vendor"
                )
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        is_primary_vendor = vendor in primary_vendors
        vendor_attempt_count += 1

        # Track if we attempted any primary vendor
        if is_primary_vendor:
            any_primary_vendor_attempted = True

        # Debug: Print current attempt
        vendor_type = "PRIMARY" if is_primary_vendor else "FALLBACK"
        _vlog(
            f"DEBUG: Attempting {vendor_type} vendor '{vendor}' for {method} (attempt #{vendor_attempt_count})"
        )

        # Handle list of methods for a vendor
        if isinstance(vendor_impl, list):
            vendor_methods = [(impl, vendor) for impl in vendor_impl]
            _vlog(
                f"DEBUG: Vendor '{vendor}' has multiple implementations: {len(vendor_methods)} functions"
            )
        else:
            vendor_methods = [(vendor_impl, vendor)]

        # Run methods for this vendor
        vendor_results = []
        for impl_func, vendor_name in vendor_methods:
            try:
                _vlog(f"DEBUG: Calling {impl_func.__name__} from vendor '{vendor_name}'...")
                result = impl_func(*args, **kwargs)
                vendor_results.append(result)
                _vlog(
                    f"SUCCESS: {impl_func.__name__} from vendor '{vendor_name}' completed successfully"
                )
                    
            except AlphaVantageRateLimitError as e:
                if vendor == "alpha_vantage":
                    _vlog(
                        "RATE_LIMIT: Alpha Vantage rate limit exceeded, falling back to next available vendor"
                    )
                    _vlog(f"DEBUG: Rate limit details: {e}")
                # Continue to next vendor for fallback
                continue
            except Exception as e:
                # Log error but continue with other implementations
                _vlog(f"FAILED: {impl_func.__name__} from vendor '{vendor_name}' failed: {e}")
                continue

        # Add this vendor's results
        if vendor_results:
            results.extend(vendor_results)
            successful_vendor = vendor
            result_summary = f"Got {len(vendor_results)} result(s)"
            _vlog(f"SUCCESS: Vendor '{vendor}' succeeded - {result_summary}")
            
            # Stopping logic: Stop after first successful vendor for single-vendor configs
            # Multiple vendor configs (comma-separated) may want to collect from multiple sources
            if len(primary_vendors) == 1:
                _vlog(f"DEBUG: Stopping after successful vendor '{vendor}' (single-vendor config)")
                break
        else:
            _vlog(f"FAILED: Vendor '{vendor}' produced no results")

    # Final result summary
    if not results:
        _vlog(f"FAILURE: All {vendor_attempt_count} vendor attempts failed for method '{method}'")
        raise RuntimeError(f"All vendor implementations failed for method '{method}'")
    else:
        _vlog(
            f"FINAL: Method '{method}' completed with {len(results)} result(s) from {vendor_attempt_count} vendor attempt(s)"
        )

    # Return single result if only one, otherwise concatenate as string
    if len(results) == 1:
        return results[0]
    else:
        # Convert all results to strings and concatenate
        return '\n'.join(str(result) for result in results)