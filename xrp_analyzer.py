#!/usr/bin/env python3
"""
XRP Daily Analyzer v2.0
- Ã­ÂÂ­Ã­ÂÂ Ã«ÂÂ´Ã¬ÂÂ¤ (Ripple ÃªÂ³ÂµÃ¬ÂÂ / Ã¬ÂÂ¼Ã«Â°Â)
- Ã¬ÂÂÃ«Â²Â/ÃªÂ·ÂÃ¬Â Â Ã­ÂÂ¸Ã«ÂÂÃ¬Â»Â¤ (CLARITY Act, GENIUS Act, SEC/CFTC)
- ÃªÂ¸Â°ÃªÂ´Â Ã¬ÂÂÃªÂ¸Â Ã­ÂÂÃ«Â¦Â (ETF, RLUSD, XRPL Ã­ÂÂ¸Ã«ÂÂÃ¬ÂÂ­Ã¬ÂÂ)
- Ã¬ÂÂ¤Ã¬ÂÂÃªÂ°Â ÃªÂ°ÂÃªÂ²Â© ÃªÂ°Â±Ã¬ÂÂ  (30Ã¬Â´Â)
Ã¬ÂÂÃ¬Â¡Â´Ã¬ÂÂ±: pip install requests pandas
"""

import requests
import pandas as pd
import json, os, sys, time
import xml.etree.ElementTree as ET
from datetime import datetime

# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# 1. ÃªÂ³ÂµÃ­ÂÂµ Ã¬ÂÂ Ã­ÂÂ¸
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def fetch_rss(url, max_items=10, label=""):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, timeout=12, headers=headers)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item")[:max_items]:
            title  = item.findtext("title", "").strip()
            link   = item.findtext("link",  "").strip()
            pub    = item.findtext("pubDate", "").strip()
            src_el = item.find("source")
            source = src_el.text.strip() if src_el is not None and src_el.text else ""
            if " - " in title:
                clean  = title.rsplit(" - ", 1)[0].strip()
                source = source or title.rsplit(" - ", 1)[1].strip()
            else:
                clean = title
            items.append({"title": clean, "url": link, "date": pub, "source": source})
        return items
    except Exception as e:
        print(f"  Ã¢ÂÂ  RSS Ã¬ÂÂ¤Ã­ÂÂ¨ ({label}): {e}")
        return []


def fmt_large(v):
    if not v: return "Ã¢ÂÂ"
    if v >= 1e9: return f"${v/1e9:.2f}B"
    if v >= 1e6: return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def fmt_pct(v):
    if v is None: return "Ã¢ÂÂ"
    return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"

def pct_color(v):
    if v is None: return "#94a3b8"
    return "#10b981" if v >= 0 else "#ef4444"


# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# 2. Ã«ÂÂ°Ã¬ÂÂ´Ã­ÂÂ° Ã¬ÂÂÃ¬Â§Â
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def fetch_ohlc(days=90):
    print("[1/7] ÃªÂ°ÂÃªÂ²Â© Ã«ÂÂ°Ã¬ÂÂ´Ã­ÂÂ° Ã¬ÂÂÃ¬Â§Â Ã¬Â¤Â...")
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"}, timeout=15
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  Ã¢ÂÂ  Ã¬ÂÂ¤Ã­ÂÂ¨: {e}"); return None

    prices = pd.DataFrame(data["prices"],        columns=["ts", "price"])
    vols   = pd.DataFrame(data["total_volumes"], columns=["ts", "volume"])
    mcaps  = pd.DataFrame(data["market_caps"],   columns=["ts", "market_cap"])
    df = prices.copy()
    df["volume"]     = vols["volume"]
    df["market_cap"] = mcaps["market_cap"]
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df.set_index("ts", inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    print(f"  Ã¢ÂÂ {len(df)}Ã¬ÂÂ¼Ã¬Â¹Â Ã¬ÂÂÃ«Â£Â")
    return df


def fetch_current_info():
    print("[2/7] Ã¬ÂÂÃ¬ÂÂ¥ Ã¬Â ÂÃ«Â³Â´ Ã¬ÂÂÃ¬Â§Â Ã¬Â¤Â...")
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple",
            params={"localization": "false", "tickers": "false",
                    "community_data": "true", "developer_data": "false"}, timeout=15
        )
        r.raise_for_status()
        data = r.json()
        md = data.get("market_data", {})
        cd = data.get("community_data", {})
        info = {
            "price_usd":           md.get("current_price", {}).get("usd", 0),
            "price_krw":           md.get("current_price", {}).get("krw", 0),
            "price_change_24h":    md.get("price_change_percentage_24h", 0),
            "price_change_7d":     md.get("price_change_percentage_7d", 0),
            "price_change_30d":    md.get("price_change_percentage_30d", 0),
            "market_cap_usd":      md.get("market_cap", {}).get("usd", 0),
            "market_cap_rank":     data.get("market_cap_rank", 0),
            "volume_24h":          md.get("total_volume", {}).get("usd", 0),
            "circulating_supply":  md.get("circulating_supply", 0),
            "total_supply":        md.get("total_supply", 0),
            "ath_usd":             md.get("ath", {}).get("usd", 0),
            "twitter_followers":   cd.get("twitter_followers", 0),
            "reddit_subscribers":  cd.get("reddit_subscribers", 0),
            "sentiment_votes_up":  data.get("sentiment_votes_up_percentage", 0),
            "sentiment_votes_down":data.get("sentiment_votes_down_percentage", 0),
        }
        print(f"  Ã¢ÂÂ Ã­ÂÂÃ¬ÂÂ¬ÃªÂ°Â ${info['price_usd']:,.4f}")
        return info
    except Exception as e:
        print(f"  Ã¢ÂÂ  Ã¬ÂÂ¤Ã­ÂÂ¨: {e}"); return {}


def fetch_all_news():
    print("[3/7] Ã«ÂÂ´Ã¬ÂÂ¤ Ã¬ÂÂÃ¬Â§Â Ã¬Â¤Â...")
    general = fetch_rss(
        "https://news.google.com/rss/search?q=XRP+Ripple+price+news&hl=en&gl=US&ceid=US:en",
        10, "Google News"
    )
    print(f"  Ã¢ÂÂ Ã«ÂÂ´Ã¬ÂÂ¤ {len(general)}ÃªÂ±Â´ Ã¬ÂÂÃ¬Â§Â")
    return general[:10]


def fetch_regulatory():
    print("[4/7] ÃªÂ·ÂÃ¬Â Â/Ã¬ÂÂÃ«Â²Â Ã«ÂÂ´Ã¬ÂÂ¤ Ã¬ÂÂÃ¬Â§Â Ã¬Â¤Â...")
    clarity = fetch_rss(
        "https://news.google.com/rss/search?q=CLARITY+Act+crypto+XRP&hl=en&gl=US&ceid=US:en",
        5, "CLARITY Act"
    )
    genius  = fetch_rss(
        "https://news.google.com/rss/search?q=GENIUS+Act+stablecoin+crypto&hl=en&gl=US&ceid=US:en",
        5, "GENIUS Act"
    )
    sec     = fetch_rss(
        "https://news.google.com/rss/search?q=SEC+CFTC+XRP+regulation+2026&hl=en&gl=US&ceid=US:en",
        5, "SEC/CFTC"
    )
    print(f"  Ã¢ÂÂ CLARITY {len(clarity)}ÃªÂ±Â´ / GENIUS {len(genius)}ÃªÂ±Â´ / SEC {len(sec)}ÃªÂ±Â´")
    return clarity, genius, sec


def fetch_institutional():
    print("[5/7] ÃªÂ¸Â°ÃªÂ´Â Ã¬ÂÂÃªÂ¸Â Ã­ÂÂÃ«Â¦Â Ã¬ÂÂÃ¬Â§Â Ã¬Â¤Â...")

    etf_news = fetch_rss(
        "https://news.google.com/rss/search?q=XRP+ETF+inflow+institutional&hl=en&gl=US&ceid=US:en",
        6, "XRP ETF"
    )

    xrpl = {"tx_today": 0, "tx_7d_avg": 0}
    try:
        r = requests.get(
            "https://data.xrpl.org/v1/network/transaction_stats?interval=day&limit=7",
            timeout=10
        )
        if r.ok:
            rows = r.json().get("rows", [])
            if rows:
                xrpl["tx_today"]  = int(rows[0].get("transaction_count", 0))
                xrpl["tx_7d_avg"] = int(sum(row.get("transaction_count", 0) for row in rows) / len(rows))
    except Exception as e:
        print(f"  Ã¢ÂÂ  XRPL stats Ã¬ÂÂ¤Ã­ÂÂ¨: {e}")

    rlusd_mcap = 0
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ripple-usd&vs_currencies=usd&include_market_cap=true",
            timeout=10
        )
        if r.ok:
            rlusd_mcap = r.json().get("ripple-usd", {}).get("usd_market_cap", 0)
    except Exception as e:
        print(f"  Ã¢ÂÂ  RLUSD Ã¬ÂÂ¤Ã­ÂÂ¨: {e}")

    print(f"  Ã¢ÂÂ ETFÃ«ÂÂ´Ã¬ÂÂ¤ {len(etf_news)}ÃªÂ±Â´ / XRPL tx {xrpl['tx_today']:,} / RLUSD {fmt_large(rlusd_mcap)}")
    return etf_news, xrpl, rlusd_mcap


def fetch_fear_greed():
    print("[6/7] ÃªÂ³ÂµÃ­ÂÂ¬-Ã­ÂÂÃ¬ÂÂ Ã¬Â§ÂÃ¬ÂÂ Ã¬ÂÂÃ¬Â§Â Ã¬Â¤Â...")
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            latest  = data[0]
            history = [{"value": int(d["value"]), "label": d["value_classification"]} for d in data]
            print(f"  Ã¢ÂÂ {latest['value']} ({latest['value_classification']})")
            return int(latest["value"]), latest["value_classification"], history
    except Exception as e:
        print(f"  Ã¢ÂÂ  Ã¬ÂÂ¤Ã­ÂÂ¨: {e}")
    return 50, "Neutral", []


# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# 3. ÃªÂ¸Â°Ã¬ÂÂ  Ã¬Â§ÂÃ­ÂÂ
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def calc_indicators(df):
    print("[7/7] ÃªÂ¸Â°Ã¬ÂÂ  Ã¬Â§ÂÃ­ÂÂ ÃªÂ³ÂÃ¬ÂÂ° Ã¬Â¤Â...")
    df["ma7"]  = df["price"].rolling(7).mean()
    df["ma25"] = df["price"].rolling(25).mean()
    df["ma50"] = df["price"].rolling(50).mean()

    delta     = df["price"].diff()
    gain      = delta.clip(lower=0)
    loss      = -delta.clip(upper=0)
    avg_gain  = gain.ewm(com=13, adjust=False).mean()
    avg_loss  = loss.ewm(com=13, adjust=False).mean()
    df["rsi"] = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, 1e-10)))

    ema12           = df["price"].ewm(span=12, adjust=False).mean()
    ema26           = df["price"].ewm(span=26, adjust=False).mean()
    df["macd"]      = ema12 - ema26
    df["macd_sig"]  = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]

    bb_mid         = df["price"].rolling(20).mean()
    bb_std         = df["price"].rolling(20).std()
    df["bb_upper"] = bb_mid + 2 * bb_std
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["vol_ma7"]  = df["volume"].rolling(7).mean()
    print("  Ã¢ÂÂ RSI / MACD / Ã«Â³Â¼Ã«Â¦Â°Ã¬Â ÂÃ«Â°Â´Ã«ÂÂ / MA Ã¬ÂÂÃ«Â£Â")
    return df


def gen_signals(df):
    latest = df.iloc[-1]; prev = df.iloc[-2]
    signals = []; score = 0.0
    price = latest["price"]

    if   latest["ma7"] > latest["ma25"] and prev["ma7"] <= prev["ma25"]:
        signals.append({"name":"MA Ã­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤","verdict":"Ã«Â§Â¤Ã¬ÂÂ","detail":"7Ã¬ÂÂ¼MA ÃªÂ³Â¨Ã«ÂÂ Ã­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤ Ã«Â°ÂÃ¬ÂÂ"}); score += 2
    elif latest["ma7"] < latest["ma25"] and prev["ma7"] >= prev["ma25"]:
        signals.append({"name":"MA Ã­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤","verdict":"Ã«Â§Â¤Ã«ÂÂ","detail":"7Ã¬ÂÂ¼MA Ã«ÂÂ°Ã«ÂÂÃ­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤ Ã«Â°ÂÃ¬ÂÂ"}); score -= 2
    elif latest["ma7"] > latest["ma25"]:
        signals.append({"name":"MA Ã­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤","verdict":"Ã«Â§Â¤Ã¬ÂÂ","detail":f"MA7(${latest['ma7']:.4f}) > MA25(${latest['ma25']:.4f}) Ã¬ÂÂ Ã¬Â§Â"}); score += 1
    else:
        signals.append({"name":"MA Ã­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤","verdict":"Ã«Â§Â¤Ã«ÂÂ","detail":f"MA7(${latest['ma7']:.4f}) < MA25(${latest['ma25']:.4f}) Ã¬ÂÂ Ã¬Â§Â"}); score -= 1

    rsi = latest["rsi"]
    if   rsi < 30: signals.append({"name":"RSI","verdict":"ÃªÂ°ÂÃ«Â§Â¤Ã¬ÂÂ","detail":f"RSI {rsi:.1f} Ã¢ÂÂ ÃªÂ³Â¼Ã«Â§Â¤Ã«ÂÂ"}); score += 2.5
    elif rsi < 40: signals.append({"name":"RSI","verdict":"Ã«Â§Â¤Ã¬ÂÂ",  "detail":f"RSI {rsi:.1f} Ã¢ÂÂ Ã«Â§Â¤Ã¬ÂÂ Ã¬ÂÂ°Ã¬ÂÂ"}); score += 1.5
    elif rsi > 70: signals.append({"name":"RSI","verdict":"ÃªÂ°ÂÃ«Â§Â¤Ã«ÂÂ","detail":f"RSI {rsi:.1f} Ã¢ÂÂ ÃªÂ³Â¼Ã«Â§Â¤Ã¬ÂÂ"}); score -= 2.5
    elif rsi > 60: signals.append({"name":"RSI","verdict":"Ã«Â§Â¤Ã«ÂÂ",  "detail":f"RSI {rsi:.1f} Ã¢ÂÂ Ã«Â§Â¤Ã«ÂÂ Ã¬ÂÂ°Ã¬ÂÂ"}); score -= 1.5
    else:          signals.append({"name":"RSI","verdict":"Ã¬Â¤ÂÃ«Â¦Â½",  "detail":f"RSI {rsi:.1f} Ã¢ÂÂ Ã¬Â¤ÂÃ«Â¦Â½ ÃªÂµÂ¬ÃªÂ°Â"})

    bb_upper = latest["bb_upper"]; bb_lower = latest["bb_lower"]
    bb_pos   = (price - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
    if   price < bb_lower: signals.append({"name":"Ã«Â³Â¼Ã«Â¦Â°Ã¬Â ÂÃ«Â°Â´Ã«ÂÂ","verdict":"Ã«Â§Â¤Ã¬ÂÂ","detail":"Ã­ÂÂÃ«ÂÂ¨Ã«Â°Â´Ã«ÂÂ Ã­ÂÂÃ­ÂÂ Ã¢ÂÂ Ã«Â°ÂÃ«ÂÂ± ÃªÂ°ÂÃ«ÂÂ¥Ã¬ÂÂ±"}); score += 1.5
    elif price > bb_upper: signals.append({"name":"Ã«Â³Â¼Ã«Â¦Â°Ã¬Â ÂÃ«Â°Â´Ã«ÂÂ","verdict":"Ã«Â§Â¤Ã«ÂÂ","detail":"Ã¬ÂÂÃ«ÂÂ¨Ã«Â°Â´Ã«ÂÂ Ã«ÂÂÃ­ÂÂ Ã¢ÂÂ ÃªÂ³Â¼Ã¬ÂÂ´ ÃªÂµÂ¬ÃªÂ°Â"}); score -= 1.5
    else:                  signals.append({"name":"Ã«Â³Â¼Ã«Â¦Â°Ã¬Â ÂÃ«Â°Â´Ã«ÂÂ","verdict":"Ã¬Â¤ÂÃ«Â¦Â½","detail":f"Ã«Â°Â´Ã«ÂÂ Ã«ÂÂ´ Ã¬ÂÂÃ¬Â¹Â {bb_pos:.0f}%"})

    macd, sig = latest["macd"], latest["macd_sig"]
    if   macd > sig and prev["macd"] <= prev["macd_sig"]: signals.append({"name":"MACD","verdict":"Ã«Â§Â¤Ã¬ÂÂ","detail":"ÃªÂ³Â¨Ã«ÂÂ Ã­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤ Ã«Â°ÂÃ¬ÂÂ"}); score += 2
    elif macd < sig and prev["macd"] >= prev["macd_sig"]: signals.append({"name":"MACD","verdict":"Ã«Â§Â¤Ã«ÂÂ","detail":"Ã«ÂÂ°Ã«ÂÂÃ­ÂÂ¬Ã«Â¡ÂÃ¬ÂÂ¤ Ã«Â°ÂÃ¬ÂÂ"}); score -= 2
    elif macd > sig: signals.append({"name":"MACD","verdict":"Ã«Â§Â¤Ã¬ÂÂ","detail":"MACD > Signal Ã¬ÂÂ Ã¬Â§Â"}); score += 0.5
    else:            signals.append({"name":"MACD","verdict":"Ã«Â§Â¤Ã«ÂÂ","detail":"MACD < Signal Ã¬ÂÂ Ã¬Â§Â"}); score -= 0.5

    vol, vol_ma = latest["volume"], latest["vol_ma7"]
    ratio = vol / vol_ma if vol_ma else 1
    if   ratio > 1.5: signals.append({"name":"ÃªÂ±Â°Ã«ÂÂÃ«ÂÂ","verdict":"Ã¬Â£Â¼Ã«ÂªÂ©","detail":f"7Ã¬ÂÂ¼ Ã­ÂÂÃªÂ·Â  {ratio:.1f}Ã«Â°Â° Ã¢ÂÂ ÃªÂ¸ÂÃ«ÂÂ±"})
    elif ratio > 1.1: signals.append({"name":"ÃªÂ±Â°Ã«ÂÂÃ«ÂÂ","verdict":"Ã¬Â¤ÂÃ«Â¦Â½","detail":f"7Ã¬ÂÂ¼ Ã­ÂÂÃªÂ·Â  {ratio:.1f}Ã«Â°Â° Ã¢ÂÂ Ã¬ÂÂÃ­ÂÂ­ Ã¬Â¦ÂÃªÂ°Â"})
    else:             signals.append({"name":"ÃªÂ±Â°Ã«ÂÂÃ«ÂÂ","verdict":"Ã¬Â¤ÂÃ«Â¦Â½","detail":f"7Ã¬ÂÂ¼ Ã­ÂÂÃªÂ·Â  {ratio:.1f}Ã«Â°Â° Ã¢ÂÂ Ã­ÂÂÃ¬ÂÂ´Ã­ÂÂ Ã¬ÂÂÃ¬Â¤Â"})

    if   score >= 3:    direction, color, eng = "ÃªÂ°ÂÃ­ÂÂ Ã«Â§Â¤Ã¬ÂÂ Ã¬ÂÂ°Ã¬ÂÂ", "#10b981", "STRONG BUY"
    elif score >= 1.5:  direction, color, eng = "Ã«Â§Â¤Ã¬ÂÂ Ã¬ÂÂ°Ã¬ÂÂ",      "#34d399", "BUY"
    elif score <= -3:   direction, color, eng = "ÃªÂ°ÂÃ­ÂÂ Ã«Â§Â¤Ã«ÂÂ Ã¬ÂÂ°Ã¬ÂÂ", "#ef4444", "STRONG SELL"
    elif score <= -1.5: direction, color, eng = "Ã«Â§Â¤Ã«ÂÂ Ã¬ÂÂ°Ã¬ÂÂ",      "#f87171", "SELL"
    else:               direction, color, eng = "Ã¬Â¤ÂÃ«Â¦Â½ / ÃªÂ´ÂÃ«Â§Â",    "#f59e0b", "HOLD"
    return signals, score, direction, color, eng


# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# 4. HTML Ã«Â¹ÂÃ«ÂÂ
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

VERDICT_COLORS = {
    "ÃªÂ°ÂÃ«Â§Â¤Ã¬ÂÂ":"#10b981","Ã«Â§Â¤Ã¬ÂÂ":"#34d399","ÃªÂ°ÂÃ«Â§Â¤Ã«ÂÂ":"#ef4444",
    "Ã«Â§Â¤Ã«ÂÂ":"#f87171","Ã¬Â¤ÂÃ«Â¦Â½":"#94a3b8","ÃªÂ´ÂÃ«Â§Â":"#f59e0b","Ã¬Â£Â¼Ã«ÂªÂ©":"#a78bfa",
}

def badge(v):
    c = VERDICT_COLORS.get(v, "#94a3b8")
    return f'<span class="badge" style="background:{c}20;color:{c};border:1px solid {c}50">{v}</span>'

def news_items_html(items):
    if not items:
        return '<p class="no-data">Ã«ÂÂ´Ã¬ÂÂ¤Ã«Â¥Â¼ Ã«Â¶ÂÃ«ÂÂ¬Ã¬ÂÂ¤Ã«ÂÂ Ã¬Â¤Â...</p>'
    html = ""
    for i, n in enumerate(items[:10]):
        cls = " latest" if i == 0 else ""
        tag = "Ã°ÂÂÂ´ Ã¬ÂµÂÃ¬ÂÂ " if i == 0 else f"#{i+1}"
        html += f'''<a class="ni" href="{n['url']}" target="_blank" rel="noopener">
          <span class="ntag{cls}">{tag}</span>
          <span class="nt">{n['title']}</span>
          <span class="nsrc">{n['source']}</span>
        </a>'''
    return html

def reg_news_html(items):
    if not items:
        return '<p class="no-data">ÃªÂ´ÂÃ«Â Â¨ Ã«ÂÂ´Ã¬ÂÂ¤ Ã¬ÂÂÃ¬ÂÂ</p>'
    html = ""
    for n in items[:4]:
        html += f'''<a class="reg-ni" href="{n['url']}" target="_blank" rel="noopener">
          <span class="rni-dot"></span>
          <span class="rni-title">{n['title']}</span>
          <span class="rni-src">{n['source']}</span>
        </a>'''
    return html


def build_html(df, info, fg_value, fg_label, fg_history,
               signals, score, direction, dir_color, dir_eng,
               general_news,
               clarity_news, genius_news, sec_news,
               etf_news, xrpl_stats, rlusd_mcap):

    now_kst = datetime.now().strftime("%YÃ«ÂÂ %mÃ¬ÂÂ %dÃ¬ÂÂ¼ %H:%M KST")

    chart_df  = df.tail(60).copy()
    labels    = [d.strftime("%m/%d") for d in chart_df.index.to_pydatetime()]
    prices_c  = [round(p, 5) for p in chart_df["price"].tolist()]
    ma7s      = [round(v, 5) if not pd.isna(v) else None for v in chart_df["ma7"].tolist()]
    ma25s     = [round(v, 5) if not pd.isna(v) else None for v in chart_df["ma25"].tolist()]
    bb_up     = [round(v, 5) if not pd.isna(v) else None for v in chart_df["bb_upper"].tolist()]
    bb_lo     = [round(v, 5) if not pd.isna(v) else None for v in chart_df["bb_lower"].tolist()]
    rsi_data  = [round(v, 2) if not pd.isna(v) else None for v in chart_df["rsi"].tolist()]
    macd_data = [round(v, 6) if not pd.isna(v) else None for v in chart_df["macd"].tolist()]
    macd_sig  = [round(v, 6) if not pd.isna(v) else None for v in chart_df["macd_sig"].tolist()]
    macd_hist = [round(v, 6) if not pd.isna(v) else None for v in chart_df["macd_hist"].tolist()]
    vol_data  = [round(v / 1e6, 2) for v in chart_df["volume"].tolist()]
    fg_values = [d["value"] for d in fg_history]
    fg_labels = [f"D-{i}" if i > 0 else "Ã¬ÂÂ¤Ã«ÂÂ" for i in range(len(fg_history)-1, -1, -1)]

    signal_cards = ""
    for s in signals:
        signal_cards += f'''<div class="signal-card">
          <div class="signal-top"><span class="signal-name">{s["name"]}</span>{badge(s["verdict"])}</div>
          <p class="signal-detail">{s["detail"]}</p>
        </div>'''

    price_usd  = info.get("price_usd", 0)
    ath_usd    = info.get("ath_usd", 1)
    ath_pct    = price_usd / ath_usd * 100 if ath_usd else 0
    circ       = info.get("circulating_supply", 0)
    total      = info.get("total_supply", 1)
    supply_pct = circ / total * 100 if total else 0

    gen_html     = news_items_html(general_news)
    clarity_html = reg_news_html(clarity_news)
    genius_html  = reg_news_html(genius_news)
    sec_html     = reg_news_html(sec_news)
    etf_html     = reg_news_html(etf_news)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>XRP Ã«Â¶ÂÃ¬ÂÂ Ã«Â¦Â¬Ã­ÂÂ¬Ã­ÂÂ¸ Ã¢ÂÂ {now_kst}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {{
  --bg:#070c14;--surface:#0d1420;--card:#111827;--border:#1e2d42;
  --text:#e2e8f0;--muted:#64748b;--accent:#00d4ff;--accent2:#7c3aed;
  --green:#10b981;--red:#ef4444;--yellow:#f59e0b;--purple:#a78bfa;
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--mono);overflow-x:hidden}}
body::before{{content:'';position:fixed;inset:0;z-index:0;
  background-image:linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px);
  background-size:40px 40px;opacity:0.25;pointer-events:none}}
.wrap{{position:relative;z-index:1;max-width:1280px;margin:0 auto;padding:32px 24px}}
.hdr{{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--border);padding-bottom:24px;margin-bottom:32px}}
.sym{{font-family:var(--sans);font-size:52px;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1}}
.sub{{color:var(--muted);font-size:11px;margin-top:6px;letter-spacing:2px;text-transform:uppercase}}
.ts{{color:var(--muted);font-size:11px;text-align:right}}
.tag{{display:inline-block;margin-top:6px;background:var(--surface);border:1px solid var(--border);padding:4px 10px;font-size:10px;color:var(--accent);border-radius:2px;letter-spacing:1px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px}}
.g4{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px}}
@media(max-width:900px){{.g2,.g3,.g4{{grid-template-columns:1fr 1fr}}}}
@media(max-width:520px){{.g2,.g3,.g4{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:20px;transition:border-color .2s}}
.card:hover{{border-color:#2e4060}}
.cl{{font-size:10px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:10px}}
.cv{{font-family:var(--sans);font-size:22px;font-weight:700}}
.cs{{font-size:11px;color:var(--muted);margin-top:4px}}
.st{{font-size:10px;letter-spacing:3px;text-transform:uppercase;color:var(--accent);
  border-left:2px solid var(--accent);padding-left:10px;margin-bottom:16px;margin-top:32px;
  display:flex;align-items:center;gap:12px}}
.rt-badge{{font-size:9px;color:var(--muted);background:var(--surface);border:1px solid var(--border);
  padding:2px 8px;border-radius:2px;display:flex;align-items:center;gap:4px}}
.dir{{border:1px solid;border-radius:4px;padding:22px 28px;margin-bottom:28px;display:flex;
  align-items:center;justify-content:space-between;position:relative;overflow:hidden}}
.dir::before{{content:'';position:absolute;inset:0;background:currentColor;opacity:0.05}}
.dl{{font-size:10px;color:var(--muted);letter-spacing:2px;text-transform:uppercase}}
.dm{{font-family:var(--sans);font-size:30px;font-weight:800;margin-top:4px}}
.ds{{font-size:12px;color:var(--muted);margin-top:4px}}
.de{{font-family:var(--sans);font-size:44px;font-weight:800;opacity:.12;letter-spacing:-2px}}
.news-box{{background:var(--card);border:1px solid var(--border);border-radius:4px;margin-bottom:28px;overflow:hidden}}
.news-hdr{{display:flex;align-items:center;border-bottom:1px solid var(--border);background:var(--surface)}}
.tab-btn{{padding:14px 20px;font-size:10px;letter-spacing:2px;text-transform:uppercase;
  color:var(--muted);cursor:pointer;border:none;background:transparent;
  border-bottom:2px solid transparent;transition:all .2s;font-family:var(--mono)}}
.tab-btn.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.tab-btn:hover{{color:var(--text)}}
.news-meta{{font-size:10px;color:var(--muted);margin-left:auto;padding:0 16px;display:flex;align-items:center;gap:6px}}
.tab-pane{{display:none}}.tab-pane.active{{display:block}}
.ni{{display:flex;align-items:flex-start;gap:12px;padding:13px 20px;border-bottom:1px solid var(--border);
  text-decoration:none;transition:background .15s}}
.ni:last-child{{border-bottom:none}}
.ni:hover{{background:var(--surface)}}
.ntag{{flex-shrink:0;font-size:9px;padding:2px 7px;background:#00d4ff15;color:var(--accent);
  border:1px solid #00d4ff30;border-radius:2px;letter-spacing:1px;margin-top:1px;white-space:nowrap}}
.ntag.latest{{background:#ef444415;color:#ef4444;border-color:#ef444430}}
.nt{{font-size:12px;color:var(--text);line-height:1.5;flex:1}}
.nsrc{{flex-shrink:0;font-size:10px;color:var(--muted);margin-left:12px;white-space:nowrap;align-self:center}}
.no-data{{font-size:11px;color:var(--muted);padding:16px 20px}}
.reg-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px}}
@media(max-width:900px){{.reg-grid{{grid-template-columns:1fr}}}}
.reg-card{{background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:hidden}}
.reg-card-hdr{{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;background:var(--surface)}}
.reg-title{{font-size:11px;font-weight:700;color:var(--text);letter-spacing:1px}}
.status-badge{{margin-left:auto;font-size:9px;padding:2px 8px;border-radius:2px;font-weight:700;letter-spacing:1px;white-space:nowrap}}
.reg-body{{padding:14px 18px}}
.reg-desc{{font-size:11px;color:var(--muted);line-height:1.6;margin-bottom:12px}}
.reg-ni{{display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);text-decoration:none}}
.reg-ni:last-child{{border-bottom:none}}
.reg-ni:hover .rni-title{{color:var(--accent)}}
.rni-dot{{width:4px;height:4px;background:var(--accent);border-radius:50%;flex-shrink:0;margin-top:5px}}
.rni-title{{font-size:11px;color:var(--text);line-height:1.4;flex:1;transition:color .15s}}
.rni-src{{font-size:9px;color:var(--muted);margin-left:6px;white-space:nowrap;align-self:center;flex-shrink:0}}
.inst-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px}}
@media(max-width:900px){{.inst-grid{{grid-template-columns:1fr 1fr}}}}
.inst-card{{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:18px}}
.ic-label{{font-size:10px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}}
.ic-value{{font-family:var(--sans);font-size:22px;font-weight:700}}
.ic-sub{{font-size:10px;color:var(--muted);margin-top:4px}}
.etf-box{{background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:hidden}}
.etf-hdr{{padding:12px 18px;border-bottom:1px solid var(--border);background:var(--surface);
  font-size:10px;color:var(--muted);letter-spacing:2px;text-transform:uppercase}}
.cc{{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:20px;margin-bottom:16px}}
.ct{{font-size:11px;color:var(--muted);letter-spacing:1px;margin-bottom:12px;text-transform:uppercase}}
.cw{{position:relative;height:220px}}.cwl{{position:relative;height:280px}}
.sg{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
@media(max-width:800px){{.sg{{grid-template-columns:1fr 1fr}}}}
.signal-card{{background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:14px}}
.signal-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.signal-name{{font-size:12px;font-weight:600}}
.badge{{font-size:10px;padding:2px 8px;border-radius:2px;font-weight:600;letter-spacing:1px}}
.signal-detail{{font-size:11px;color:var(--muted);line-height:1.5}}
.bar{{height:8px;background:var(--border);border-radius:4px;overflow:hidden;margin-top:10px}}
.bar-fill{{height:100%;border-radius:4px}}
.bar6{{height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:8px}}
.bar6-fill{{height:100%;border-radius:3px}}
.fgw{{display:flex;align-items:center;gap:20px;margin-top:12px}}
.fgv{{font-family:var(--sans);font-size:28px;font-weight:800}}
.fgl{{font-size:11px;color:var(--muted);margin-top:2px}}
.fgb{{flex:1}}
.disc{{margin-top:40px;padding:16px 20px;background:var(--surface);border:1px solid var(--border);
  border-left:2px solid var(--yellow);border-radius:4px;font-size:10px;color:var(--muted);line-height:1.7}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.dot{{display:inline-block;width:6px;height:6px;background:var(--green);border-radius:50%;margin-right:6px;animation:pulse 2s infinite}}
</style>
</head>
<body>
<div class="wrap">

  <div class="hdr">
    <div>
      <div class="sym">XRP</div>
      <div class="sub"><span class="dot"></span>Ã¬ÂÂ¼Ã¬ÂÂ¼ Ã¬ÂÂÃ«ÂÂ Ã«Â¶ÂÃ¬ÂÂ Ã«Â¦Â¬Ã­ÂÂ¬Ã­ÂÂ¸ ÃÂ· Ripple / XRP Ledger</div>
    </div>
    <div>
      <div class="ts">{now_kst}</div>
      <div class="tag">AUTO_GENERATED v2.0</div>
    </div>
  </div>

  <!-- Ã¢ÂÂ  Ã­ÂÂÃ¬ÂÂ¬ Ã¬ÂÂÃ¬ÂÂ¥ Ã¬Â§ÂÃ­ÂÂ -->
  <p class="st">Ã­ÂÂÃ¬ÂÂ¬ Ã¬ÂÂÃ¬ÂÂ¥ Ã¬Â§ÂÃ­ÂÂ
    <span class="rt-badge"><span class="dot"></span>Ã¬ÂÂ¤Ã¬ÂÂÃªÂ°Â ÃÂ· <span id="last-updated">ÃªÂ°Â±Ã¬ÂÂ  Ã¬Â¤Â...</span></span>
  </p>
  <div class="g4">
    <div class="card">
      <div class="cl">Ã­ÂÂÃ¬ÂÂ¬ÃªÂ°Â (USD)</div>
      <div class="cv" id="price-usd">${price_usd:,.4f}</div>
      <div class="cs" id="pct-24h" style="color:{pct_color(info.get('price_change_24h'))}">24h {fmt_pct(info.get('price_change_24h'))}</div>
    </div>
    <div class="card">
      <div class="cl">Ã­ÂÂÃ¬ÂÂ¬ÃªÂ°Â (KRW)</div>
      <div class="cv" id="price-krw">Ã¢ÂÂ©{info.get('price_krw',0):,.0f}</div>
      <div class="cs" id="pct-7d" style="color:{pct_color(info.get('price_change_7d'))}">7d {fmt_pct(info.get('price_change_7d'))}</div>
    </div>
    <div class="card">
      <div class="cl">Ã¬ÂÂÃªÂ°ÂÃ¬Â´ÂÃ¬ÂÂ¡</div>
      <div class="cv" id="market-cap">{fmt_large(info.get('market_cap_usd',0))}</div>
      <div class="cs">Ã¬ÂÂÃ¬ÂÂ #{info.get('market_cap_rank','Ã¢ÂÂ')}</div>
    </div>
    <div class="card">
      <div class="cl">24h ÃªÂ±Â°Ã«ÂÂÃ«ÂÂ</div>
      <div class="cv" id="volume-24h">{fmt_large(info.get('volume_24h',0))}</div>
      <div class="cs" id="pct-30d" style="color:{pct_color(info.get('price_change_30d'))}">30d {fmt_pct(info.get('price_change_30d'))}</div>
    </div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="cl">ATH Ã«ÂÂÃ«Â¹Â Ã­ÂÂÃ¬ÂÂ¬ÃªÂ°Â</div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="cv">${ath_usd:,.4f} <span style="font-size:13px;color:var(--muted)">ATH</span></div>
        <div style="color:var(--muted);font-size:12px">{ath_pct:.1f}%</div>
      </div>
      <div class="bar6"><div class="bar6-fill" style="width:{min(ath_pct,100):.1f}%;background:var(--green)"></div></div>
      <div class="cs" style="margin-top:6px">ATH Ã«ÂÂÃ«Â¹Â {ath_pct:.1f}% / Ã­ÂÂÃ«Â³ÂµÃªÂ¹ÂÃ¬Â§Â {100-ath_pct:.1f}% Ã«ÂÂ¨Ã¬ÂÂ</div>
    </div>
    <div class="card">
      <div class="cl">Ã¬ÂÂ Ã­ÂÂµ / Ã¬Â´Â ÃªÂ³ÂµÃªÂ¸ÂÃ«ÂÂ</div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="cv">{circ/1e9:.1f}B XRP</div>
        <div style="color:var(--muted);font-size:12px">{supply_pct:.1f}%</div>
      </div>
      <div class="bar"><div class="bar-fill" style="width:{supply_pct:.1f}%;background:linear-gradient(90deg,var(--accent),var(--accent2))"></div></div>
      <div class="cs" style="margin-top:6px">Ã¬Â´Â {total/1e9:.0f}B XRP Ã¬Â¤Â Ã¬ÂÂ Ã­ÂÂµ {supply_pct:.1f}%</div>
    </div>
  </div>

  <!-- Ã¢ÂÂ¡ Ã«ÂÂ´Ã¬ÂÂ¤ -->
  <div class="news-box">
    <div class="news-hdr">
      <button class="tab-btn active">Ã°ÂÂÂ° XRP / Ripple Ã¬ÂµÂÃ¬ÂÂ  Ã«ÂÂ´Ã¬ÂÂ¤</button>
      <span class="news-meta"><span class="dot"></span><span id="news-updated">Ã¬ÂµÂÃ¬ÂÂ Ã¬ÂÂ ÃÂ· ÃªÂ°Â±Ã¬ÂÂ  Ã¬Â¤Â...</span></span>
    </div>
    <div id="gen-list">{gen_html}</div>
  </div>

  <!-- Ã¢ÂÂ¢ Ã¬ÂÂÃ«Â²Â/ÃªÂ·ÂÃ¬Â Â Ã­ÂÂ¸Ã«ÂÂÃ¬Â»Â¤ -->
  <p class="st">Ã¬ÂÂÃ«Â²Â / ÃªÂ·ÂÃ¬Â Â Ã­ÂÂ¸Ã«ÂÂÃ¬Â»Â¤</p>
  <div class="reg-grid">
    <div class="reg-card">
      <div class="reg-card-hdr">
        <span class="reg-title">CLARITY Act</span>
        <span class="status-badge" style="background:#f59e0b20;color:#f59e0b;border:1px solid #f59e0b40">Ã¬ÂÂÃ¬ÂÂ Ã¬Â§ÂÃ­ÂÂ Ã¬Â¤Â</span>
      </div>
      <div class="reg-body">
        <p class="reg-desc">Ã«ÂÂÃ¬Â§ÂÃ­ÂÂ¸ Ã¬ÂÂÃ¬ÂÂ° Ã¬Â¦ÂÃªÂ¶Â/Ã¬ÂÂÃ­ÂÂ Ã«Â¶ÂÃ«Â¥Â ÃªÂ¸Â°Ã¬Â¤Â Ã«ÂªÂÃ­ÂÂÃ­ÂÂ Ã«Â²ÂÃ¬ÂÂ. Ã­ÂÂÃ¬ÂÂ Ã­ÂÂµÃªÂ³Â¼ Ã­ÂÂ Ã¬ÂÂÃ¬ÂÂ Ã¬ÂÂ¬Ã¬ÂÂ Ã¬Â¤Â. XRP Ã«Â²ÂÃ¬Â Â Ã¬Â§ÂÃ¬ÂÂÃ¬ÂÂ Ã¬Â§ÂÃ¬Â Â Ã¬ÂÂÃ­ÂÂ¥.</p>
        {clarity_html}
      </div>
    </div>
    <div class="reg-card">
      <div class="reg-card-hdr">
        <span class="reg-title">GENIUS Act</span>
        <span class="status-badge" style="background:#10b98120;color:#10b981;border:1px solid #10b98140">Ã¬ÂÂÃ¬ÂÂ Ã­ÂÂµÃªÂ³Â¼</span>
      </div>
      <div class="reg-body">
        <p class="reg-desc">Ã¬ÂÂ¤Ã­ÂÂÃ¬ÂÂ´Ã«Â¸ÂÃ¬Â½ÂÃ¬ÂÂ¸ Ã«Â°ÂÃ­ÂÂ ÃªÂ·ÂÃ¬Â Â Ã­ÂÂÃ«Â ÂÃ¬ÂÂÃ¬ÂÂÃ­ÂÂ¬ Ã«Â²ÂÃ¬ÂÂ. RLUSD ÃªÂ·ÂÃ¬Â Â Ã¬Â ÂÃ­ÂÂ©Ã¬ÂÂ±Ã¬ÂÂ Ã¬Â§ÂÃ¬Â Â Ã¬ÂÂÃ­ÂÂ¥. Ã­ÂÂÃ¬ÂÂ Ã¬ÂÂ¬Ã¬ÂÂ Ã¬Â¤Â.</p>
        {genius_html}
      </div>
    </div>
    <div class="reg-card">
      <div class="reg-card-hdr">
        <span class="reg-title">SEC / CFTC Ã«ÂÂÃ­ÂÂ¥</span>
        <span class="status-badge" style="background:#10b98120;color:#10b981;border:1px solid #10b98140">XRP Ã¬ÂÂÃ­ÂÂ Ã­ÂÂÃ¬ÂÂ¸</span>
      </div>
      <div class="reg-body">
        <p class="reg-desc">SEC 2026Ã«ÂÂ ÃªÂ°ÂÃ¬ÂÂ´Ã«ÂÂÃ¬ÂÂ¤Ã¬ÂÂÃ¬ÂÂ XRPÃ«Â¥Â¼ Ã«ÂÂÃ¬Â§ÂÃ­ÂÂ¸ Ã¬ÂÂÃ­ÂÂÃ¬ÂÂ¼Ã«Â¡Â Ã¬ÂÂ¬Ã­ÂÂÃ¬ÂÂ¸. Ã¬ÂÂÃ¬ÂÂ¡ Ã¬Â¢ÂÃªÂ²Â° Ã­ÂÂ Ã¬Â ÂÃ«ÂÂÃªÂ¶Â Ã­ÂÂ¸Ã¬ÂÂ ÃªÂ°ÂÃ¬ÂÂÃ­ÂÂ ÃªÂµÂ­Ã«Â©Â´.</p>
        {sec_html}
      </div>
    </div>
  </div>

  <!-- Ã¢ÂÂ£ ÃªÂ¸Â°ÃªÂ´Â Ã¬ÂÂÃªÂ¸Â Ã­ÂÂÃ«Â¦Â -->
  <p class="st">ÃªÂ¸Â°ÃªÂ´Â Ã¬ÂÂÃªÂ¸Â Ã­ÂÂÃ«Â¦Â</p>
  <div class="inst-grid">
    <div class="inst-card">
      <div class="ic-label">RLUSD Ã¬ÂÂÃªÂ°ÂÃ¬Â´ÂÃ¬ÂÂ¡</div>
      <div class="ic-value" style="color:var(--accent)">{fmt_large(rlusd_mcap) if rlusd_mcap else "Ã¬ÂÂÃ¬Â§Â Ã¬Â¤Â"}</div>
      <div class="ic-sub">Ripple Ã¬ÂÂ¤Ã­ÂÂÃ¬ÂÂ´Ã«Â¸ÂÃ¬Â½ÂÃ¬ÂÂ¸ ÃÂ· ODL Ã¬ÂÂ°Ã«ÂÂ</div>
    </div>
    <div class="inst-card">
      <div class="ic-label">XRPL Ã¬ÂÂ¼Ã«Â³Â Ã­ÂÂ¸Ã«ÂÂÃ¬ÂÂ­Ã¬ÂÂ</div>
      <div class="ic-value" style="color:var(--green)">{xrpl_stats.get('tx_today',0):,}</div>
      <div class="ic-sub">7Ã¬ÂÂ¼ Ã­ÂÂÃªÂ·Â  {xrpl_stats.get('tx_7d_avg',0):,}ÃªÂ±Â´</div>
    </div>
    <div class="inst-card">
      <div class="ic-label">XRP Ã­ÂÂÃ«Â¬Â¼ ETF</div>
      <div class="ic-value" style="color:var(--purple)">6ÃªÂ°Â Ã¬ÂÂ¹Ã¬ÂÂ¸</div>
      <div class="ic-sub">SEC Ã¬ÂÂ¹Ã¬ÂÂ¸ Ã¬ÂÂÃ«Â£Â ÃÂ· Ã¬ÂÂÃªÂ¸Â Ã¬ÂÂ Ã¬ÂÂ Ã«ÂªÂ¨Ã«ÂÂÃ­ÂÂ°Ã«Â§Â</div>
    </div>
  </div>
  <div class="etf-box">
    <div class="etf-hdr">ÃªÂ¸Â°ÃªÂ´Â / ETF ÃªÂ´ÂÃ«Â Â¨ Ã¬ÂµÂÃ¬ÂÂ  Ã«ÂÂÃ­ÂÂ¥</div>
    {etf_html}
  </div>

  <!-- Ã¬Â°Â¨Ã­ÂÂ¸ -->
  <p class="st">ÃªÂ°ÂÃªÂ²Â© & ÃªÂ¸Â°Ã¬ÂÂ  Ã¬Â§ÂÃ­ÂÂ Ã¬Â°Â¨Ã­ÂÂ¸ (60Ã¬ÂÂ¼)</p>
  <div class="cc"><div class="ct">ÃªÂ°ÂÃªÂ²Â© / MA7 / MA25 / Ã«Â³Â¼Ã«Â¦Â°Ã¬Â ÂÃ«Â°Â´Ã«ÂÂ</div><div class="cwl"><canvas id="priceChart"></canvas></div></div>
  <div class="g2">
    <div class="cc"><div class="ct">RSI-14</div><div class="cw"><canvas id="rsiChart"></canvas></div></div>
    <div class="cc"><div class="ct">MACD (12-26-9)</div><div class="cw"><canvas id="macdChart"></canvas></div></div>
  </div>
  <div class="cc"><div class="ct">ÃªÂ±Â°Ã«ÂÂÃ«ÂÂ (Ã«Â°Â±Ã«Â§Â USD)</div><div class="cw"><canvas id="volChart"></canvas></div></div>

  <!-- Ã¬ÂÂÃªÂ·Â¸Ã«ÂÂ -->
  <p class="st">ÃªÂ¸Â°Ã¬ÂÂ Ã¬Â Â Ã¬Â§ÂÃ­ÂÂ Ã¬ÂÂÃªÂ·Â¸Ã«ÂÂ</p>
  <div class="sg">{signal_cards}</div>

  <!-- Ã¬ÂÂÃ¬ÂÂ¥ Ã¬ÂÂ¬Ã«Â¦Â¬ -->
  <p class="st">Ã¬ÂÂÃ¬ÂÂ¥ Ã¬ÂÂ¬Ã«Â¦Â¬ Ã¬Â§ÂÃ­ÂÂ</p>
  <div class="g2">
    <div class="card">
      <div class="cl">ÃªÂ³ÂµÃ­ÂÂ¬-Ã­ÂÂÃ¬ÂÂ Ã¬Â§ÂÃ¬ÂÂ (7Ã¬ÂÂ¼)</div>
      <div class="fgw">
        <div>
          <div class="fgv" style="color:{'#ef4444' if fg_value<30 else '#10b981' if fg_value>60 else '#f59e0b'}">{fg_value}</div>
          <div class="fgl">{fg_label}</div>
        </div>
        <div class="fgb">
          <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-bottom:4px">
            <span>ÃªÂ³ÂµÃ­ÂÂ¬(0)</span><span>Ã¬Â¤ÂÃ«Â¦Â½(50)</span><span>Ã­ÂÂÃ¬ÂÂ(100)</span>
          </div>
          <div class="bar6"><div class="bar6-fill" style="width:{fg_value}%;background:{'#ef4444' if fg_value<30 else '#10b981' if fg_value>60 else '#f59e0b'}"></div></div>
          <div style="position:relative;height:90px;margin-top:12px"><canvas id="fgChart"></canvas></div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="cl">Ã¬Â»Â¤Ã«Â®Â¤Ã«ÂÂÃ­ÂÂ° Ã¬ÂÂ¼Ã­ÂÂ°Ã«Â©ÂÃ­ÂÂ¸</div>
      <div style="margin-top:12px">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px">
          <span style="color:var(--green)">Ã¢ÂÂ² ÃªÂ¸ÂÃ¬Â Â {info.get('sentiment_votes_up',0):.1f}%</span>
          <span style="color:var(--red)">Ã¢ÂÂ¼ Ã«Â¶ÂÃ¬Â Â {info.get('sentiment_votes_down',0):.1f}%</span>
        </div>
        <div style="height:8px;background:var(--border);border-radius:4px;overflow:hidden">
          <div style="width:{info.get('sentiment_votes_up',50):.1f}%;height:100%;background:linear-gradient(90deg,var(--green),#34d399);border-radius:4px"></div>
        </div>
        <div style="margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div>
            <div style="font-size:10px;color:var(--muted);letter-spacing:1px">TWITTER FOLLOWERS</div>
            <div style="font-size:18px;font-weight:700;margin-top:4px">{info.get('twitter_followers',0):,}</div>
          </div>
          <div>
            <div style="font-size:10px;color:var(--muted);letter-spacing:1px">REDDIT SUBSCRIBERS</div>
            <div style="font-size:18px;font-weight:700;margin-top:4px">{info.get('reddit_subscribers',0):,}</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="disc">
    <strong style="color:var(--yellow)">Ã¢ÂÂ  Ã«Â©Â´Ã¬Â±Â ÃªÂ³Â Ã¬Â§Â</strong><br>
    Ã«Â³Â¸ Ã«Â¦Â¬Ã­ÂÂ¬Ã­ÂÂ¸Ã«ÂÂ ÃªÂ¸Â°Ã¬ÂÂ Ã¬Â Â Ã¬Â§ÂÃ­ÂÂ ÃªÂ¸Â°Ã«Â°Â Ã¬ÂÂÃ«ÂÂ Ã«Â¶ÂÃ¬ÂÂ Ã¬ÂÂÃ«Â£ÂÃ«Â¡Â, Ã­ÂÂ¬Ã¬ÂÂ ÃªÂ¶ÂÃ¬ÂÂ ÃªÂ°Â Ã¬ÂÂÃ«ÂÂÃ«ÂÂÃ«ÂÂ¤. Ã¬ÂÂÃ«Â²Â/ÃªÂ·ÂÃ¬Â Â Ã¬Â ÂÃ«Â³Â´Ã«ÂÂ ÃªÂ³ÂµÃªÂ°Â Ã«ÂÂ´Ã¬ÂÂ¤ ÃªÂ¸Â°Ã«Â°ÂÃ¬ÂÂ´Ã«Â©Â° Ã«Â²ÂÃ¬Â Â Ã­ÂÂ¨Ã«Â Â¥Ã¬ÂÂ´ Ã¬ÂÂÃ¬ÂÂµÃ«ÂÂÃ«ÂÂ¤. Ã¬ÂÂÃ­ÂÂ¸Ã­ÂÂÃ­ÂÂ Ã­ÂÂ¬Ã¬ÂÂÃ«ÂÂ Ã¬ÂÂÃªÂ¸Â Ã¬ÂÂÃ¬ÂÂ¤ Ã¬ÂÂÃ­ÂÂÃ¬ÂÂ´ Ã¬ÂÂÃ¬ÂÂ¼Ã«Â©Â°, Ã«ÂªÂ¨Ã«ÂÂ  Ã­ÂÂ¬Ã¬ÂÂ ÃªÂ²Â°Ã¬Â ÂÃ¬ÂÂ Ã«Â³Â¸Ã¬ÂÂ¸Ã¬ÂÂ Ã­ÂÂÃ«ÂÂ¨ÃªÂ³Â¼ Ã¬Â±ÂÃ¬ÂÂ Ã­ÂÂÃ¬ÂÂ Ã¬ÂÂ´Ã«Â£Â¨Ã¬ÂÂ´Ã¬Â Â¸Ã¬ÂÂ¼ Ã­ÂÂ©Ã«ÂÂÃ«ÂÂ¤.
  </div>
</div>

<script>
function switchTab(id,btn){{
  document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
}}

Chart.defaults.color='#64748b';Chart.defaults.borderColor='#1e2d42';
Chart.defaults.font.family="'JetBrains Mono',monospace";Chart.defaults.font.size=10;

const L={json.dumps(labels)},P={json.dumps(prices_c)},M7={json.dumps(ma7s)},M25={json.dumps(ma25s)};
const BU={json.dumps(bb_up)},BL={json.dumps(bb_lo)},RI={json.dumps(rsi_data)};
const MD={json.dumps(macd_data)},MS={json.dumps(macd_sig)},MH={json.dumps(macd_hist)};
const VD={json.dumps(vol_data)},FV={json.dumps(fg_values[::-1])},FL={json.dumps(fg_labels)};

const base={{responsive:true,maintainAspectRatio:false,
  plugins:{{legend:{{display:true,position:'top',labels:{{boxWidth:10,padding:12}}}},tooltip:{{mode:'index',intersect:false}}}},
  scales:{{x:{{grid:{{color:'#1e2d4240'}},ticks:{{maxTicksLimit:8}}}},y:{{grid:{{color:'#1e2d4240'}},position:'right'}}}},
  elements:{{point:{{radius:0}},line:{{tension:0.3}}}}}};

new Chart(document.getElementById('priceChart'),{{type:'line',data:{{labels:L,datasets:[
  {{label:'Price',data:P,borderColor:'#00d4ff',borderWidth:2,backgroundColor:'transparent'}},
  {{label:'MA7',data:M7,borderColor:'#f59e0b',borderWidth:1.5,borderDash:[4,2],backgroundColor:'transparent'}},
  {{label:'MA25',data:M25,borderColor:'#a78bfa',borderWidth:1.5,borderDash:[6,3],backgroundColor:'transparent'}},
  {{label:'BBÃ¢ÂÂ',data:BU,borderColor:'#ef444430',borderWidth:1,backgroundColor:'#ef44440a',fill:false}},
  {{label:'BBÃ¢ÂÂ',data:BL,borderColor:'#10b98130',borderWidth:1,backgroundColor:'#10b9810a',fill:'-1'}},
]}},options:base}});

new Chart(document.getElementById('rsiChart'),{{type:'line',data:{{labels:L,datasets:[
  {{label:'RSI',data:RI,borderColor:'#a78bfa',borderWidth:1.5,backgroundColor:'transparent'}}
]}},options:{{...base,scales:{{x:base.scales.x,y:{{...base.scales.y,min:0,max:100,ticks:{{stepSize:20}}}}}}}}}});

new Chart(document.getElementById('macdChart'),{{type:'bar',data:{{labels:L,datasets:[
  {{label:'Hist',data:MH,backgroundColor:MH.map(v=>v>=0?'#10b98160':'#ef444460'),type:'bar'}},
  {{label:'MACD',data:MD,borderColor:'#00d4ff',borderWidth:1.5,backgroundColor:'transparent',type:'line'}},
  {{label:'Sig',data:MS,borderColor:'#f59e0b',borderWidth:1.5,borderDash:[4,2],backgroundColor:'transparent',type:'line'}},
]}},options:base}});

new Chart(document.getElementById('volChart'),{{type:'bar',data:{{labels:L,datasets:[
  {{label:'Vol(M$)',data:VD,backgroundColor:'#00d4ff25',borderColor:'#00d4ff50',borderWidth:1}}
]}},options:{{...base,plugins:{{...base.plugins,legend:{{display:false}}}}}}}});

new Chart(document.getElementById('fgChart'),{{type:'line',data:{{labels:FL,datasets:[
  {{label:'F&G',data:FV,borderColor:'#f59e0b',backgroundColor:'#f59e0b15',borderWidth:2,fill:true}}
]}},options:{{responsive:true,maintainAspectRatio:false,
  plugins:{{legend:{{display:false}},tooltip:{{mode:'index',intersect:false}}}},
  scales:{{x:{{grid:{{color:'#1e2d4240'}}}},y:{{grid:{{color:'#1e2d4240'}},min:0,max:100,position:'right'}}}},
  elements:{{point:{{radius:3}},line:{{tension:0.4}}}}}}}});

// Ã¬ÂÂ¤Ã¬ÂÂÃªÂ°Â ÃªÂ°ÂÃªÂ²Â© ÃªÂ°Â±Ã¬ÂÂ  (30Ã¬Â´Â)
function fL(v){{return v>=1e9?'$'+(v/1e9).toFixed(2)+'B':v>=1e6?'$'+(v/1e6).toFixed(2)+'M':'$'+v.toFixed(2)}}
function fP(v){{return(v>=0?'+':'')+v.toFixed(2)+'%'}}
function pC(v){{return v>=0?'#10b981':'#ef4444'}}

async function updatePrice(){{
  try{{
    const r=await fetch('https://api.coingecko.com/api/v3/coins/ripple?localization=false&tickers=false&community_data=false&developer_data=false');
    if(!r.ok)throw new Error();
    const md=(await r.json()).market_data;
    document.getElementById('price-usd').textContent='$'+md.current_price.usd.toFixed(4);
    document.getElementById('price-krw').textContent='Ã¢ÂÂ©'+md.current_price.krw.toLocaleString();
    document.getElementById('market-cap').textContent=fL(md.market_cap.usd);
    document.getElementById('volume-24h').textContent=fL(md.total_volume.usd);
    const p24=document.getElementById('pct-24h');p24.textContent='24h '+fP(md.price_change_percentage_24h);p24.style.color=pC(md.price_change_percentage_24h);
    const p7=document.getElementById('pct-7d');p7.textContent='7d '+fP(md.price_change_percentage_7d);p7.style.color=pC(md.price_change_percentage_7d);
    const p30=document.getElementById('pct-30d');p30.textContent='30d '+fP(md.price_change_percentage_30d);p30.style.color=pC(md.price_change_percentage_30d);
    const n=new Date();
    document.getElementById('last-updated').textContent=n.getHours().toString().padStart(2,'0')+':'+n.getMinutes().toString().padStart(2,'0')+':'+n.getSeconds().toString().padStart(2,'0')+' ÃªÂ°Â±Ã¬ÂÂ ';
  }}catch(e){{document.getElementById('last-updated').textContent='ÃªÂ°Â±Ã¬ÂÂ  Ã¬ÂÂ¤Ã­ÂÂ¨';}}
}}
updatePrice();setInterval(updatePrice,30000);

// Ã¬ÂÂ¤Ã¬ÂÂÃªÂ°Â Ã«ÂÂ´Ã¬ÂÂ¤ ÃªÂ°Â±Ã¬ÂÂ  (30Ã«Â¶Â)
const PROXY=url=>`https://api.allorigins.win/get?url=${{encodeURIComponent(url)}}`;
const RSS_OFF='https://news.google.com/rss/search?q=Ripple+XRP+official&hl=en&gl=US&ceid=US:en';
const RSS_GEN='https://news.google.com/rss/search?q=XRP+Ripple+price+news&hl=en&gl=US&ceid=US:en';
const OFFICIAL_DOMAINS=['ripple.com','xrpl.org','ripplex'];

function timeAgo(d){{
  const s=(Date.now()-new Date(d).getTime())/1000;
  if(s<60)return 'Ã«Â°Â©ÃªÂ¸Â';if(s<3600)return Math.floor(s/60)+'Ã«Â¶Â Ã¬Â Â';
  if(s<86400)return Math.floor(s/3600)+'Ã¬ÂÂÃªÂ°Â Ã¬Â Â';return Math.floor(s/86400)+'Ã¬ÂÂ¼ Ã¬Â Â';
}}

function parseRSS(xml){{
  const doc=new DOMParser().parseFromString(xml,'text/xml');
  return [...doc.querySelectorAll('item')].map(el=>{{
    const t=el.querySelector('title')?.textContent?.replace(/<[^>]+>/g,'').replace(/ - [^-]+$/,'').trim()||'';
    const l=el.querySelector('link')?.textContent?.trim()||'#';
    const d=el.querySelector('pubDate')?.textContent?.trim()||'';
    const s=el.querySelector('source')?.textContent?.trim()||'';
    return {{title:t,url:l,date:d,source:s}};
  }});
}}

function renderNews(items,listId){{
  const el=document.getElementById(listId);if(!el)return;
  items.sort((a,b)=>new Date(b.date)-new Date(a.date));
  el.innerHTML=items.slice(0,10).map((n,i)=>
    `<a class="ni" href="${{n.url}}" target="_blank" rel="noopener">
      <span class="ntag${{i===0?' latest':''}}">${{i===0?'Ã°ÂÂÂ´ Ã¬ÂµÂÃ¬ÂÂ ':'#'+(i+1)}}</span>
      <span class="nt">${{n.title}}</span>
      <span class="nsrc">${{n.source}}${{n.date?' ÃÂ· '+timeAgo(n.date):''}}</span>
    </a>`
  ).join('');
}}

async function fetchNews(rssUrl,listId,filterFn){{
  try{{
    const r=await fetch(PROXY(rssUrl));if(!r.ok)return;
    const xml=(await r.json()).contents;
    if(!xml)return;
    let items=parseRSS(xml);
    if(filterFn){{
      const filtered=items.filter(filterFn);
      items=filtered.length>=3?filtered:items;
    }}
    if(items.length)renderNews(items,listId);
  }}catch(e){{}}
}}

async function updateNews(){{
  await fetchNews(RSS_GEN,'gen-list',null);
  const n=new Date();
  document.getElementById('news-updated').textContent=
    'Ã¬ÂµÂÃ¬ÂÂ Ã¬ÂÂ ÃÂ· '+n.getHours().toString().padStart(2,'0')+':'+n.getMinutes().toString().padStart(2,'0')+' ÃªÂ°Â±Ã¬ÂÂ ';
}}
updateNews();setInterval(updateNews,30*60*1000);
</script>
</body>
</html>"""


# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
# 5. Ã«Â©ÂÃ¬ÂÂ¸
# Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

def main():
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xrp_report.html")
    print("=" * 54)
    print("  XRP Daily Analyzer v2.0")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 54)

    df = fetch_ohlc(90)
    if df is None or len(df) < 30:
        print("Ã¢ÂÂ ÃªÂ°ÂÃªÂ²Â© Ã«ÂÂ°Ã¬ÂÂ´Ã­ÂÂ° Ã«Â¶ÂÃ¬Â¡Â±"); sys.exit(1)

    info                                    = fetch_current_info();      time.sleep(1)
    general_news                            = fetch_all_news();          time.sleep(1)
    clarity_news, genius_news, sec_news     = fetch_regulatory();        time.sleep(1)
    etf_news, xrpl_stats, rlusd_mcap       = fetch_institutional();     time.sleep(1)
    fg_value, fg_label, fg_history          = fetch_fear_greed()

    df = calc_indicators(df)
    signals, score, direction, dir_color, dir_eng = gen_signals(df)

    print("\nÃ¢ÂÂ¶ HTML Ã¬ÂÂÃ¬ÂÂ± Ã¬Â¤Â...")
    html = build_html(
        df, info, fg_value, fg_label, fg_history,
        signals, score, direction, dir_color, dir_eng,
        general_news,
        clarity_news, genius_news, sec_news,
        etf_news, xrpl_stats, rlusd_mcap
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nÃ¢ÂÂ Ã¬ÂÂÃ«Â£Â Ã¢ÂÂ {output_path}")
    print(f"   Ã«Â°Â©Ã­ÂÂ¥Ã¬ÂÂ±: {direction} ({score:+.1f}pt)")
    print("=" * 54)


if __name__ == "__main__":
    main()
