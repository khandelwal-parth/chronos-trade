"""Chronos — Time Travel Trading Sandbox."""

import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from data import get_candles, collect_today
from sandbox import create_session, get_session, execute_trade, generate_review
from occasions import OCCASIONS

app = Flask(__name__)
init_db()


@app.route("/")
def index():
    return render_template("index.html", occasions=OCCASIONS)


@app.route("/play")
def play():
    return render_template("play.html")


# ── Data Collection ──────────────────────────────────────────
@app.route("/collect")
def collect():
    """Nightly cron job endpoint — collects today's candles for all tracked stocks."""
    try:
        result = collect_today()
        return jsonify({"success": True, "collected": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Sandbox API ──────────────────────────────────────────────
@app.route("/api/start", methods=["POST"])
def api_start():
    try:
        body = request.get_json()
        symbol = body.get("symbol", "").upper().strip()
        date = body.get("date", "").strip()
        starting_cash = float(body.get("starting_cash", 100000))

        if not symbol or not date:
            return jsonify({"success": False, "error": "Symbol and date required"}), 400

        candles = get_candles(symbol, date)
        if not candles:
            return jsonify({"success": False, "error": f"No data for {symbol} on {date}. Market may have been closed or date out of range."}), 400

        session_id = str(uuid.uuid4())
        create_session(session_id, symbol, date, starting_cash)

        return jsonify({
            "success": True,
            "session_id": session_id,
            "candles": candles,
            "meta": {
                "symbol": symbol,
                "date": date,
                "total_candles": len(candles),
                "starting_cash": starting_cash,
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/trade", methods=["POST"])
def api_trade():
    try:
        body = request.get_json()
        result = execute_trade(
            session_id=body["session_id"],
            action=body["action"].upper(),
            price=float(body["price"]),
            shares=int(body["shares"]),
            timestamp=body.get("timestamp", datetime.now().isoformat())
        )
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/review", methods=["POST"])
def api_review():
    try:
        body = request.get_json()
        review = generate_review(body["session_id"], body["candles"])
        return jsonify({"success": True, "data": review})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/session/<session_id>")
def api_session(session_id):
    try:
        session = get_session(session_id)
        if not session:
            return jsonify({"success": False, "error": "Session not found"}), 404
        return jsonify({"success": True, "data": session})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


if __name__ == "__main__":
    print("\n  ⏱  Chronos — Time Travel Trading")
    print("  " + "─" * 32)
    print("  http://localhost:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
