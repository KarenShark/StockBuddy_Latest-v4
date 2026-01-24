from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yfinance as yf
import os
from .stockstats_utils import StockstatsUtils

def normalize_ticker_for_market(symbol: str) -> str:
    """
    Normalize ticker symbol based on DEFAULT_MARKET setting.
    For HKEX market, automatically adds .HK suffix and pads to 4 digits.
    """
    default_market = os.getenv('DEFAULT_MARKET', 'HK')
    
    if default_market == 'HKEX':
        # Remove any existing suffix
        clean_symbol = symbol.upper().replace('.HK', '').replace('.HKG', '')
        
        # If it's a pure number, pad to 4 digits and add .HK suffix
        if clean_symbol.isdigit():
            return f"{clean_symbol.zfill(4)}.HK"
        elif not symbol.endswith('.HK'):
            # If not ending with .HK, add it
            return f"{symbol}.HK"
    
    return symbol.upper()

def get_YFin_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Normalize ticker based on market
    normalized_symbol = normalize_ticker_for_market(symbol)

    # Create ticker object
    ticker = yf.Ticker(normalized_symbol)

    # Fetch historical data for the specified date range
    data = ticker.history(start=start_date, end=end_date)

    # Check if data is empty
    if data.empty:
        return (
            f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
        )

    # Remove timezone info from index for cleaner output
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Round numerical values to 2 decimal places for cleaner display
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    # Convert DataFrame to CSV string
    csv_string = data.to_csv()

    # Add header information
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string

def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:

    best_ind_params = {
        # Moving Averages
        "close_50_sma": (
            "50 SMA: A medium-term trend indicator. "
            "Usage: Identify trend direction and serve as dynamic support/resistance. "
            "Tips: It lags price; combine with faster indicators for timely signals."
        ),
        "close_200_sma": (
            "200 SMA: A long-term trend benchmark. "
            "Usage: Confirm overall market trend and identify golden/death cross setups. "
            "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
        ),
        "close_10_ema": (
            "10 EMA: A responsive short-term average. "
            "Usage: Capture quick shifts in momentum and potential entry points. "
            "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
        ),
        # MACD Related
        "macd": (
            "MACD: Computes momentum via differences of EMAs. "
            "Usage: Look for crossovers and divergence as signals of trend changes. "
            "Tips: Confirm with other indicators in low-volatility or sideways markets."
        ),
        "macds": (
            "MACD Signal: An EMA smoothing of the MACD line. "
            "Usage: Use crossovers with the MACD line to trigger trades. "
            "Tips: Should be part of a broader strategy to avoid false positives."
        ),
        "macdh": (
            "MACD Histogram: Shows the gap between the MACD line and its signal. "
            "Usage: Visualize momentum strength and spot divergence early. "
            "Tips: Can be volatile; complement with additional filters in fast-moving markets."
        ),
        # Momentum Indicators
        "rsi": (
            "RSI: Measures momentum to flag overbought/oversold conditions. "
            "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
            "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
        ),
        # Volatility Indicators
        "boll": (
            "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
            "Usage: Acts as a dynamic benchmark for price movement. "
            "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
        ),
        "boll_ub": (
            "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
            "Usage: Signals potential overbought conditions and breakout zones. "
            "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
        ),
        "boll_lb": (
            "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
            "Usage: Indicates potential oversold conditions. "
            "Tips: Use additional analysis to avoid false reversal signals."
        ),
        "atr": (
            "ATR: Averages true range to measure volatility. "
            "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
            "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
        ),
        # Volume-Based Indicators
        "vwma": (
            "VWMA: A moving average weighted by volume. "
            "Usage: Confirm trends by integrating price action with volume data. "
            "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
        ),
        "mfi": (
            "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
            "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
            "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
        ),
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )

    end_date = curr_date
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    # Optimized: Get stock data once and calculate indicators for all dates
    try:
        indicator_data = _get_stock_stats_bulk(symbol, indicator, curr_date)
        
        # Generate the date range we need
        current_dt = curr_date_dt
        date_values = []
        
        while current_dt >= before:
            date_str = current_dt.strftime('%Y-%m-%d')
            
            # Look up the indicator value for this date
            if date_str in indicator_data:
                indicator_value = indicator_data[date_str]
            else:
                indicator_value = "N/A: Not a trading day (weekend or holiday)"
            
            date_values.append((date_str, indicator_value))
            current_dt = current_dt - relativedelta(days=1)
        
        # Build the result string
        ind_string = ""
        for date_str, value in date_values:
            ind_string += f"{date_str}: {value}\n"
        
    except Exception as e:
        print(f"Error getting bulk stockstats data: {e}")
        # Fallback to original implementation if bulk method fails
        ind_string = ""
        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        while curr_date_dt >= before:
            indicator_value = get_stockstats_indicator(
                symbol, indicator, curr_date_dt.strftime("%Y-%m-%d")
            )
            ind_string += f"{curr_date_dt.strftime('%Y-%m-%d')}: {indicator_value}\n"
            curr_date_dt = curr_date_dt - relativedelta(days=1)

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "No description available.")
    )

    return result_str


def _get_stock_stats_bulk(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to calculate"],
    curr_date: Annotated[str, "current date for reference"]
) -> dict:
    """
    Optimized bulk calculation of stock stats indicators.
    Fetches data once and calculates indicator for all available dates.
    Returns dict mapping date strings to indicator values.
    """
    from .config import get_config
    import pandas as pd
    from stockstats import wrap
    import os
    
    # 规范化ticker（港股自动添加.HK后缀）
    normalized_symbol = normalize_ticker_for_market(symbol)
    
    config = get_config()
    online = config["data_vendors"]["technical_indicators"] != "local"
    
    if not online:
        # Local data path
        try:
            data = pd.read_csv(
                os.path.join(
                    config.get("data_cache_dir", "data"),
                    f"{normalized_symbol}-YFin-data-2015-01-01-2025-03-25.csv",
                )
            )
            df = wrap(data)
        except FileNotFoundError:
            raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
    else:
        # Online data fetching with caching
        today_date = pd.Timestamp.today()
        curr_date_dt = pd.to_datetime(curr_date)
        
        end_date = today_date
        start_date = today_date - pd.DateOffset(years=15)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        os.makedirs(config["data_cache_dir"], exist_ok=True)
        
        data_file = os.path.join(
            config["data_cache_dir"],
            f"{normalized_symbol}-YFin-data-{start_date_str}-{end_date_str}.csv",
        )
        
        if os.path.exists(data_file):
            data = pd.read_csv(data_file)
            data["Date"] = pd.to_datetime(data["Date"])
        else:
            data = yf.download(
                normalized_symbol,  # 使用规范化的ticker
                start=start_date_str,
                end=end_date_str,
                multi_level_index=False,
                progress=False,
                auto_adjust=True,
            )
            data = data.reset_index()
            data.to_csv(data_file, index=False)
        
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    
    # Calculate the indicator for all rows at once
    df[indicator]  # This triggers stockstats to calculate the indicator
    
    # Create a dictionary mapping date strings to indicator values
    result_dict = {}
    for _, row in df.iterrows():
        date_str = row["Date"]
        indicator_value = row[indicator]
        
        # Handle NaN/None values
        if pd.isna(indicator_value):
            result_dict[date_str] = "N/A"
        else:
            result_dict[date_str] = str(indicator_value)
    
    return result_dict


def get_stockstats_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
) -> str:

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_date = curr_date_dt.strftime("%Y-%m-%d")

    try:
        indicator_value = StockstatsUtils.get_stock_stats(
            symbol,
            indicator,
            curr_date,
        )
    except Exception as e:
        print(
            f"Error getting stockstats indicator data for indicator {indicator} on {curr_date}: {e}"
        )
        return ""

    return str(indicator_value)


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get balance sheet data from yfinance."""
    try:
        normalized_ticker = normalize_ticker_for_market(ticker)
        ticker_obj = yf.Ticker(normalized_ticker)
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_balance_sheet
        else:
            data = ticker_obj.balance_sheet
            
        if data.empty:
            return f"No balance sheet data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Balance Sheet data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get cash flow data from yfinance."""
    try:
        normalized_ticker = normalize_ticker_for_market(ticker)
        ticker_obj = yf.Ticker(normalized_ticker)
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_cashflow
        else:
            data = ticker_obj.cashflow
            
        if data.empty:
            return f"No cash flow data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Cash Flow data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get income statement data from yfinance."""
    try:
        normalized_ticker = normalize_ticker_for_market(ticker)
        ticker_obj = yf.Ticker(normalized_ticker)
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_income_stmt
        else:
            data = ticker_obj.income_stmt
            
        if data.empty:
            return f"No income statement data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Income Statement data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"]
):
    """Get insider transactions data from yfinance."""
    try:
        normalized_ticker = normalize_ticker_for_market(ticker)
        ticker_obj = yf.Ticker(normalized_ticker)
        data = ticker_obj.insider_transactions
        
        if data is None or data.empty:
            return f"No insider transactions data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Insider Transactions data for {ticker.upper()}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving insider transactions for {ticker}: {str(e)}"


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
) -> str:
    """
    Get comprehensive fundamental data for a company using yfinance.
    This provides company overview and key financial metrics.
    
    Args:
        ticker: Ticker symbol of the company
        curr_date: Current date (not used for yfinance)
        
    Returns:
        Formatted string with comprehensive fundamental data
    """
    try:
        normalized_ticker = normalize_ticker_for_market(ticker)
        ticker_obj = yf.Ticker(normalized_ticker)
        info = ticker_obj.info
        
        if not info or len(info) < 3:
            return f"No fundamental data found for symbol '{ticker}' ({normalized_ticker})"
        
        # Build comprehensive fundamental report
        report = f"# Comprehensive Fundamental Data for {normalized_ticker}\n"
        report += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Company Information
        report += "## Company Information\n"
        report += f"- **Company Name**: {info.get('longName', info.get('shortName', 'N/A'))}\n"
        report += f"- **Sector**: {info.get('sector', 'N/A')}\n"
        report += f"- **Industry**: {info.get('industry', 'N/A')}\n"
        report += f"- **Country**: {info.get('country', 'N/A')}\n"
        report += f"- **Website**: {info.get('website', 'N/A')}\n"
        report += f"- **Business Summary**: {info.get('longBusinessSummary', 'N/A')}\n\n"
        
        # Key Statistics
        report += "## Key Statistics\n"
        report += f"- **Market Cap**: {info.get('marketCap', 'N/A')}\n"
        report += f"- **Enterprise Value**: {info.get('enterpriseValue', 'N/A')}\n"
        report += f"- **Shares Outstanding**: {info.get('sharesOutstanding', 'N/A')}\n"
        report += f"- **Float Shares**: {info.get('floatShares', 'N/A')}\n"
        report += f"- **Employees**: {info.get('fullTimeEmployees', 'N/A')}\n\n"
        
        # Trading Information
        report += "## Trading Information\n"
        report += f"- **Currency**: {info.get('currency', 'N/A')}\n"
        report += f"- **Exchange**: {info.get('exchange', 'N/A')}\n"
        report += f"- **Current Price**: {info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))}\n"
        report += f"- **Previous Close**: {info.get('previousClose', 'N/A')}\n"
        report += f"- **52 Week High**: {info.get('fiftyTwoWeekHigh', 'N/A')}\n"
        report += f"- **52 Week Low**: {info.get('fiftyTwoWeekLow', 'N/A')}\n"
        report += f"- **50 Day Average**: {info.get('fiftyDayAverage', 'N/A')}\n"
        report += f"- **200 Day Average**: {info.get('twoHundredDayAverage', 'N/A')}\n"
        report += f"- **Average Volume**: {info.get('averageVolume', 'N/A')}\n\n"
        
        # Valuation Metrics
        report += "## Valuation Metrics\n"
        report += f"- **P/E Ratio (Trailing)**: {info.get('trailingPE', 'N/A')}\n"
        report += f"- **P/E Ratio (Forward)**: {info.get('forwardPE', 'N/A')}\n"
        report += f"- **PEG Ratio**: {info.get('pegRatio', 'N/A')}\n"
        report += f"- **Price to Book**: {info.get('priceToBook', 'N/A')}\n"
        report += f"- **Price to Sales**: {info.get('priceToSalesTrailing12Months', 'N/A')}\n"
        report += f"- **EV/Revenue**: {info.get('enterpriseToRevenue', 'N/A')}\n"
        report += f"- **EV/EBITDA**: {info.get('enterpriseToEbitda', 'N/A')}\n\n"
        
        # Profitability Metrics
        report += "## Profitability Metrics\n"
        report += f"- **Profit Margin**: {info.get('profitMargins', 'N/A')}\n"
        report += f"- **Operating Margin**: {info.get('operatingMargins', 'N/A')}\n"
        report += f"- **Gross Margin**: {info.get('grossMargins', 'N/A')}\n"
        report += f"- **Return on Assets (ROA)**: {info.get('returnOnAssets', 'N/A')}\n"
        report += f"- **Return on Equity (ROE)**: {info.get('returnOnEquity', 'N/A')}\n"
        report += f"- **EBITDA**: {info.get('ebitda', 'N/A')}\n\n"
        
        # Growth & Revenue
        report += "## Growth & Revenue\n"
        report += f"- **Revenue**: {info.get('totalRevenue', 'N/A')}\n"
        report += f"- **Revenue Per Share**: {info.get('revenuePerShare', 'N/A')}\n"
        report += f"- **Revenue Growth**: {info.get('revenueGrowth', 'N/A')}\n"
        report += f"- **Earnings Growth**: {info.get('earningsGrowth', 'N/A')}\n"
        report += f"- **Quarterly Revenue Growth**: {info.get('quarterlyRevenueGrowth', 'N/A')}\n"
        report += f"- **Quarterly Earnings Growth**: {info.get('quarterlyEarningsGrowth', 'N/A')}\n\n"
        
        # Financial Health
        report += "## Financial Health\n"
        report += f"- **Total Cash**: {info.get('totalCash', 'N/A')}\n"
        report += f"- **Total Debt**: {info.get('totalDebt', 'N/A')}\n"
        report += f"- **Debt to Equity**: {info.get('debtToEquity', 'N/A')}\n"
        report += f"- **Current Ratio**: {info.get('currentRatio', 'N/A')}\n"
        report += f"- **Quick Ratio**: {info.get('quickRatio', 'N/A')}\n"
        report += f"- **Free Cash Flow**: {info.get('freeCashflow', 'N/A')}\n"
        report += f"- **Operating Cash Flow**: {info.get('operatingCashflow', 'N/A')}\n\n"
        
        # Dividend Information
        report += "## Dividend Information\n"
        report += f"- **Dividend Rate**: {info.get('dividendRate', 'N/A')}\n"
        report += f"- **Dividend Yield**: {info.get('dividendYield', 'N/A')}\n"
        report += f"- **Payout Ratio**: {info.get('payoutRatio', 'N/A')}\n"
        report += f"- **Ex-Dividend Date**: {info.get('exDividendDate', 'N/A')}\n"
        report += f"- **5 Year Avg Dividend Yield**: {info.get('fiveYearAvgDividendYield', 'N/A')}\n\n"
        
        # Analyst Recommendations
        report += "## Analyst Recommendations\n"
        report += f"- **Recommendation**: {info.get('recommendationKey', 'N/A')}\n"
        report += f"- **Target High Price**: {info.get('targetHighPrice', 'N/A')}\n"
        report += f"- **Target Low Price**: {info.get('targetLowPrice', 'N/A')}\n"
        report += f"- **Target Mean Price**: {info.get('targetMeanPrice', 'N/A')}\n"
        report += f"- **Target Median Price**: {info.get('targetMedianPrice', 'N/A')}\n"
        report += f"- **Number of Analyst Opinions**: {info.get('numberOfAnalystOpinions', 'N/A')}\n\n"
        
        return report
        
    except Exception as e:
        return f"Error retrieving fundamental data for {ticker}: {str(e)}"