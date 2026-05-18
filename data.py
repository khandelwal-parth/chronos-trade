"""Data fetching + caching — Chronos."""

import yfinance as yf
from datetime import datetime, timedelta
from database import get_cached_candles, save_candles

# Stocks we collect every night automatically
TRACKED_STOCKS = [
    "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL",
    "AMZN", "META", "SPY", "QQQ", "GME",
    "AMD", "NFLX", "IBIT", "COIN", "PLTR"
]


def fetch_from_yfinance(symbol: str, date: str):
    """Fetch hourly candles from yfinance for a specific date."""
    try:
        # yfinance needs a date range
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)

        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1h"
        )

        if df.empty:
            return None

        candles = []
        for ts, row in df.iterrows():
            candles.append({
                "time": ts.strftime("%Y-%m-%d %H:%M"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return candles if candles else None

    except Exception as e:
        print(f"yfinance failed for {symbol} on {date}: {e}")
        return None


def get_candles(symbol: str, date: str):
    """
    Get candles — check cache first, then yfinance.
    Always saves to cache so your database keeps growing.
    """
    symbol = symbol.upper()

    # 1. Check Supabase cache first
    cached = get_cached_candles(symbol, date)
    if cached:
        print(f"⚡ Cache hit: {symbol} on {date} ({len(cached)} candles)")
        return cached

    # 2. Fetch from yfinance
    print(f"🌐 Fetching {symbol} on {date} from yfinance...")
    candles = fetch_from_yfinance(symbol, date)

    if not candles:
        return None

    # 3. Save to Supabase forever
    save_candles(symbol, date, candles)

    return candles


def collect_today():
    """
    Nightly collector — fetches today's candles for all tracked stocks.
    Called by cron-job.org hitting /collect every night.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    results = {}

    for symbol in TRACKED_STOCKS:
        try:
            candles = fetch_from_yfinance(symbol, today)
            if candles:
                save_candles(symbol, today, candles)
                results[symbol] = len(candles)
                print(f"✅ Collected {len(candles)} candles for {symbol}")
            else:
                results[symbol] = 0
                print(f"⚠️ No data for {symbol} today (market closed?)")
        except Exception as e:
            results[symbol] = f"error: {e}"
            print(f"❌ Failed {symbol}: {e}")

    return results


def get_db_stats():
    """How much data do we have stored?"""
    from database import get_db
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT 
            COUNT(DISTINCT symbol) as symbols,
            COUNT(DISTINCT date) as dates,
            COUNT(*) as total_entries
        FROM candles
    """)
    row = dict(c.fetchone())
    c.close()
    conn.close()
    return row
