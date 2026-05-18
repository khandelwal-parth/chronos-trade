"""Sandbox logic — Chronos."""

import json
from database import db_create_session, db_get_session, db_update_session


def create_session(session_id, symbol, date, starting_cash=100000):
    db_create_session(session_id, symbol, date, starting_cash)


def get_session(session_id):
    return db_get_session(session_id)


def execute_trade(session_id, action, price, shares, timestamp):
    session = db_get_session(session_id)
    if not session:
        raise Exception("Session not found")

    cash = session["cash"]
    owned = session["shares"]
    avg = session["avg_buy_price"]
    trades = session["trades"]

    if action == "BUY":
        cost = price * shares
        if cost > cash:
            shares = int(cash // price)
            if shares == 0:
                raise Exception("Not enough cash to buy even 1 share")
            cost = price * shares

        total_val = (avg * owned) + (price * shares)
        owned += shares
        avg = total_val / owned
        cash -= cost

        trades.append({
            "action": "BUY",
            "price": price,
            "shares": shares,
            "timestamp": timestamp,
            "pnl": None
        })

    elif action == "SELL":
        if shares > owned:
            shares = owned
        if shares == 0:
            raise Exception("No shares to sell")

        pnl = (price - avg) * shares
        cash += price * shares
        owned -= shares
        if owned == 0:
            avg = 0

        trades.append({
            "action": "SELL",
            "price": price,
            "shares": shares,
            "timestamp": timestamp,
            "pnl": round(pnl, 2)
        })

    cash = round(cash, 2)
    avg = round(avg, 2)

    db_update_session(session_id, cash, owned, avg, trades)

    return {
        "cash": cash,
        "shares": owned,
        "avg_buy_price": avg,
        "portfolio_value": round(cash + (owned * price), 2),
        "trades": trades,
    }


def generate_review(session_id, candles):
    session = db_get_session(session_id)
    trades = session["trades"]
    starting_cash = session["starting_cash"]

    if not candles:
        return _empty_review()

    prices = [c["close"] for c in candles]
    day_low = min(prices)
    day_high = max(prices)
    day_low_time = candles[prices.index(day_low)]["time"][-5:]
    day_high_time = candles[prices.index(day_high)]["time"][-5:]
    last_price = candles[-1]["close"]
    first_price = candles[0]["open"]
    day_change_pct = round(((last_price - first_price) / first_price) * 100, 2)

    sell_trades = [t for t in trades if t["action"] == "SELL"]
    buy_trades = [t for t in trades if t["action"] == "BUY"]

    realized_pnl = round(sum(t["pnl"] for t in sell_trades if t["pnl"]), 2)
    unrealized_pnl = round((last_price - session["avg_buy_price"]) * session["shares"], 2) if session["shares"] > 0 else 0
    total_pnl = round(realized_pnl + unrealized_pnl, 2)
    final_value = round(session["cash"] + session["shares"] * last_price, 2)
    return_pct = round(((final_value - starting_cash) / starting_cash) * 100, 2)

    # Grade
    if total_pnl > 1000: grade = "S"
    elif total_pnl > 500: grade = "A"
    elif total_pnl > 0: grade = "B"
    elif total_pnl > -300: grade = "C"
    elif total_pnl > -700: grade = "D"
    else: grade = "F"

    # Insights
    insights = []

    if not trades:
        insights.append("You didn't make any trades. Watch for momentum — when price breaks above the opening range, that's often a signal.")
    else:
        if buy_trades:
            avg_buy = sum(t["price"] for t in buy_trades) / len(buy_trades)
            if avg_buy > day_low * 1.005:
                insights.append(f"Your average buy was ${avg_buy:.2f} but the day low was ${day_low:.2f} at {day_low_time}. Patience could've saved you ${round(avg_buy - day_low, 2)}/share.")
            else:
                insights.append(f"Excellent buy timing! You bought near the day low of ${day_low:.2f}. That's professional-level entry.")

        if sell_trades:
            avg_sell = sum(t["price"] for t in sell_trades) / len(sell_trades)
            if avg_sell < day_high * 0.995:
                insights.append(f"You sold at ${avg_sell:.2f} but the day high was ${day_high:.2f} at {day_high_time}. You left ${round(day_high - avg_sell, 2)}/share on the table.")
            else:
                insights.append(f"Near-perfect exit! You sold close to the day high of ${day_high:.2f}.")

        if session["shares"] > 0:
            insights.append(f"You're holding {session['shares']} shares at close (${last_price:.2f}). Unrealized P&L: ${unrealized_pnl:+.2f}.")

        if len(buy_trades) > 3:
            insights.append("You made many small buys — averaging in can be smart but watch your transaction costs in real trading.")

        if day_change_pct > 2:
            insights.append(f"Strong bullish day (+{day_change_pct}%). Momentum strategies worked well here — buy early, ride the trend.")
        elif day_change_pct < -2:
            insights.append(f"Bearish day ({day_change_pct}%). Short selling or staying in cash would've been the winning move.")

    if total_pnl > 0:
        summary = f"Profitable session! You made ${total_pnl:,.2f} ({return_pct:+.2f}%)"
    elif total_pnl == 0:
        summary = "Break even — no gains, no losses. Try being more decisive next time."
    else:
        summary = f"Tough session. You lost ${abs(total_pnl):,.2f} ({return_pct:.2f}%). Every loss is a lesson."

    return {
        "summary": summary,
        "grade": grade,
        "total_pnl": total_pnl,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "return_pct": return_pct,
        "final_value": final_value,
        "total_trades": len(trades),
        "insights": insights,
        "best_buy": {"price": day_low, "time": day_low_time},
        "best_sell": {"price": day_high, "time": day_high_time},
        "day_change_pct": day_change_pct,
    }


def _empty_review():
    return {
        "summary": "No data available for review.",
        "grade": "N/A",
        "total_pnl": 0,
        "realized_pnl": 0,
        "unrealized_pnl": 0,
        "return_pct": 0,
        "final_value": 100000,
        "total_trades": 0,
        "insights": ["No trades were made."],
        "best_buy": None,
        "best_sell": None,
        "day_change_pct": 0,
    }
