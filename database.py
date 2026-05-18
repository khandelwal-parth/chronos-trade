"""Database — Chronos."""

import os
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Candle cache — your growing dataset
    c.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id SERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            interval TEXT NOT NULL DEFAULT '1h',
            data JSONB NOT NULL,
            collected_at TEXT NOT NULL,
            UNIQUE(symbol, date, interval)
        )
    """)

    # Trading sessions
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            starting_cash REAL NOT NULL DEFAULT 100000,
            cash REAL NOT NULL DEFAULT 100000,
            shares INTEGER NOT NULL DEFAULT 0,
            avg_buy_price REAL DEFAULT 0,
            trades JSONB DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_complete BOOLEAN DEFAULT FALSE
        )
    """)

    conn.commit()
    c.close()
    conn.close()
    print("✅ Chronos DB initialized.")


# ── Candle Cache ──────────────────────────────────────────────

def get_cached_candles(symbol: str, date: str, interval: str = "1h"):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT data FROM candles
        WHERE symbol = %s AND date = %s AND interval = %s
    """, (symbol.upper(), date, interval))
    row = c.fetchone()
    c.close()
    conn.close()
    if row:
        data = row["data"]
        return data if isinstance(data, list) else json.loads(data)
    return None


def save_candles(symbol: str, date: str, candles: list, interval: str = "1h"):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO candles (symbol, date, interval, data, collected_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (symbol, date, interval) DO UPDATE SET data = EXCLUDED.data
    """, (symbol.upper(), date, interval, json.dumps(candles), datetime.now().isoformat()))
    conn.commit()
    c.close()
    conn.close()
    print(f"💾 Saved {len(candles)} candles for {symbol} on {date}")


# ── Sessions ──────────────────────────────────────────────────

def db_create_session(session_id, symbol, date, starting_cash):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO sessions (id, symbol, date, starting_cash, cash, shares, avg_buy_price, trades, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 0, 0, '[]', %s, %s)
    """, (session_id, symbol.upper(), date, starting_cash, starting_cash, now, now))
    conn.commit()
    c.close()
    conn.close()


def db_get_session(session_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    row = c.fetchone()
    c.close()
    conn.close()
    if not row:
        return None
    s = dict(row)
    if isinstance(s["trades"], str):
        s["trades"] = json.loads(s["trades"])
    return s


def db_update_session(session_id, cash, shares, avg_buy_price, trades):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE sessions
        SET cash = %s, shares = %s, avg_buy_price = %s, trades = %s, updated_at = %s
        WHERE id = %s
    """, (cash, shares, avg_buy_price, json.dumps(trades), datetime.now().isoformat(), session_id))
    conn.commit()
    c.close()
    conn.close()
