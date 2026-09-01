# Nifty Indices Dashboard

A lightweight dashboard for tracking selected NSE indices with live price data, valuation metrics, market breadth, and interactive historical charts.

## What It Tracks

- NIFTY 50
- NIFTY 500
- NIFTY MIDCAP 150
- NIFTY SMALLCAP 250
- NIFTY IT
- NIFTY BANK
- NIFTY FMCG
- NIFTY PHARMA

## Features

- Live NSE index snapshot: price, daily change, high, low, previous close, 52-week high/low, PE, and PB.
- Market breadth: advances, declines, and unchanged constituents.
- Chart periods from one week through maximum available history.
- Yahoo Finance chart history with NSE and ETF-proxy fallbacks where needed.
- Static browser frontend with a Flask API backend.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python app.py
```

Keep the server running, then open `http://localhost:5050` in a browser.

The API runs at `http://localhost:5050`.

## Deploy

Deploy the Flask API to Render (or another Python host):

```text
Build command: pip install -r requirements.txt
Start command: gunicorn --bind 0.0.0.0:$PORT app:app
```

The Flask app serves the dashboard and API from one deployment, so no separate frontend host or API URL configuration is required.

## Data Sources

- [NSE India](https://www.nseindia.com/) for live index data and valuation metrics.
- [Yahoo Finance](https://finance.yahoo.com/) through `yfinance` for historical chart data.

Market data is informational only and should not be treated as investment advice.
