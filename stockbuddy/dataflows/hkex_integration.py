"""
Hong Kong Stock Exchange (HKEX) data integration module.
Provides market data specific to Hong Kong stocks.
"""

from typing import Annotated
import requests
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import os


def normalize_hk_ticker(symbol: str) -> str:
    """
    Normalize Hong Kong stock ticker format.
    
    Examples:
        '0700' -> '0700.HK'
        '700' -> '0700.HK'
        '0700.HK' -> '0700.HK'
        '9988' -> '9988.HK'
    """
    # Remove .HK suffix if present
    symbol = symbol.upper().replace('.HK', '')
    
    # Pad with zeros to 4 digits for Hong Kong stocks
    if symbol.isdigit() and len(symbol) <= 4:
        symbol = symbol.zfill(4)
    
    return f"{symbol}.HK"


def get_hk_stock_data(
    symbol: Annotated[str, "Hong Kong stock code (e.g., '0700', '9988', or '0700.HK')"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Get historical stock data for Hong Kong stocks using Yahoo Finance.
    Automatically handles HK ticker format conversion.
    
    Args:
        symbol: Hong Kong stock code
        start_date: Start date
        end_date: End date
    
    Returns:
        CSV string with OHLCV data in HKD
    """
    # Normalize ticker format
    hk_ticker = normalize_hk_ticker(symbol)
    
    try:
        ticker = yf.Ticker(hk_ticker)
        data = ticker.history(start=start_date, end=end_date)
        
        if data.empty:
            return f"No data found for Hong Kong stock '{hk_ticker}' between {start_date} and {end_date}"
        
        # Remove timezone info
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        
        # Round values
        numeric_columns = ["Open", "High", "Low", "Close"]
        for col in numeric_columns:
            if col in data.columns:
                data[col] = data[col].round(2)
        
        csv_string = data.to_csv()
        
        # Add Hong Kong specific header
        header = f"# Hong Kong Stock Data for {hk_ticker} from {start_date} to {end_date}\n"
        header += f"# Currency: HKD (Hong Kong Dollar)\n"
        header += f"# Market: Hong Kong Stock Exchange (HKEX)\n"
        header += f"# Trading Hours: 09:30-12:00, 13:00-16:00 HKT (UTC+8)\n"
        header += f"# Total records: {len(data)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving Hong Kong stock data for {hk_ticker}: {str(e)}"


def get_hk_market_calendar(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"]
) -> dict:
    """
    Get Hong Kong market trading calendar information.
    Returns whether the market is open and upcoming holidays.
    
    Uses dynamic holiday detection via holidays library if available,
    otherwise falls back to hardcoded holidays for current year.
    """
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_year = curr_dt.year
    
    # Try to use holidays library for dynamic holiday detection
    try:
        import holidays
        hk_holidays = holidays.HongKong(years=curr_year)
        is_holiday = curr_date in hk_holidays
    except ImportError:
        # Fallback: Use hardcoded holidays if holidays library not available
        # Note: This should be updated annually or use holidays library
        hk_holidays_dict = {
            2026: [
                "2026-01-01", "2026-01-02", "2026-01-28", "2026-01-29",
                "2026-01-30", "2026-01-31", "2026-04-03", "2026-04-04",
                "2026-04-06", "2026-04-05", "2026-05-01", "2026-06-25",
                "2026-07-01", "2026-10-01", "2026-10-02", "2026-10-26",
                "2026-12-25", "2026-12-26",
            ],
            # Add more years as needed, or better: install holidays library
        }
        hk_holidays_list = hk_holidays_dict.get(curr_year, [])
        is_holiday = curr_date in hk_holidays_list
    except Exception as e:
        # If holidays library fails, fallback to hardcoded
        print(f"Warning: Could not load holidays library: {e}")
        is_holiday = False
    
    is_weekend = curr_dt.weekday() >= 5
    market_open = not is_holiday and not is_weekend
    
    return {
        "date": curr_date,
        "is_holiday": is_holiday,
        "is_weekend": is_weekend,
        "market_open": market_open,
        "trading_hours": "09:30-12:00, 13:00-16:00 HKT",
        "timezone": "Asia/Hong_Kong (UTC+8)"
    }


def get_hk_company_info(
    symbol: Annotated[str, "Hong Kong stock code"]
) -> str:
    """
    Get company information for Hong Kong listed companies.
    """
    hk_ticker = normalize_hk_ticker(symbol)
    
    try:
        ticker = yf.Ticker(hk_ticker)
        info = ticker.info
        
        # Extract Hong Kong specific information
        company_info = {
            "Stock Code": hk_ticker,
            "Company Name (EN)": info.get('longName', 'N/A'),
            "Company Name (中文)": info.get('longName', 'N/A'),  # yfinance might not have Chinese name
            "Sector": info.get('sector', 'N/A'),
            "Industry": info.get('industry', 'N/A'),
            "Market Cap (HKD)": info.get('marketCap', 'N/A'),
            "Currency": info.get('currency', 'HKD'),
            "Exchange": info.get('exchange', 'HKG'),
            "Website": info.get('website', 'N/A'),
            "Business Summary": info.get('longBusinessSummary', 'N/A'),
            "Employees": info.get('fullTimeEmployees', 'N/A'),
            "P/E Ratio": info.get('trailingPE', 'N/A'),
            "Dividend Yield": info.get('dividendYield', 'N/A'),
        }
        
        # Format as readable text
        result = f"# Company Information: {hk_ticker}\n\n"
        result += f"## Basic Information\n"
        for key, value in company_info.items():
            result += f"- **{key}**: {value}\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving company information for {hk_ticker}: {str(e)}"


def get_hk_stock_fundamentals(
    symbol: Annotated[str, "Hong Kong stock code"],
    freq: Annotated[str, "Frequency: 'annual' or 'quarterly'"] = "quarterly"
) -> str:
    """
    Get fundamental data for Hong Kong stocks.
    Includes balance sheet, income statement, and cash flow.
    """
    hk_ticker = normalize_hk_ticker(symbol)
    
    try:
        ticker = yf.Ticker(hk_ticker)
        
        result = f"# Fundamental Data for {hk_ticker} ({freq})\n\n"
        result += f"Currency: HKD\n"
        result += f"Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Get financial statements
        if freq.lower() == "quarterly":
            balance_sheet = ticker.quarterly_balance_sheet
            income_stmt = ticker.quarterly_income_stmt
            cashflow = ticker.quarterly_cashflow
        else:
            balance_sheet = ticker.balance_sheet
            income_stmt = ticker.income_stmt
            cashflow = ticker.cashflow
        
        # Format results
        if not balance_sheet.empty:
            result += "## Balance Sheet\n"
            result += balance_sheet.to_string() + "\n\n"
        
        if not income_stmt.empty:
            result += "## Income Statement\n"
            result += income_stmt.to_string() + "\n\n"
        
        if not cashflow.empty:
            result += "## Cash Flow\n"
            result += cashflow.to_string() + "\n\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving fundamental data for {hk_ticker}: {str(e)}"


def get_hk_index_data(
    index_name: Annotated[str, "Index name: 'HSI' (Hang Seng Index) or 'HSCEI' (H-shares Index)"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Get Hong Kong market index data.
    
    Supported indices:
    - HSI: Hang Seng Index (^HSI)
    - HSCEI: Hang Seng China Enterprises Index (^HSCE)
    """
    index_mapping = {
        "HSI": "^HSI",
        "HSCEI": "^HSCE",
        "HSTECH": "^HSTECH",  # Hang Seng TECH Index
    }
    
    ticker_symbol = index_mapping.get(index_name.upper())
    if not ticker_symbol:
        return f"Invalid index name. Supported: {list(index_mapping.keys())}"
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(start=start_date, end=end_date)
        
        if data.empty:
            return f"No data found for {index_name} between {start_date} and {end_date}"
        
        # Remove timezone
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        
        csv_string = data.to_csv()
        
        header = f"# Hong Kong Market Index: {index_name} ({ticker_symbol})\n"
        header += f"# Period: {start_date} to {end_date}\n"
        header += f"# Total records: {len(data)}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving index data for {index_name}: {str(e)}"
