"""
Nifty Indices Dashboard — Backend
Run:  python app.py
Then: open dashboard.html in your browser
"""

import time
import json
import os
import requests
import yfinance as yf
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allows dashboard.html to call localhost freely

# ── NSE session ──────────────────────────────────────────────────────────────
_session = None
_session_ts = 0
SESSION_TTL = 300  # refresh cookie every 5 min

def get_session():
    global _session, _session_ts
    if _session and (time.time() - _session_ts) < SESSION_TTL:
        return _session

    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.nseindia.com/",
    })
    # warm-up to get cookies
    s.get("https://www.nseindia.com/", timeout=15)
    time.sleep(0.5)
    _session = s
    _session_ts = time.time()
    return s

def nse_get(path):
    s = get_session()
    s.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest",
    })
    r = s.get(f"https://www.nseindia.com{path}", timeout=15)
    r.raise_for_status()
    return r.json()

# ── Target indices ────────────────────────────────────────────────────────────
TARGET_INDICES = {
    "NIFTY 50",
    "NIFTY 500",
    "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 250",
    "NIFTY IT",
    "NIFTY BANK",
    "NIFTY FMCG",
    "NIFTY PHARMA",
}

YF_SYMBOLS = {
    "NIFTY 50": "^NSEI",
    "NIFTY 500": "^CRSLDX",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY PHARMA": "^CNXPHARMA",
}

YF_PROXY_SYMBOLS = {
    "NIFTY MIDCAP 150": "MID150BEES.NS",
    "NIFTY SMALLCAP 250": "MOSMALL250.NS",
}

YF_PERIODS = {
    "1W": "7d",
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "MAX": "max",
}

YF_DAYS = {"1W": 7, "1M": 30, "3M": 90, "6M": 182, "1Y": 365}

def index_snapshot(index_name):
    data = nse_get("/api/allIndices")
    return next((r for r in data.get("data", []) if r.get("index") == index_name), None)

def fallback_history(index_name):
    row = index_snapshot(index_name)
    if not row:
        return []

    values = [
        row.get("previousClose"),
        row.get("open"),
        row.get("low"),
        row.get("high"),
        row.get("last"),
    ]
    values = [float(v) for v in values if v is not None]
    return [
        {"date": f"Point {i + 1}", "close": value}
        for i, value in enumerate(values)
    ]

def yahoo_history(index_name, period):
    from datetime import datetime, timedelta

    symbol = YF_SYMBOLS.get(index_name)
    is_proxy = False
    if not symbol:
        symbol = YF_PROXY_SYMBOLS.get(index_name)
        is_proxy = bool(symbol)
    if not symbol:
        return []

    yf_period = "max" if is_proxy else YF_PERIODS.get(period, "1mo")
    hist = yf.Ticker(symbol).history(period=yf_period, interval="1d")
    if hist.empty or "Close" not in hist:
        return []

    scale = 1
    if is_proxy:
        row = index_snapshot(index_name)
        last_index = row.get("last") if row else None
        last_proxy = hist["Close"].dropna().iloc[-1] if not hist["Close"].dropna().empty else None
        if last_index and last_proxy:
            scale = float(last_index) / float(last_proxy)

    out = []
    cutoff = datetime.today() - timedelta(days=YF_DAYS.get(period, 30)) if is_proxy and period != "MAX" else None
    for date, row in hist.iterrows():
        dt = date.to_pydatetime().replace(tzinfo=None)
        if cutoff and dt < cutoff:
            continue
        close = row.get("Close")
        if close == close:
            out.append({"date": date.strftime("%Y-%m-%d"), "close": float(close) * scale})
    return out

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/indices")
def all_indices():
    """Current snapshot for all 6 indices."""
    try:
        data = nse_get("/api/allIndices")
        rows = [
            r for r in data.get("data", [])
            if r.get("index") in TARGET_INDICES
        ]
        # normalise field names
        out = []
        for r in rows:
            out.append({
                "name":        r.get("index"),
                "last":        r.get("last"),
                "open":        r.get("open"),
                "high":        r.get("high"),
                "low":         r.get("low"),
                "previousClose": r.get("previousClose"),
                "change":      r.get("change"),
                "pChange":     r.get("percentChange"),
                "yearHigh":    r.get("yearHigh"),
                "yearLow":     r.get("yearLow"),
                "pe":          r.get("pe"),
                "pb":          r.get("pb"),
                "dy":          r.get("dy"),
                "advances":    r.get("advances"),
                "declines":    r.get("declines"),
                "unchanged":   r.get("unchanged"),
            })
        return jsonify({"ok": True, "data": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/history/<path:index_name>/<period>")
def history(index_name, period):
    """
    Historical closing data.
    period: 1W | 1M | 3M | 6M | 1Y | MAX
    """
    from datetime import datetime, timedelta

    end   = datetime.today()
    delta = {"1W": 7, "1M": 30, "3M": 90, "6M": 182, "1Y": 365, "MAX": 365 * 25}
    days  = delta.get(period, 30)
    start = end - timedelta(days=days)

    fmt   = lambda d: d.strftime("%d-%m-%Y")
    chart_path = f"/api/chart-databyindex?index={requests.utils.quote(index_name)}&indices=true"
    path  = (
        f"/api/historical/indicesHistory"
        f"?indexType={requests.utils.quote(index_name)}"
        f"&from={fmt(start)}&to={fmt(end)}"
    )
    try:
        out = yahoo_history(index_name, period)
        if len(out) >= 2:
            return jsonify({"ok": True, "data": out, "source": "yahoo"})

        chart_data = nse_get(chart_path)
        graph_rows = chart_data.get("grapthData") or []
        out = [
            {"date": str(r[0]), "close": r[1]}
            for r in graph_rows
            if isinstance(r, list) and len(r) >= 2 and r[1] is not None
        ]
        if out:
            return jsonify({"ok": True, "data": out, "source": "nse-chart"})

        data = nse_get(path)
        payload = data.get("data", [])
        rows = payload.get("indexCloseOnlineRecords", []) if isinstance(payload, dict) else payload
        out  = [
            {"date": r.get("TIMESTAMP") or r.get("EOD_TIMESTAMP") or r.get("indexCloseOnlineRecords", {}).get("EOD_TIMESTAMP"),
             "close": r.get("EOD_CLOSE_INDEX_VAL") or r.get("CLOSE") or r.get("indexCloseOnlineRecords", {}).get("EOD_CLOSE_INDEX_VAL")}
            for r in rows
        ]
        # filter nulls, reverse so oldest→newest
        out = [x for x in out if x["date"] and x["close"]][::-1]
        if not out:
            out = fallback_history(index_name)
        return jsonify({"ok": True, "data": out, "source": "nse-history" if len(out) > 5 else "fallback"})
    except Exception as e:
        out = fallback_history(index_name)
        if out:
            return jsonify({"ok": True, "data": out, "source": "fallback"})
        return jsonify({"ok": False, "error": f"History unavailable from NSE: {e}", "data": []})


@app.route("/api/status")
def status():
    try:
        data = nse_get("/api/marketStatus")
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/")
def root():
    return send_from_directory(app.root_path, "dashboard.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n  ✓ Starting Nifty Dashboard on http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
