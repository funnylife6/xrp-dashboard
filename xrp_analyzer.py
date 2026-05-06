#!/usr/bin/env python3
"""
XRP Daily Analyzer v2.0
- 탭형 뉴스 (Ripple 공식 / 일반)
- 입법/규제 트래커 (CLARITY Act, GENIUS Act, SEC/CFTC)
- 기관 자금 흐름 (ETF, RLUSD, XRPL 트랜잭션)
- 실시간 가격 갱신 (30초)
의존성: pip install requests pandas
"""

import requests
import pandas as pd
import json, os, sys, time, re
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape as html_unescape

# ─────────────────────────────────────────────────
# 1. 공통 유틸
# ─────────────────────────────────────────────────

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
        print(f"  ⚠ RSS 실패 ({label}): {e}")
        return []


def fmt_large(v):
    if not v: return "—"
    if v >= 1e9: return f"${v/1e9:.2f}B"
    if v >= 1e6: return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def fmt_krw_large(v):
    """KRW 큰 숫자를 한국식 단위로 표시. 예: ₩127조 4,900억"""
    if not v:
        return "—"
    try:
        v = float(v)
    except Exception:
        return "—"

    jo = int(v // 1_000_000_000_000)
    eok = int(round((v - jo * 1_000_000_000_000) / 100_000_000))

    # 반올림으로 10,000억이 되면 1조로 올림
    if eok >= 10_000:
        jo += 1
        eok -= 10_000

    if jo > 0:
        return f"₩{jo}조 {eok:,}억" if eok else f"₩{jo}조"

    if v >= 100_000_000:
        return f"₩{int(round(v / 100_000_000)):,}억"

    if v >= 10_000:
        return f"₩{int(round(v / 10_000)):,}만"

    return f"₩{v:,.0f}"

def market_fx(info):
    """CMC KRW 가격과 USD 가격으로 환산 환율 산출."""
    usd = info.get("price_usd") or 0
    krw = info.get("price_krw") or 0
    if usd and krw:
        return krw / usd
    return 0

def fmt_pct(v):
    if v is None: return "—"
    return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"

def pct_color(v):
    if v is None: return "#94a3b8"
    return "#10b981" if v >= 0 else "#ef4444"


def parse_news_dt(date_text):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_text or "")
    except Exception:
        return None

def news_time_label(date_text):
    dt = parse_news_dt(date_text)
    if not dt:
        return ""
    try:
        from datetime import timezone
        now = datetime.now(dt.tzinfo or timezone.utc)
        sec = max(0, int((now - dt).total_seconds()))
        if sec < 60:
            return "방금 전"
        if sec < 3600:
            return f"{sec//60}분 전"
        if sec < 86400:
            return f"{sec//3600}시간 전"
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return dt.strftime("%m/%d %H:%M")


# ─────────────────────────────────────────────────
# 2. 데이터 수집
# ─────────────────────────────────────────────────

def fetch_ohlc(days=90):
    print("[1/7] 가격 데이터 수집 중...")
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/ripple/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"}, timeout=15
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  ⚠ 실패: {e}"); return None

    prices = pd.DataFrame(data["prices"],        columns=["ts", "price"])
    vols   = pd.DataFrame(data["total_volumes"], columns=["ts", "volume"])
    mcaps  = pd.DataFrame(data["market_caps"],   columns=["ts", "market_cap"])
    df = prices.copy()
    df["volume"]     = vols["volume"]
    df["market_cap"] = mcaps["market_cap"]
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df.set_index("ts", inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    print(f"  ✓ {len(df)}일치 완료")
    return df


def _parse_compact_number(text):
    """$87.78B, ₩2,066.25, 61.79B XRP 같은 표기를 숫자로 변환"""
    if text is None:
        return 0
    raw = str(text).replace("$", "").replace("₩", "").replace(",", "").strip()
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*([KMBT])?", raw, re.I)
    if not m:
        return 0
    val = float(m.group(1))
    unit = (m.group(2) or "").upper()
    mul = {"K":1e3, "M":1e6, "B":1e9, "T":1e12}.get(unit, 1)
    return val * mul


def _save_market_cache(info):
    try:
        cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmc_xrp_cache.json")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_market_cache():
    try:
        cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmc_xrp_cache.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def fetch_current_info_cmc_api():
    """CoinMarketCap 공식 API 우선 사용. 환경변수 CMC_API_KEY가 있으면 가장 정확함."""
    api_key = os.getenv("CMC_API_KEY") or os.getenv("COINMARKETCAP_API_KEY")
    if not api_key:
        return None
    try:
        r = requests.get(
            "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest",
            headers={"X-CMC_PRO_API_KEY": api_key},
            params={"slug":"xrp", "convert":"USD,KRW", "aux":"cmc_rank,circulating_supply,total_supply,max_supply"},
            timeout=15
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        row = next(iter(data.values()))[0] if isinstance(next(iter(data.values()), None), list) else next(iter(data.values()))
        q_usd = row.get("quote", {}).get("USD", {})
        q_krw = row.get("quote", {}).get("KRW", {})
        info = {
            "price_usd": q_usd.get("price", 0),
            "price_krw": q_krw.get("price", 0),
            "price_change_24h": q_usd.get("percent_change_24h", 0),
            "price_change_7d": q_usd.get("percent_change_7d", 0),
            "price_change_30d": q_usd.get("percent_change_30d", 0),
            "market_cap_usd": q_usd.get("market_cap", 0),
            "market_cap_rank": row.get("cmc_rank", 0),
            "volume_24h": q_usd.get("volume_24h", 0),
            "circulating_supply": row.get("circulating_supply", 0),
            "total_supply": row.get("total_supply", 0) or row.get("max_supply", 0),
            "ath_usd": 3.65,
            "twitter_followers": 0,
            "reddit_subscribers": 0,
            "sentiment_votes_up": 0,
            "sentiment_votes_down": 0,
            "source": "CoinMarketCap API"
        }
        _save_market_cache(info)
        return info
    except Exception as e:
        print(f"  ⚠ CMC API 실패: {e}")
        return None


def fetch_current_info_cmc_page():
    """CoinMarketCap XRP 페이지의 __NEXT_DATA__/HTML에서 가격·시총·거래량·공급량을 함께 파싱."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def walk(obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v)

    def get_num_from_any(d, keys):
        if not isinstance(d, dict):
            return 0
        for k in keys:
            if k in d and d.get(k) not in (None, "", "--"):
                val = d.get(k)
                if isinstance(val, dict):
                    for kk in ("USD", "usd", "value", "amount"):
                        if kk in val:
                            return _parse_compact_number(val.get(kk))
                return _parse_compact_number(val)
        return 0

    def find_next_json(page):
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', page, re.S | re.I)
        if not m:
            return None
        try:
            return json.loads(html_unescape(m.group(1)))
        except Exception:
            return None

    def parse_next_data(page):
        root = find_next_json(page)
        if not root:
            return None

        best = None
        best_score = -1
        for d in walk(root):
            symbol = str(d.get("symbol") or d.get("symbolName") or d.get("baseSymbol") or "").upper()
            slug = str(d.get("slug") or d.get("nameSlug") or d.get("url") or "").lower()
            name = str(d.get("name") or "").lower()
            is_xrp = symbol == "XRP" or slug == "xrp" or name == "xrp" or name == "ripple"
            if not is_xrp:
                continue

            quote = d.get("quote") or d.get("quotes") or {}
            usd_quote = {}
            if isinstance(quote, dict):
                usd_quote = quote.get("USD") or quote.get("usd") or quote

            price = get_num_from_any(usd_quote, ["price", "priceUsd", "close", "lastPrice"]) or get_num_from_any(d, ["price", "priceUsd", "price_usd"])
            market_cap = get_num_from_any(usd_quote, ["market_cap", "marketCap", "fullyDilluttedMarketCap", "fullyDilutedMarketCap"]) or get_num_from_any(d, ["marketCap", "market_cap", "marketCapUsd"])
            volume = get_num_from_any(usd_quote, ["volume_24h", "volume24h", "volume", "volumeUsd"]) or get_num_from_any(d, ["volume24h", "volume_24h", "volume", "volumeUsd"])
            circ = get_num_from_any(d, ["circulating_supply", "circulatingSupply", "availableSupply"])
            total = get_num_from_any(d, ["total_supply", "totalSupply", "max_supply", "maxSupply"])
            rank = int(get_num_from_any(d, ["cmc_rank", "cmcRank", "rank"]) or 0)
            pct24 = get_num_from_any(usd_quote, ["percent_change_24h", "percentChange24h", "change24h", "percent_change_1d"]) or get_num_from_any(d, ["percentChange24h", "percent_change_24h"])
            pct7 = get_num_from_any(usd_quote, ["percent_change_7d", "percentChange7d"]) or get_num_from_any(d, ["percentChange7d", "percent_change_7d"])
            pct30 = get_num_from_any(usd_quote, ["percent_change_30d", "percentChange30d"]) or get_num_from_any(d, ["percentChange30d", "percent_change_30d"])

            score = sum(bool(x) for x in [price, market_cap, volume, circ])
            if score > best_score:
                best_score = score
                best = {
                    "price_usd": price,
                    "market_cap_usd": market_cap,
                    "volume_24h": volume,
                    "circulating_supply": circ,
                    "total_supply": total or 100_000_000_000,
                    "market_cap_rank": rank or 4,
                    "price_change_24h": pct24,
                    "price_change_7d": pct7,
                    "price_change_30d": pct30,
                }

        if best and best_score >= 2:
            return best
        return None

    def parse_visible_text(page, krw_page=""):
        """CMC 영문/국문 페이지의 눈에 보이는 텍스트에서 핵심 시장지표를 직접 추출.
        기존 방식은 'Market cap $...' 같은 짧은 라벨만 찾으려 해서,
        CMC의 본문 문장인 'live market cap of $...' / '24-hour trading volume of $...'
        을 놓치는 문제가 있었다.
        """
        text = re.sub(r"<[^>]+>", " ", page)
        text = html_unescape(re.sub(r"\s+", " ", text))
        krw_text = re.sub(r"<[^>]+>", " ", krw_page or page)
        krw_text = html_unescape(re.sub(r"\s+", " ", krw_text))

        def first_num(patterns, src=text):
            for pat in patterns:
                m = re.search(pat, src, re.I)
                if m:
                    return _parse_compact_number(m.group(1))
            return 0

        price_usd = first_num([
            r"live XRP price today is \$\s*([\d,.]+)\s*USD",
            r"XRP Price\s*\$\s*([\d,.]+)",
            r"XRP to USD live price[^$]*\$\s*([\d,.]+)",
        ])

        volume = first_num([
            r"24-hour trading volume of \$\s*([\d,.]+)\s*USD",
            r"trading volume of \$\s*([\d,.]+)\s*USD",
            r"Volume\s*\(24h\)\s*\$\s*([\d,.]+\s*[KMBT]?)",
            r"24h trading volume\s*\$\s*([\d,.]+\s*[KMBT]?)",
        ])

        market_cap = first_num([
            r"live market cap of \$\s*([\d,.]+)\s*USD",
            r"market cap of \$\s*([\d,.]+)\s*USD",
            r"Market cap\s*\$\s*([\d,.]+\s*[KMBT]?)",
        ])

        circ = first_num([
            r"circulating supply of\s*([\d,.]+)\s*XRP",
            r"Circulating supply\s*([\d,.]+\s*[KMBT]?)\s*XRP",
            r"유통 공급량\s*([\d,.]+\s*[KMBT]?)\s*XRP",
        ])

        total = first_num([
            r"max\. supply of\s*([\d,.]+)\s*XRP",
            r"max supply of\s*([\d,.]+)\s*XRP",
            r"Total supply\s*([\d,.]+\s*[KMBT]?)\s*XRP",
            r"최대 공급량\s*([\d,.]+\s*[KMBT]?)\s*XRP",
            r"총 공급량\s*([\d,.]+\s*[KMBT]?)\s*XRP",
        ]) or 100_000_000_000

        # 국문 CMC 페이지의 첫 번째 큰 KRW 가격을 우선 사용
        price_krw = first_num([
            r"₩\s*([\d,.]+)",
            r"XRP 가격[^₩]*₩\s*([\d,.]+)",
        ], src=krw_text)

        rank = int(first_num([
            r"current CoinMarketCap ranking is #\s*(\d+)",
            r"CoinMarketCap ranking is #\s*(\d+)",
        ]) or 4)

        change_24h = 0
        m = re.search(r"XRP is (up|down)\s*([\d.]+)% in the last 24 hours", text, re.I)
        if m:
            change_24h = float(m.group(2)) * (-1 if m.group(1).lower() == "down" else 1)

        # 보정: CMC 문장 파싱에서 하나가 빠진 경우 가격*유통량으로 시총 계산
        if price_usd and circ and not market_cap:
            market_cap = price_usd * circ
        if price_usd and market_cap and not circ:
            circ = market_cap / price_usd

        return {
            "price_usd": price_usd,
            "price_krw": price_krw,
            "market_cap_usd": market_cap,
            "volume_24h": volume,
            "circulating_supply": circ,
            "total_supply": total,
            "market_cap_rank": rank,
            "price_change_24h": change_24h,
            "price_change_7d": 0,
            "price_change_30d": 0,
        }

    try:
        page = requests.get("https://coinmarketcap.com/currencies/xrp/", headers=headers, timeout=18).text
        krw_page = requests.get("https://coinmarketcap.com/ko/currencies/xrp/", headers=headers, timeout=18).text

        info = parse_next_data(page) or {}
        visible = parse_visible_text(page, krw_page)

        # __NEXT_DATA__가 일부만 잡히면 보이는 텍스트/계산값으로 보강
        for k, v in visible.items():
            if not info.get(k) and v:
                info[k] = v

        if info.get("market_cap_usd") and info.get("circulating_supply") and not info.get("price_usd"):
            info["price_usd"] = info["market_cap_usd"] / info["circulating_supply"]
        if info.get("price_usd") and info.get("circulating_supply") and not info.get("market_cap_usd"):
            info["market_cap_usd"] = info["price_usd"] * info["circulating_supply"]

        if not (info.get("price_usd") and info.get("market_cap_usd") and info.get("volume_24h")):
            return None

        info.update({
            "ath_usd": 3.65,
            "twitter_followers": 0,
            "reddit_subscribers": 0,
            "sentiment_votes_up": 0,
            "sentiment_votes_down": 0,
            "source": "CoinMarketCap Page",
        })
        info["total_supply"] = info.get("total_supply") or 100_000_000_000
        info["market_cap_rank"] = info.get("market_cap_rank") or 4
        _save_market_cache(info)
        return info
    except Exception as e:
        print(f"  ⚠ CMC 페이지 파싱 실패: {e}")
        return None


def fetch_current_info_coingecko_fallback():
    """마지막 대체 소스. CMC/API/캐시가 모두 실패했을 때만 사용."""
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
        return {
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
            "source": "CoinGecko"
        }
    except Exception as e:
        print(f"  ⚠ CoinGecko 대체 실패: {e}")
        return {}


def fetch_current_info():
    print("[2/7] 시장 정보 수집 중... CoinGecko 우선")

    # 가격 / 시가총액 / 24H 거래량 / 7D 변동률은 CoinGecko를 기준으로 사용합니다.
    # GitHub Pages 브라우저 30초 갱신 JS도 같은 CoinGecko 엔드포인트를 사용하므로
    # 초기 HTML 값과 실시간 갱신 값의 출처가 일치합니다.
    info = fetch_current_info_coingecko_fallback()

    # CoinGecko 장애 시에만 CMC API/페이지/캐시를 폴백으로 사용합니다.
    if not info:
        info = fetch_current_info_cmc_api()
    if not info:
        info = fetch_current_info_cmc_page()
    if not info:
        cached = _load_market_cache()
        if cached:
            cached["source"] = cached.get("source", "Market Cache") + " / Cache"
            info = cached
            print("  ✓ 시장 정보 캐시 사용")

    if info:
        print(f"  ✓ 현재가 ${info.get('price_usd',0):,.4f} / ₩{info.get('price_krw',0):,.0f} / 시총 {fmt_large(info.get('market_cap_usd',0))} / 거래량 {fmt_large(info.get('volume_24h',0))} ({info.get('source','')})")
    return info or {}


def fetch_all_news():
    print("[3/7] 국내 XRP / 리플 최신 뉴스 수집 중...")

    rss_queries = [
        ("https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko", "리플 XRP"),
        ("https://news.google.com/rss/search?q=XRP+ETF+%EB%A6%AC%ED%94%8C&hl=ko&gl=KR&ceid=KR:ko", "XRP ETF"),
        ("https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+SEC+XRP&hl=ko&gl=KR&ceid=KR:ko", "리플 SEC"),
        ("https://news.google.com/rss/search?q=RLUSD+%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko", "RLUSD"),
    ]

    priority_sources = ["연합뉴스", "뉴스1", "블로터", "디지털애셋", "매일경제", "한국경제", "이데일리", "조선비즈", "서울경제", "코인데스크", "토큰포스트"]
    priority_terms = ["ETF", "SEC", "리플", "XRP", "RLUSD", "송금", "기관", "은행", "업비트", "빗썸", "현물"]
    block_terms = ["prediction", "forecast", "price analysis", "2030", "2040", "$50", "$100", "hit this price", "crash", "beyond"]

    merged = []
    seen = set()
    for url, label in rss_queries:
        for n in fetch_rss(url, 8, label):
            title = html_unescape(n.get("title", "")).strip()
            source = html_unescape(n.get("source", "")).strip()
            key = re.sub(r"\s+", " ", title.lower())
            if not title or key in seen:
                continue
            text = f"{title} {source}".lower()
            if any(term.lower() in text for term in block_terms):
                continue
            score = 0
            if any(src in source for src in priority_sources):
                score += 5
            score += sum(1 for term in priority_terms if term.lower() in text)
            n["title"] = title
            n["source"] = source or "Google News KR"
            n["score"] = score
            seen.add(key)
            merged.append(n)

    def date_key(n):
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(n.get("date", "")).timestamp()
        except Exception:
            return 0

    # 최신 날짜순 정렬을 최우선으로 적용합니다.
    # 우선 언론사/키워드 점수는 동일 시간대 보조 정렬에만 사용합니다.
    merged.sort(key=lambda n: (date_key(n), n.get("score", 0)), reverse=True)
    print(f"  ✓ 국내 뉴스 {len(merged)}건 수집 / 최신순 정렬")
    return merged[:10]


def _merge_sorted_news(rss_queries, max_per_feed=8, limit=10):
    """여러 Google News RSS를 합치고, 중복 제거 후 최신순으로 정렬."""
    priority_sources = ["연합뉴스", "뉴스1", "블로터", "디지털애셋", "매일경제", "한국경제", "이데일리", "조선비즈", "서울경제", "코인데스크", "토큰포스트"]
    block_terms = ["prediction", "forecast", "price analysis", "2030", "2040", "$50", "$100", "hit this price", "beyond"]
    merged, seen = [], set()

    for url, label in rss_queries:
        for n in fetch_rss(url, max_per_feed, label):
            title = html_unescape(n.get("title", "")).strip()
            source = html_unescape(n.get("source", "")).strip()
            key = re.sub(r"\s+", " ", title.lower())
            if not title or key in seen:
                continue
            text = f"{title} {source}".lower()
            if any(term.lower() in text for term in block_terms):
                continue
            score = 0
            if any(src in source for src in priority_sources):
                score += 5
            n["title"] = title
            n["source"] = source or "Google News KR"
            n["score"] = score
            seen.add(key)
            merged.append(n)

    def date_key(n):
        dt = parse_news_dt(n.get("date", ""))
        return dt.timestamp() if dt else 0

    merged.sort(key=lambda n: (date_key(n), n.get("score", 0)), reverse=True)
    return merged[:limit]


def translate_etf_title_to_ko(title):
    """해외 ETF 기사 제목을 한국어 느낌의 짧은 제목으로 보정합니다. 외부 번역 API 없이 규칙 기반으로 처리합니다."""
    t = html_unescape(title or "").strip()
    if not t:
        return t
    if re.search(r"[가-힣]", t):
        return t

    low = t.lower()
    m = re.search(r"xrp spot etfs?.*?(?:net inflows?|inflows?).*?(?:\$\s*([0-9]+(?:\.[0-9]+)?\s*[mb]))", low, re.I)
    if m:
        return f"XRP 현물 ETF, 순유입 {m.group(1).upper()} 기록"
    m = re.search(r"(?:net inflows?|inflows?).*?(\$\s*[0-9]+(?:\.[0-9]+)?\s*[mb]).*?xrp", low, re.I)
    if m:
        return f"XRP 현물 ETF, 순유입 {m.group(1).upper()} 기록"
    if "outflow" in low:
        return "XRP 현물 ETF, 자금 유출 흐름 발생"
    if "inflow" in low:
        return "XRP 현물 ETF, 자금 유입 흐름 지속"
    if "aum" in low or "assets under management" in low:
        return "XRP 현물 ETF, 운용자산 규모 변동"
    if "institutional" in low:
        return "XRP ETF, 기관 수요 관련 동향"
    if "sec" in low and "etf" in low:
        return "SEC의 XRP ETF 심사 관련 동향"
    if "approved" in low or "approval" in low:
        return "XRP 현물 ETF 승인 관련 소식"
    if "xrp etf" in low or "xrp spot etf" in low:
        return "XRP 현물 ETF 관련 최신 동향"
    return t


def fetch_etf_news():
    """기관/ETF 최신 동향: 국내 기사 우선, 부족하면 해외 기사 제목을 한국어 요약형으로 보정."""
    print("[ETF] 국내/번역 ETF 뉴스 수집 중...")
    domestic = _merge_sorted_news([
        ("https://news.google.com/rss/search?q=XRP+ETF+%EB%A6%AC%ED%94%8C&hl=ko&gl=KR&ceid=KR:ko", "국내 XRP ETF 리플"),
        ("https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+%ED%98%84%EB%AC%BC+ETF&hl=ko&gl=KR&ceid=KR:ko", "리플 현물 ETF"),
        ("https://news.google.com/rss/search?q=XRP+%ED%98%84%EB%AC%BC+ETF+SEC&hl=ko&gl=KR&ceid=KR:ko", "XRP 현물 ETF SEC"),
        ("https://news.google.com/rss/search?q=XRP+ETF+%EC%88%9C%EC%9C%A0%EC%9E%85&hl=ko&gl=KR&ceid=KR:ko", "XRP ETF 순유입"),
    ], max_per_feed=8, limit=8)

    if len(domestic) >= 4:
        print(f"  ✓ 국내 ETF 뉴스 {len(domestic)}건")
        return domestic[:6]

    overseas_raw = fetch_rss(
        "https://news.google.com/rss/search?q=XRP+spot+ETF+inflow+AUM+institutional&hl=en&gl=US&ceid=US:en",
        10, "XRP ETF overseas"
    )
    seen = {re.sub(r"\s+", " ", n.get("title", "").lower()).strip() for n in domestic}
    translated = []
    for n in overseas_raw:
        title = html_unescape(n.get("title", "")).strip()
        if not title:
            continue
        key = re.sub(r"\s+", " ", title.lower()).strip()
        if key in seen:
            continue
        n = dict(n)
        n["title"] = translate_etf_title_to_ko(title)
        src = html_unescape(n.get("source", "")).strip() or "해외 뉴스"
        n["source"] = f"{src} · 번역요약"
        translated.append(n)
        seen.add(key)
        if len(domestic) + len(translated) >= 6:
            break

    combined = domestic + translated
    def date_key(n):
        dt = parse_news_dt(n.get("date", ""))
        return dt.timestamp() if dt else 0
    combined.sort(key=date_key, reverse=True)
    print(f"  ✓ ETF 뉴스 {len(combined)}건 / 국내 {len(domestic)}건 / 번역요약 {len(translated)}건")
    return combined[:6]


def fetch_regulatory():
    print("[4/7] 국내 규제/입법 뉴스 수집 중...")
    clarity = _merge_sorted_news([
        ("https://news.google.com/rss/search?q=CLARITY+Act+%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko", "CLARITY 리플 XRP"),
        ("https://news.google.com/rss/search?q=%EB%94%94%EC%A7%80%ED%84%B8%EC%9E%90%EC%82%B0+%EC%8B%9C%EC%9E%A5%EA%B5%AC%EC%A1%B0%EB%B2%95+XRP&hl=ko&gl=KR&ceid=KR:ko", "디지털자산 시장구조법 XRP"),
        ("https://news.google.com/rss/search?q=%EB%AF%B8%EA%B5%AD+%EA%B0%80%EC%83%81%EC%9E%90%EC%82%B0+CLARITY+Act&hl=ko&gl=KR&ceid=KR:ko", "미국 가상자산 CLARITY Act"),
    ], limit=4)
    genius = _merge_sorted_news([
        ("https://news.google.com/rss/search?q=GENIUS+Act+%EC%8A%A4%ED%85%8C%EC%9D%B4%EB%B8%94%EC%BD%94%EC%9D%B8+%EB%A6%AC%ED%94%8C+RLUSD&hl=ko&gl=KR&ceid=KR:ko", "GENIUS 스테이블코인 리플 RLUSD"),
        ("https://news.google.com/rss/search?q=%EB%AF%B8%EA%B5%AD+%EC%8A%A4%ED%85%8C%EC%9D%B4%EB%B8%94%EC%BD%94%EC%9D%B8+%EB%B2%95%EC%95%88+RLUSD&hl=ko&gl=KR&ceid=KR:ko", "미국 스테이블코인 법안 RLUSD"),
        ("https://news.google.com/rss/search?q=%EC%8A%A4%ED%85%8C%EC%9D%B4%EB%B8%94%EC%BD%94%EC%9D%B8+%EA%B7%9C%EC%A0%9C+GENIUS+Act&hl=ko&gl=KR&ceid=KR:ko", "스테이블코인 규제 GENIUS"),
    ], limit=4)
    sec = _merge_sorted_news([
        ("https://news.google.com/rss/search?q=SEC+CFTC+%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko", "SEC CFTC 리플 XRP"),
        ("https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+SEC+%EC%86%8C%EC%86%A1+XRP&hl=ko&gl=KR&ceid=KR:ko", "리플 SEC 소송 XRP"),
        ("https://news.google.com/rss/search?q=XRP+ETF+SEC+%EB%A6%AC%ED%94%8C&hl=ko&gl=KR&ceid=KR:ko", "XRP ETF SEC 리플"),
    ], limit=4)
    print(f"  ✓ 국내 CLARITY {len(clarity)}건 / GENIUS {len(genius)}건 / SEC {len(sec)}건")
    return clarity, genius, sec


def _money_to_usd(text):
    """뉴스 제목에서 $124M, 2.8 billion 같은 금액 표현을 USD 숫자로 변환."""
    if not text:
        return None
    m = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|bn|b|million|mn|m)\b", text, re.I)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit in ("billion", "bn", "b"):
        value *= 1_000_000_000
    else:
        value *= 1_000_000
    return int(value)


def parse_etf_flow_from_news(items):
    """
    Google News RSS 제목을 기준으로 XRP ETF 유입액/AUM/승인 수를 자동 추정합니다.
    주의: 뉴스 제목 기반 파싱이라 공식 API만큼 정확하지 않을 수 있습니다.
    """
    parsed = {
        "approved_count": 0,
        "daily_inflow_usd": 0,
        "weekly_inflow_usd": 0,
        "aum_usd": 0,
        "updated_at": "뉴스 자동 파싱 대기",
        "data_source": "news_parse"
    }

    for item in items or []:
        title = (item.get("title") or "").strip()
        source = (item.get("source") or "").strip()
        text = f"{title} {source}"
        low = text.lower()

        # 승인 수: "6 XRP ETFs approved" / "six spot XRP ETFs" 같은 제목 대응
        m_count = re.search(r"\b(\d{1,2})\b\s+(?:spot\s+)?xrp\s+etfs?", low)
        if m_count and ("approv" in low or "launch" in low or "trading" in low):
            parsed["approved_count"] = max(parsed["approved_count"], int(m_count.group(1)))

        money = _money_to_usd(text)
        if not money:
            continue

        sign = -1 if "outflow" in low or "outflows" in low else 1
        money *= sign

        if "cumulative" in low or "total net inflow" in low or "누적" in low or "총 순유입" in low:
            parsed["total_net_inflow_usd"] = money
        elif "aum" in low or "assets under management" in low or "asset under management" in low:
            parsed["aum_usd"] = money
        elif "week" in low or "weekly" in low or "7-day" in low or "7 day" in low:
            parsed["weekly_inflow_usd"] = money
        elif "inflow" in low or "inflows" in low or "flow" in low or "flows" in low or "순유입" in low:
            # 날짜 단서가 없어도 ETF inflow 제목이면 오늘/최근 유입액으로 표시
            if parsed["daily_inflow_usd"] == 0:
                parsed["daily_inflow_usd"] = money

    # 제목 안에 일일/누적이 함께 들어오는 기사 패턴 보조 파싱
    for item in items or []:
        pair = _extract_etf_inflow_pair_from_text(f"{item.get('title','')} {item.get('source','')}")
        if pair.get("daily_inflow_usd") and not parsed.get("daily_inflow_usd"):
            parsed["daily_inflow_usd"] = pair["daily_inflow_usd"]
        if pair.get("total_net_inflow_usd") and not parsed.get("total_net_inflow_usd"):
            parsed["total_net_inflow_usd"] = pair["total_net_inflow_usd"]

    if any(parsed.get(k, 0) for k in ("daily_inflow_usd", "total_net_inflow_usd", "weekly_inflow_usd", "approved_count")):
        parsed["updated_at"] = datetime.now().strftime("뉴스 순유입 파싱 %m/%d %H:%M")
    return parsed


def _extract_money_near(text, keywords):
    """주어진 키워드 주변에 있는 금액 표현을 USD 숫자로 변환."""
    if not text:
        return None
    for kw in keywords:
        # keyword 앞뒤 140자 안에서 $1.23B / 1.23 million 같은 패턴 탐색
        for m_kw in re.finditer(re.escape(kw), text, re.I):
            a = max(0, m_kw.start() - 140)
            b = min(len(text), m_kw.end() + 140)
            chunk = text[a:b]
            money = _money_to_usd(chunk)
            if money:
                sign = -1 if re.search(r"outflow|net outflow|유출", chunk, re.I) else 1
                return money * sign
    return None


def _walk_json(obj):
    """중첩 JSON 내부의 모든 dict를 순회."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_json(v)


def _num_from_any(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(float(v))
    if isinstance(v, str):
        raw = v.strip().replace(',', '')
        try:
            return int(float(raw))
        except Exception:
            return _money_to_usd(v)
    return None


def _pick_first_numeric_from_json(data, key_candidates):
    """SoSoValue 내부 JSON/API 응답 구조가 바뀌어도 키 이름 후보로 숫자를 최대한 찾아냄."""
    keys = [k.lower() for k in key_candidates]
    for d in _walk_json(data):
        for k, v in d.items():
            kl = str(k).lower()
            if any(c in kl for c in keys):
                n = _num_from_any(v)
                if n is not None:
                    return n
    return None



def _normalize_money_text(text):
    """HTML/Next.js/JSON에 섞인 금액 문자열을 파싱하기 좋게 정리."""
    if not text:
        return ""
    normalized = html_unescape(str(text))
    normalized = normalized.replace('\\u0024', '$').replace('\\/', '/')
    normalized = normalized.replace('USD', ' USD ').replace('usd', ' USD ')
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _extract_money_after_label(text, labels, search_window=420):
    """SoSoValue 상단 요약 카드처럼 '라벨 → $값' 순서로 붙어 있는 텍스트에서 첫 금액만 추출."""
    normalized = _normalize_money_text(text)
    if not normalized:
        return None
    for label in labels:
        m = re.search(re.escape(label), normalized, re.I)
        if not m:
            continue
        chunk = normalized[m.end():m.end()+search_window]
        money = _money_to_usd(chunk)
        if money is not None:
            return money
    return None


def _extract_etf_inflow_pair_from_text(text):
    """일일 순유입량과 누적 순유입량만 전용으로 추출. AUM/거래대금은 성공 기준에서 제외."""
    clean = _normalize_money_text(text)
    result = {"daily_inflow_usd": 0, "total_net_inflow_usd": 0}

    daily_labels = [
        "Daily Total Net Inflow", "Daily Net Inflow", "Net Inflow",
        "single-day net inflow", "single day net inflow", "daily inflow",
        "일일 순유입", "당일 순유입"
    ]
    cumulative_labels = [
        "Cumulative Total Net Inflow", "Cumulative Net Inflow", "Total Net Inflow",
        "cumulative net inflow", "total cumulative net inflow",
        "누적 순유입", "총 순유입"
    ]

    daily = _extract_money_after_label(clean, daily_labels)
    cumulative = _extract_money_after_label(clean, cumulative_labels)

    # 기사 문장형 보조 패턴: XRP spot ETF had a single-day net inflow of $11.2M ... cumulative net inflow reached $1.3B
    if daily is None:
        daily = _extract_money_near(clean, [
            "single-day net inflow", "single day net inflow", "daily net inflow",
            "Daily Total Net Inflow", "일일 순유입", "당일 순유입"
        ])
    if cumulative is None:
        cumulative = _extract_money_near(clean, [
            "cumulative net inflow", "Cumulative Total Net Inflow", "Total Net Inflow",
            "누적 순유입", "총 순유입"
        ])

    if daily is not None:
        result["daily_inflow_usd"] = daily
    if cumulative is not None:
        result["total_net_inflow_usd"] = cumulative
    return result


def _extract_etf_count_from_table(text):
    """SoSoValue XRP ETF 테이블에 실제 표시되는 XRP ETF ticker 개수를 세기 위한 보수적 추출."""
    if not text:
        return 0
    # XRP 자체는 티커가 아니라 자산명으로 자주 등장하므로 제외한다.
    ticker_candidates = {"XRP", "XRPC", "XRPZ", "TOXR", "GXRP", "XRPR", "XRPI"}
    found = set(re.findall(r"\b(XRPC|XRPZ|TOXR|GXRP|XRPR|XRPI)\b", text))
    return len(found)




def _fetch_sosovalue_rendered_text(url="https://sosovalue.com/assets/etf/us-xrp-spot"):
    """GitHub Actions에서 Playwright/Chromium으로 SoSoValue JS 렌더링 후 보이는 텍스트를 가져온다.
    requests HTML에 순유입값이 없을 때만 쓰는 무거운 폴백이다.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"  ⚠ Playwright 사용 불가: {e}")
        return ""

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1440, "height": 1200},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                locale="en-US",
            )
            page.goto(url, wait_until="networkidle", timeout=45000)
            # SoSoValue 상단 카드/테이블이 늦게 붙는 경우 대비
            page.wait_for_timeout(5000)
            text = page.locator("body").inner_text(timeout=10000)
            html = page.content()
            browser.close()
            return f"{text}\n{html}"
    except Exception as e:
        print(f"  ⚠ Playwright SoSoValue 렌더링 실패: {e}")
        return ""

def fetch_sosovalue_etf_flow():
    """
    SoSoValue XRP spot ETF 페이지에서 상단 요약 카드 값을 우선 추출합니다.
    핵심 수정점: 뉴스/히스토리 테이블의 첫 금액을 잡지 않고,
    Daily Total Net Inflow / Cumulative Total Net Inflow / Total Value Traded / Total Net Assets 라벨 직후 금액만 사용합니다.
    실패하면 None을 반환해 캐시/뉴스 파싱으로 넘어갑니다.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Referer": "https://sosovalue.com/assets/etf/us-xrp-spot",
        "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    }

    result = {
        "approved_count": 0,
        "daily_inflow_usd": 0,
        "weekly_inflow_usd": 0,
        "aum_usd": 0,
        "total_value_traded_usd": 0,
        "total_net_inflow_usd": 0,
        "total_value_traded_usd": 0,
        "updated_at": "ETF 데이터 수집중",
        "data_source": "sosovalue"
    }

    page_urls = [
        "https://sosovalue.com/assets/etf/us-xrp-spot",
        "https://m.sosovalue.com/assets/etf/us-xrp-spot",
    ]

    for url in page_urls:
        try:
            r = requests.get(url, headers=headers, timeout=18)
            if not r.ok or not r.text:
                continue

            html = r.text
            clean = re.sub(r"<[^>]+>", " ", html_unescape(html))
            clean = clean.replace('\\u0024', '$')
            clean = re.sub(r"\s+", " ", clean)

            # 1순위: 일일 순유입 + 누적 순유입 전용 추출
            inflow_pair = _extract_etf_inflow_pair_from_text(clean)
            daily = inflow_pair.get("daily_inflow_usd") or None
            cumulative = inflow_pair.get("total_net_inflow_usd") or None
            traded = _extract_money_after_label(clean, [
                "Total Value Traded", "Value Traded"
            ])
            assets = _extract_money_after_label(clean, [
                "Total Net Assets", "Net Assets", "AUM"
            ])

            if daily is not None:
                result["daily_inflow_usd"] = daily
            if cumulative is not None:
                result["total_net_inflow_usd"] = cumulative
            if traded is not None:
                result["total_value_traded_usd"] = traded
            if assets is not None:
                result["aum_usd"] = assets

            count = _extract_etf_count_from_table(clean)
            if count:
                result["approved_count"] = count

            # 2순위: __NEXT_DATA__가 있을 때도 broad key first-match는 금지.
            # 일일/누적 순유입값이 없을 때만 보조적으로 사용한다.
            if not any(result.get(k, 0) for k in ("daily_inflow_usd", "total_net_inflow_usd")):
                m_next = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
                if m_next:
                    try:
                        data = json.loads(html_unescape(m_next.group(1)))
                        result["daily_inflow_usd"] = _pick_first_numeric_from_json(data, [
                            "dailyTotalNetInflow", "daily_total_net_inflow"
                        ]) or 0
                        result["aum_usd"] = _pick_first_numeric_from_json(data, [
                            "totalNetAssets", "total_net_assets"
                        ]) or 0
                        result["total_value_traded_usd"] = _pick_first_numeric_from_json(data, [
                            "totalValueTraded", "total_value_traded"
                        ]) or 0
                        result["total_net_inflow_usd"] = _pick_first_numeric_from_json(data, [
                            "cumulativeTotalNetInflow", "cumulative_total_net_inflow"
                        ]) or 0
                    except Exception:
                        pass

            # 성공 기준은 AUM/거래대금이 아니라 '일일 순유입' 또는 '누적 순유입'이다.
            # AUM만 잡힌 경우에는 정상 데이터로 저장하지 않고 뉴스/백업 폴백으로 넘긴다.
            has_inflow = bool(result.get("daily_inflow_usd") or result.get("total_net_inflow_usd"))
            if has_inflow:
                result["partial"] = not bool(result.get("daily_inflow_usd") and result.get("total_net_inflow_usd"))
                result["updated_at"] = datetime.now().strftime(
                    ("SoSoValue 순유입 부분 수집 " if result["partial"] else "SoSoValue 순유입 ") + "%m/%d %H:%M"
                )
                _save_etf_cache(result)
                return result

        except Exception as e:
            print(f"  ⚠ SoSoValue 페이지 수집 실패({url}): {e}")

    # 3순위: requests에 순유입값이 없으면 Chromium으로 JS 렌더링된 화면 텍스트에서 다시 추출한다.
    rendered = _fetch_sosovalue_rendered_text()
    if rendered:
        inflow_pair = _extract_etf_inflow_pair_from_text(rendered)
        daily = inflow_pair.get("daily_inflow_usd") or 0
        cumulative = inflow_pair.get("total_net_inflow_usd") or 0
        if daily or cumulative:
            result["daily_inflow_usd"] = daily
            result["total_net_inflow_usd"] = cumulative
            assets = _extract_money_after_label(rendered, ["Total Net Assets", "Net Assets", "AUM"])
            traded = _extract_money_after_label(rendered, ["Total Value Traded", "Value Traded"])
            count = _extract_etf_count_from_table(rendered)
            if assets is not None:
                result["aum_usd"] = assets
            if traded is not None:
                result["total_value_traded_usd"] = traded
            if count:
                result["approved_count"] = count
            result["partial"] = not bool(daily and cumulative)
            result["updated_at"] = datetime.now().strftime(
                ("SoSoValue 렌더링 순유입 부분 수집 " if result["partial"] else "SoSoValue 렌더링 순유입 ") + "%m/%d %H:%M"
            )
            _save_etf_cache(result)
            return result

    return None

def _etf_cache_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "etf_cache.json")


def _save_etf_cache(data):
    try:
        payload = dict(data)
        payload["cached_at"] = datetime.now().isoformat(timespec="seconds")
        with open(_etf_cache_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ ETF 캐시 저장 실패: {e}")


def _load_etf_cache():
    try:
        path = _etf_cache_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if any(data.get(k, 0) for k in ("daily_inflow_usd", "total_net_inflow_usd")):
                data["data_source"] = data.get("data_source", "cache")
                data["updated_at"] = data.get("updated_at") or "ETF 캐시"
                return data
    except Exception as e:
        print(f"  ⚠ ETF 캐시 로드 실패: {e}")
    return None


def load_etf_flow_data(etf_news=None):
    """
    ETF 유입자금은 일일 순유입량과 누적 순유입량을 최우선으로 수집합니다.
    SoSoValue 직접 수집 실패 시 etf_cache.json → Google News RSS 자동 파싱 → xrp_etf_flows.json 순서로 폴백합니다.
    """
    default = {
        "approved_count": 0,
        "daily_inflow_usd": 0,
        "weekly_inflow_usd": 0,
        "aum_usd": 0,
        "total_net_inflow_usd": 0,
        "total_value_traded_usd": 0,
        "updated_at": "ETF 데이터 수집 대기",
        "data_source": "none"
    }

    soso = fetch_sosovalue_etf_flow()
    if soso:
        default.update(soso)
        return default

    cache = _load_etf_cache()
    if cache:
        default.update(cache)
        if "SoSoValue" not in str(default.get("updated_at", "")):
            default["updated_at"] = str(default.get("updated_at", "ETF 캐시")) + " · 캐시"
        elif cache.get("partial") and "부분 수집" not in str(default.get("updated_at", "")):
            default["updated_at"] = str(default.get("updated_at", "SoSoValue")) + " · 부분 수집 캐시"
        return default

    parsed = parse_etf_flow_from_news(etf_news or [])
    default.update({k: parsed.get(k, default.get(k)) for k in default})

    # 뉴스에서 숫자를 못 찾은 경우에만 로컬 JSON 값을 보정값으로 사용
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xrp_etf_flows.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in ("approved_count", "daily_inflow_usd", "weekly_inflow_usd", "aum_usd", "total_net_inflow_usd", "total_value_traded_usd"):
                if not default.get(k) and data.get(k):
                    default[k] = data.get(k)
            if any(default.get(k, 0) for k in ("daily_inflow_usd", "total_net_inflow_usd")) and data.get("updated_at"):
                if default.get("updated_at") == "ETF 데이터 수집 대기":
                    default["updated_at"] = data.get("updated_at")
                    default["data_source"] = "json_backup"
    except Exception as e:
        print(f"  ⚠ ETF 백업 데이터 로드 실패: {e}")

    return default


def _xrpl_cache_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "xrpl_stats_cache.json")


def _save_xrpl_cache(data):
    try:
        payload = dict(data)
        payload["cached_at"] = datetime.now().isoformat(timespec="seconds")
        with open(_xrpl_cache_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ XRPL 캐시 저장 실패: {e}")


def _load_xrpl_cache():
    try:
        if os.path.exists(_xrpl_cache_path()):
            with open(_xrpl_cache_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("tps_24h_avg") or data.get("recent_tps"):
                data["status"] = data.get("status") or "cache"
                data["status_label"] = data.get("status_label") or "캐시"
                return data
    except Exception as e:
        print(f"  ⚠ XRPL 캐시 로드 실패: {e}")
    return None


def fetch_xrpl_network_stats(sample_ledgers=24):
    """
    GitHub Pages/Actions용 XRPL 네트워크 지표 수집.
    - 최근 validated ledger 여러 개를 직접 조회해 평균 TPS 계산
    - 실패 시 0.00으로 오해시키지 않고 status=pending 반환
    - transaction_stats API는 보조값(tx/day) 용도로만 사용
    """
    xrpl = {
        "tx_today": 0,
        "tx_7d_avg": 0,
        "tps_24h_avg": None,
        "recent_tps": None,
        "recent_tx_count": 0,
        "recent_ledger_count": 0,
        "recent_window_sec": 0,
        "ledger_seq": 0,
        "ledger_close_sec": 0,
        "load_factor": 0,
        "peers": 0,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
        "status": "pending",
        "status_label": "TPS 수집중",
        "data_source": "xrpl_recent_ledgers"
    }

    endpoints = ("https://s1.ripple.com:51234/", "https://s2.ripple.com:51234/", "https://xrplcluster.com/")

    def rpc(endpoint, method, params=None, timeout=10):
        r = requests.post(endpoint, json={"method": method, "params": [params or {}]}, timeout=timeout)
        r.raise_for_status()
        js = r.json()
        result = js.get("result", {})
        if result.get("error"):
            raise RuntimeError(result.get("error_message") or result.get("error"))
        return result

    def ripple_time_to_unix(rt):
        # Ripple epoch starts at 2000-01-01T00:00:00Z
        try:
            return int(rt) + 946684800
        except Exception:
            return 0

    selected_endpoint = None

    # 1) server_info로 최신 validated ledger 확인
    for endpoint in endpoints:
        try:
            result = rpc(endpoint, "server_info", {}, timeout=10)
            info = result.get("info", {})
            vl = info.get("validated_ledger", {}) or {}
            last_close = info.get("last_close", {}) or {}
            xrpl["ledger_seq"] = int(vl.get("seq") or info.get("validated_ledger_seq") or 0)
            xrpl["ledger_close_sec"] = float(last_close.get("converge_time_s") or 0)
            xrpl["load_factor"] = float(info.get("load_factor") or 0)
            xrpl["peers"] = int(info.get("peers") or 0)
            if xrpl["ledger_seq"]:
                selected_endpoint = endpoint
                break
        except Exception as e:
            print(f"  ⚠ XRPL server_info 실패({endpoint}): {e}")

    # 2) 최근 ledger 샘플에서 직접 TPS 계산
    if selected_endpoint and xrpl["ledger_seq"]:
        start_seq = max(1, xrpl["ledger_seq"] - int(sample_ledgers) + 1)
        total_tx = 0
        close_times = []
        ledgers_seen = 0
        for seq in range(start_seq, xrpl["ledger_seq"] + 1):
            try:
                result = rpc(selected_endpoint, "ledger", {
                    "ledger_index": seq,
                    "transactions": True,
                    "expand": False
                }, timeout=10)
                ledger = result.get("ledger", {}) or {}
                txs = ledger.get("transactions") or []
                total_tx += len(txs)
                ledgers_seen += 1
                ct = ripple_time_to_unix(ledger.get("close_time"))
                if ct:
                    close_times.append(ct)
            except Exception as e:
                print(f"  ⚠ XRPL ledger 샘플 실패(seq={seq}): {e}")

        if ledgers_seen >= 2 and len(close_times) >= 2:
            window_sec = max(close_times) - min(close_times)
            if window_sec > 0:
                recent_tps = total_tx / window_sec
                xrpl["recent_tps"] = round(recent_tps, 2)
                xrpl["tps_24h_avg"] = round(recent_tps, 2)
                xrpl["recent_tx_count"] = int(total_tx)
                xrpl["recent_ledger_count"] = int(ledgers_seen)
                xrpl["recent_window_sec"] = int(window_sec)
                xrpl["status"] = "ok"
                xrpl["status_label"] = "최근 ledger 평균"

    # 3) 일간 트랜잭션 API는 보조값으로 사용. TPS 표시는 recent ledger가 성공했을 때만 확정.
    def walk(obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v)

    def tx_count(row):
        for k in ("transaction_count", "transactions", "tx_count", "count", "number_of_transactions", "txns"):
            if isinstance(row, dict) and row.get(k) not in (None, "", "--"):
                try:
                    return int(float(str(row.get(k)).replace(",", "")))
                except Exception:
                    pass
        return 0

    stat_urls = [
        "https://data.xrpl.org/v1/network/transaction_stats?interval=day&limit=7",
        "https://data.xrpl.org/v1/network/transaction_stats?interval=daily&limit=7",
    ]
    for url in stat_urls:
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"})
            if not r.ok:
                continue
            js = r.json()
            rows = js.get("rows") or js.get("data") or js.get("result", {}).get("rows") or js.get("result", {}).get("data") or []
            if not rows:
                rows = [d for d in walk(js) if tx_count(d)]
            if rows:
                rows_sorted = sorted(rows, key=lambda x: str(x.get("date") or x.get("day") or x.get("ledger_date") or x.get("time") or ""), reverse=True)
                counts = [tx_count(row) for row in rows_sorted if tx_count(row)]
                if counts:
                    xrpl["tx_today"] = counts[0]
                    xrpl["tx_7d_avg"] = int(sum(counts) / len(counts))
                    break
        except Exception as e:
            print(f"  ⚠ XRPL transaction_stats 실패({url}): {e}")

    if xrpl.get("status") == "ok":
        _save_xrpl_cache(xrpl)
        return xrpl

    cached = _load_xrpl_cache()
    if cached:
        cached["status"] = "cache"
        cached["status_label"] = "최근 ledger 평균 · 캐시"
        return cached

    # 캐시도 없으면 프론트에서 'TPS 수집중'으로 표시되도록 None 유지
    return xrpl

def fetch_institutional():
    print("[5/7] 기관 자금 흐름 수집 중...")

    etf_news = fetch_etf_news()

    xrpl = fetch_xrpl_network_stats()
    etf_flow = load_etf_flow_data(etf_news)

    rlusd_mcap = 0
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ripple-usd&vs_currencies=usd&include_market_cap=true",
            timeout=10
        )
        if r.ok:
            rlusd_mcap = r.json().get("ripple-usd", {}).get("usd_market_cap", 0)
    except Exception as e:
        print(f"  ⚠ RLUSD 실패: {e}")

    print(f"  ✓ ETF뉴스 {len(etf_news)}건 / XRPL tx {xrpl['tx_today']:,} / ETF AUM {fmt_large(etf_flow.get('aum_usd',0))} / RLUSD {fmt_large(rlusd_mcap)}")
    return etf_news, xrpl, rlusd_mcap, etf_flow


def fetch_fear_greed():
    print("[6/7] 공포-탐욕 지수 수집 중...")
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            latest  = data[0]
            history = [{"value": int(d["value"]), "label": d["value_classification"]} for d in data]
            print(f"  ✓ {latest['value']} ({latest['value_classification']})")
            return int(latest["value"]), latest["value_classification"], history
    except Exception as e:
        print(f"  ⚠ 실패: {e}")
    return 50, "Neutral", []


# ─────────────────────────────────────────────────
# 3. 기술 지표
# ─────────────────────────────────────────────────

def calc_indicators(df):
    print("[7/7] 기술 지표 계산 중...")
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
    print("  ✓ RSI / MACD / 볼린저밴드 / MA 완료")
    return df


def gen_signals(df):
    latest = df.iloc[-1]; prev = df.iloc[-2]
    signals = []; score = 0.0
    price = latest["price"]

    if   latest["ma7"] > latest["ma25"] and prev["ma7"] <= prev["ma25"]:
        signals.append({"name":"MA 크로스","verdict":"매수","detail":"7일MA 골든크로스 발생"}); score += 2
    elif latest["ma7"] < latest["ma25"] and prev["ma7"] >= prev["ma25"]:
        signals.append({"name":"MA 크로스","verdict":"매도","detail":"7일MA 데드크로스 발생"}); score -= 2
    elif latest["ma7"] > latest["ma25"]:
        signals.append({"name":"MA 크로스","verdict":"매수","detail":f"MA7(${latest['ma7']:.4f}) > MA25(${latest['ma25']:.4f}) 유지"}); score += 1
    else:
        signals.append({"name":"MA 크로스","verdict":"매도","detail":f"MA7(${latest['ma7']:.4f}) < MA25(${latest['ma25']:.4f}) 유지"}); score -= 1

    rsi = latest["rsi"]
    if   rsi < 30: signals.append({"name":"RSI","verdict":"강매수","detail":f"RSI {rsi:.1f} — 과매도"}); score += 2.5
    elif rsi < 40: signals.append({"name":"RSI","verdict":"매수",  "detail":f"RSI {rsi:.1f} — 매수 우위"}); score += 1.5
    elif rsi > 70: signals.append({"name":"RSI","verdict":"강매도","detail":f"RSI {rsi:.1f} — 과매수"}); score -= 2.5
    elif rsi > 60: signals.append({"name":"RSI","verdict":"매도",  "detail":f"RSI {rsi:.1f} — 매도 우위"}); score -= 1.5
    else:          signals.append({"name":"RSI","verdict":"중립",  "detail":f"RSI {rsi:.1f} — 중립 구간"})

    bb_upper = latest["bb_upper"]; bb_lower = latest["bb_lower"]
    bb_pos   = (price - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
    if   price < bb_lower: signals.append({"name":"볼린저밴드","verdict":"매수","detail":"하단밴드 하회 — 반등 가능성"}); score += 1.5
    elif price > bb_upper: signals.append({"name":"볼린저밴드","verdict":"매도","detail":"상단밴드 돌파 — 과열 구간"}); score -= 1.5
    else:                  signals.append({"name":"볼린저밴드","verdict":"중립","detail":f"밴드 내 위치 {bb_pos:.0f}%"})

    macd, sig = latest["macd"], latest["macd_sig"]
    if   macd > sig and prev["macd"] <= prev["macd_sig"]: signals.append({"name":"MACD","verdict":"매수","detail":"골든크로스 발생"}); score += 2
    elif macd < sig and prev["macd"] >= prev["macd_sig"]: signals.append({"name":"MACD","verdict":"매도","detail":"데드크로스 발생"}); score -= 2
    elif macd > sig: signals.append({"name":"MACD","verdict":"매수","detail":"MACD > Signal 유지"}); score += 0.5
    else:            signals.append({"name":"MACD","verdict":"매도","detail":"MACD < Signal 유지"}); score -= 0.5

    vol, vol_ma = latest["volume"], latest["vol_ma7"]
    ratio = vol / vol_ma if vol_ma else 1
    if   ratio > 1.5: signals.append({"name":"거래량","verdict":"주목","detail":f"7일 평균 {ratio:.1f}배 — 급등"})
    elif ratio > 1.1: signals.append({"name":"거래량","verdict":"중립","detail":f"7일 평균 {ratio:.1f}배 — 소폭 증가"})
    else:             signals.append({"name":"거래량","verdict":"중립","detail":f"7일 평균 {ratio:.1f}배 — 평이한 수준"})

    if   score >= 3:    direction, color, eng = "강한 매수 우위", "#10b981", "STRONG BUY"
    elif score >= 1.5:  direction, color, eng = "매수 우위",      "#34d399", "BUY"
    elif score <= -3:   direction, color, eng = "강한 매도 우위", "#ef4444", "STRONG SELL"
    elif score <= -1.5: direction, color, eng = "매도 우위",      "#f87171", "SELL"
    else:               direction, color, eng = "중립 / 관망",    "#f59e0b", "HOLD"
    return signals, score, direction, color, eng


# ─────────────────────────────────────────────────
# 4. HTML 빌드
# ─────────────────────────────────────────────────

VERDICT_COLORS = {
    "강매수":"#10b981","매수":"#34d399","강매도":"#ef4444",
    "매도":"#f87171","중립":"#94a3b8","관망":"#f59e0b","주목":"#a78bfa",
}

def badge(v):
    c = VERDICT_COLORS.get(v, "#94a3b8")
    return f'<span class="badge" style="background:{c}20;color:{c};border:1px solid {c}50">{v}</span>'

def news_items_html(items):
    if not items:
        return '<p class="no-data">뉴스를 불러오는 중...</p>'
    html = ""
    for i, n in enumerate(items[:10]):
        cls = " latest" if i == 0 else ""
        rel = news_time_label(n.get("date", ""))
        tag = "🔴 최신" if i == 0 else f"#{i+1}"
        src = n.get("source", "") or "Google News KR"
        src_date = f"{src} · {rel}" if rel else src
        html += f'''<a class="ni" href="{n['url']}" target="_blank" rel="noopener">
          <span class="ntag{cls}">{tag}</span>
          <span class="nt">{n['title']}</span>
          <span class="nsrc">{src_date}</span>
        </a>'''
    return html

def reg_news_html(items):
    if not items:
        return '<p class="no-data">관련 뉴스 없음</p>'
    html = ""
    for n in items[:4]:
        rel = news_time_label(n.get("date", ""))
        src = html_unescape(n.get("source", "")).strip() or "Google News KR"
        src_date = f"{src} · {rel}" if rel else src
        title = html_unescape(n.get("title", "")).strip()
        html += f'''<a class="reg-ni" href="{n['url']}" target="_blank" rel="noopener">
          <span class="rni-dot"></span>
          <span class="rni-content">
            <span class="rni-title">{title}</span>
            <span class="rni-src">{src_date}</span>
          </span>
        </a>'''
    return html


def fmt_tps_display(xrpl_stats):
    """TPS 값이 없을 때 0.00 대신 'TPS 수집중' 표시."""
    try:
        v = xrpl_stats.get("tps_24h_avg")
        if v is None or v == "" or float(v) <= 0:
            return "TPS 수집중"
        return f"{float(v):,.2f}"
    except Exception:
        return "TPS 수집중"



def fmt_krw_large_html(v):
    """KRW 표시에서 통화기호만 작게 렌더링하기 위한 HTML formatter."""
    txt = fmt_krw_large(v)
    if txt.startswith("₩"):
        return f'<span class="cur">₩</span><span class="num">{txt[1:]}</span>'
    return f'<span class="num">{txt}</span>'

def build_html(df, info, fg_value, fg_label, fg_history,
               signals, score, direction, dir_color, dir_eng,
               general_news,
               clarity_news, genius_news, sec_news,
               etf_news, xrpl_stats, rlusd_mcap, etf_flow):

    now_kst = datetime.now().strftime("%Y년 %m월 %d일 %H:%M KST")

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
    fg_labels = [f"D-{i}" if i > 0 else "오늘" for i in range(len(fg_history)-1, -1, -1)]

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
    fx_krw = market_fx(info)
    market_cap_krw = info.get("market_cap_krw") or (info.get("market_cap_usd", 0) * fx_krw if fx_krw else 0)
    volume_24h_krw = info.get("volume_24h_krw") or (info.get("volume_24h", 0) * fx_krw if fx_krw else 0)
    rlusd_mcap_krw = (rlusd_mcap * fx_krw) if (rlusd_mcap and fx_krw) else 0

    gen_html     = news_items_html(general_news)
    clarity_html = reg_news_html(clarity_news)
    genius_html  = reg_news_html(genius_news)
    sec_html     = reg_news_html(sec_news)
    etf_html     = reg_news_html(etf_news)

    etf_daily_value = etf_flow.get("daily_inflow_usd", 0) or 0
    etf_total_value = etf_flow.get("total_net_inflow_usd", 0) or 0
    etf_aum_value = etf_flow.get("aum_usd", 0) or 0
    etf_traded_value = etf_flow.get("total_value_traded_usd", 0) or 0
    etf_count_value = etf_flow.get("approved_count", 0) or 0
    etf_updated_text = etf_flow.get("updated_at") or "ETF 순유입 수집중"
    if "SoSoValue 수집 대기" in str(etf_updated_text) or "뉴스 자동 파싱 대기" in str(etf_updated_text) or "ETF 데이터 수집 대기" in str(etf_updated_text):
        etf_updated_text = "ETF 순유입 수집중"
    etf_has_daily = bool(etf_daily_value)
    etf_has_total = bool(etf_total_value)
    etf_is_partial = bool(etf_flow.get("partial")) or "부분 수집" in str(etf_updated_text) or not (etf_has_daily and etf_has_total)
    etf_daily_text = fmt_large(etf_daily_value) if etf_has_daily else "일일 순유입 수집중"
    etf_total_text = fmt_large(etf_total_value) if etf_has_total else "누적 순유입 수집중"
    etf_status_text = "ETF 순유입 업데이트 완료" if (etf_has_daily and etf_has_total) else "ETF 순유입 부분 수집" if (etf_has_daily or etf_has_total) else "ETF 순유입 수집중"
    etf_source_text = etf_updated_text
    etf_aum_text = fmt_large(etf_aum_value) if etf_aum_value else "—"
    etf_traded_text = fmt_large(etf_traded_value) if etf_traded_value else "—"
    etf_count_text = f"{etf_count_value}개 상장" if etf_count_value else "상장 정보 수집중"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>XRP 분석 리포트 — {now_kst}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@400;600;700;800&family=Noto+Sans+KR:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
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
.wrap{{position:relative;z-index:1;max-width:900px;margin:0 auto;padding:18px 16px 40px}}
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
.cv{{font-family:var(--sans);font-size:22px;font-weight:700;line-height:1.1;min-height:28px;display:flex;align-items:baseline;gap:2px;white-space:nowrap;font-variant-numeric:tabular-nums}}
.cv .cur{{font-size:.5em;font-weight:700;line-height:1;transform:translateY(-1px);display:inline-block;opacity:.95}}
.cv .num{{font-variant-numeric:tabular-nums}}
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
.ntag.hot{{background:#f59e0b15;color:#f59e0b;border-color:#f59e0b40}}
.ni.old-news{{opacity:.62}}
.ni.old-news:hover{{opacity:.9}}
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
.reg-ni{{display:flex;align-items:flex-start;gap:8px;padding:10px 0;border-bottom:1px solid var(--border);text-decoration:none}}
.reg-ni:last-child{{border-bottom:none}}
.reg-ni:hover .rni-title{{color:var(--accent)}}
.rni-dot{{width:4px;height:4px;background:var(--accent);border-radius:50%;flex-shrink:0;margin-top:7px}}
.rni-content{{display:flex;flex-direction:column;gap:5px;min-width:0;flex:1}}
.rni-title{{display:block;font-size:12px;color:var(--text);line-height:1.45;transition:color .15s;word-break:keep-all;overflow-wrap:break-word}}
.rni-src{{display:block;font-size:9px;color:var(--muted);line-height:1.2;white-space:normal;opacity:.78}}
.inst-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px}}
@media(max-width:900px){{.inst-grid{{grid-template-columns:1fr 1fr}}}}
.inst-card{{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:18px}}
.ic-label{{font-size:10px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}}
.ic-value{{font-family:var(--sans);font-size:22px;font-weight:700}}
.ic-sub{{font-size:10px;color:var(--muted);margin-top:4px}}
.ic-mini{{display:flex;justify-content:space-between;gap:10px;margin-top:10px;padding-top:10px;border-top:1px solid var(--border);font-size:10px;color:var(--muted)}}
.ic-mini b{{color:var(--text);font-weight:700}}
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
/* ── PRO_RIPPLER Hero ── */
.pro-nav{{display:flex;align-items:center;justify-content:space-between;
  padding:4px 4px 20px;background:transparent;margin-bottom:0;font-family:'Noto Sans KR',sans-serif}}
.pro-logo-wrap{{display:flex;align-items:center;gap:10px}}
.pro-logo-img{{width:44px;height:44px;object-fit:contain;display:block;flex-shrink:0}}
.pro-logo-text{{font-family:'Noto Sans KR',sans-serif;font-size:22px;font-weight:900;
  color:#fff;letter-spacing:-0.5px;line-height:1.1}}
.pro-logo-sub{{font-size:12px;color:#8fa3bc;margin-top:2px;font-family:'Noto Sans KR',sans-serif;font-weight:500}}
.pro-nav-right{{display:flex;align-items:center;gap:14px}}
.pro-bell-wrap{{position:relative;line-height:1}}
.pro-bell{{font-size:22px;color:#94a3b8;cursor:pointer}}
.pro-bell-dot{{position:absolute;top:-1px;right:-1px;width:9px;height:9px;
  background:#3b82f6;border-radius:50%;border:2px solid #0f172a}}
.pro-avatar{{display:flex;flex-direction:column;align-items:center;gap:3px}}
.pro-avatar-icon{{width:40px;height:40px;background:#182436;border:none;
  border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px}}
.pro-lv{{font-size:10px;color:#fff;background:#006fff;font-weight:800;letter-spacing:0;padding:2px 6px;border-radius:6px;margin-top:-8px}}
/* 단일 흰색 카드 */
.pro-hero{{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center;
  background:#f4f7fd;border-radius:16px;padding:28px 28px;
  box-shadow:none;overflow:visible;margin-bottom:14px;font-family:'Noto Sans KR',sans-serif}}
@media(max-width:640px){{.pro-hero{{grid-template-columns:1fr}}}}
.hero-left{{padding:0;display:flex;flex-direction:column;justify-content:center;
  background:transparent}}
.hero-title{{font-family:'Noto Sans KR',sans-serif;font-size:28px;font-weight:900;
  line-height:1.4;color:#06101d;margin-bottom:10px;letter-spacing:-1px;word-break:keep-all}}
.hero-desc{{font-size:13px;color:#5a6b80;line-height:1.8;
  margin-bottom:20px;font-weight:500;word-break:keep-all}}
.hero-btn{{display:inline-flex;align-items:center;justify-content:center;position:relative;overflow:visible;isolation:isolate;
  background:linear-gradient(180deg,#1e7fff,#005cff);color:#fff;
  padding:11px 22px;border-radius:10px;font-size:15px;font-weight:800;
  text-decoration:none;font-family:'Noto Sans KR',sans-serif;border:none;cursor:pointer;
  box-shadow:0 8px 20px rgba(0,94,255,.25);white-space:nowrap;width:fit-content;
  transform:translateY(0);transition:transform .14s ease,box-shadow .18s ease,background .18s ease,filter .18s ease}}
.hero-btn:hover{{background:linear-gradient(180deg,#2b8cff,#0a66ff);box-shadow:0 10px 26px rgba(0,94,255,.34),0 0 0 1px rgba(96,165,250,.16)}}
.hero-btn:active{{transform:translateY(2px);box-shadow:0 4px 12px rgba(0,94,255,.22)}}
.hero-btn.flash-red{{background:linear-gradient(180deg,#ff4d5e,#dc2626);box-shadow:0 8px 28px rgba(239,68,68,.42),0 0 0 1px rgba(255,120,120,.24);filter:saturate(1.08)}}
.hero-ripple{{position:absolute;left:50%;top:50%;border-radius:999px;pointer-events:none;z-index:-1;
  transform:translate(-50%,-50%) scale(.55);opacity:.72;
  border:1.5px solid rgba(96,165,250,.72);
  background:radial-gradient(circle,rgba(96,165,250,.20) 0%,rgba(96,165,250,.10) 34%,rgba(96,165,250,0) 68%);
  box-shadow:0 0 18px rgba(96,165,250,.48),0 0 34px rgba(37,99,235,.24);
  animation:heroRipple .62s cubic-bezier(.16,1,.3,1) forwards}}
@keyframes heroRipple{{to{{transform:translate(-50%,-50%) scale(2.65);opacity:0;border-color:rgba(96,165,250,0)}}}}
.hero-right{{padding:0;background:transparent;
  border-left:none;display:flex;align-items:center;justify-content:center}}
/* 내부 흰색 카드 */
.hero-card{{background:#ffffff;border-radius:14px;
  box-shadow:0 12px 30px rgba(10,30,60,.12);
  padding:18px 20px;display:flex;flex-direction:column;gap:8px;width:100%}}
.hero-price-header{{display:flex;align-items:center;justify-content:space-between}}
.hero-pair{{font-size:13px;font-weight:700;color:#1e293b;letter-spacing:0.3px}}
.hero-live-area{{display:flex;align-items:center;gap:6px}}
.hero-live-dot{{width:8px;height:8px;background:#22c55e;border-radius:50%;
  display:inline-block;animation:pulse 2s infinite}}
.hero-live-text{{font-size:12px;color:#22c55e;font-weight:600}}
.hero-live-time{{font-size:11px;color:#94a3b8}}
.hero-price-row{{display:flex;align-items:center;gap:12px}}
.hero-price{{font-family:'Noto Sans KR',sans-serif;font-size:32px;font-weight:900;
  color:#06101d;line-height:1;white-space:nowrap;letter-spacing:-1px;transition:color .18s ease,text-shadow .18s ease,transform .18s ease}}
.hero-price.price-boosting{{color:#ef4444;text-shadow:0 0 18px rgba(239,68,68,.32);transform:translateY(-1px)}}
.hero-price-krw{{font-size:13px;font-weight:700;color:#64748b;line-height:1.1;white-space:nowrap}}
.hero-pct-wrap{{display:flex;flex-direction:column;gap:2px;margin-top:2px}}
.hero-pct{{font-size:14px;font-weight:700;line-height:1.2;white-space:nowrap}}
.hero-pct-sub{{font-size:10px;color:#94a3b8;white-space:nowrap}}
.hero-sparkline{{height:72px;position:relative;margin:0}}
.hero-sparkline canvas{{width:100%!important;height:100%!important}}
.hero-time-axis{{display:flex;justify-content:space-between;
  font-size:9px;color:#94a3b8;margin-top:3px;padding:0 1px}}
.hero-metrics{{display:grid;grid-template-columns:1fr 1fr;
  border-top:1px solid #f0f4f8;padding-top:12px;margin-top:2px}}
.hero-metric{{padding:0 6px 0 0}}
.hero-metric+.hero-metric{{padding:0 0 0 16px;border-left:1px solid #e5e7eb}}
.hm-header{{display:flex;align-items:center;gap:7px;margin-bottom:5px}}
.hm-icon-wrap{{width:24px;height:24px;border-radius:6px;
  display:flex;align-items:center;justify-content:center;font-size:12px}}
.hm-label{{font-size:11px;color:#64748b;font-weight:500;white-space:nowrap}}
.hm-row{{display:flex;align-items:baseline;gap:6px}}
.hm-value{{font-family:'Noto Sans KR',sans-serif;font-size:16px;font-weight:900;
  color:#06101d;white-space:nowrap}}
.hm-pct{{font-size:12px;font-weight:700;white-space:nowrap}}
</style>
</head>
<body>
<div class="wrap">

  <!-- PRO_RIPPLER Hero -->
  <div class="pro-nav">
    <div class="pro-logo-wrap">
      <img class="pro-logo-img" src="data:image/png;base64,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l8CUzasAYMoWTLgECBAgQIAAAQIECBAgMBkCoiBAYEgCvbnuqn/24Nkp8suHNINhCRAgQIAAAQIECAxToB2Rz26t3vay6PWqYU5k7NEITNss/tJN24qJlwABAgQIECBAgAABAgQmQUAMBAgMQ2DTXGs21r6wH/mdOdLGYUxhTAIECBAgQIAAAQIjEDigP9+/Jr5/8FNGMJcphiswdaMrAJi6JRMwAQIECBAgQIAAAQIECIxfQAQECAxDYPb41U8sN/7PTZGOG8b4xiRAgAABAgQIECAwKoEUcUrqpw/G5q0bRjWneYYhMH1jKgCYvjUTMQECBAgQIECAAAECBAiMW8D8BAgMXuAT31sTUb095Vh46//W4CdYzohpORe5hgABAgQIECBAgMDDAuWryddW/epCvwrgYY7p/DCFUSsAmMJFEzIBAgQIECBAgAABAgQIjFfA7AQIDF5g5sf5RZHTuZFizeBHNyIBAgQIECBAgACBUQiUW/6PnqYTkc9sff/g1zz6sGfTIjCNcSoAmMZVEzMBAgQIECBAgAABAgQIjFPA3AQIDFrg0nvWpchfKDf/J+ztUfOgMzUeAQIECBAgQIBArQV2+fXjQf1+uizO/MKRtU69nslNZVYKAKZy2QRNgAABAgQIECBAgAABAuMTMDMBAgMV6N27enbVzOfKmBP4gujjfoKrhKkRIECAAAECBAgQ2J3Arr9+LEefUc23zom3X79ud1c6PokC0xmTAoDpXDdREyBAgAABAgQIECBAgMC4BMxLgMDgBObmWrP99psi5TcOblAjESBAgAABAgQIEBiXwC7fAWAhmFXRj9e1qv4rYvPWzsIB+xQITGmICgCmdOGETYAAAQIECBAgQIAAAQLjETArAQKDE1j1b9aekqs4L1LyIujgWI1EgAABAgQIECAwiQIpjoycz45teQLf+SpsuxCY1kMKAKZ15cRNgAABAgQIECBAgAABAuMQMCcBAgMSWNP7zhNyxFkp4mnlhdDyaUADG4YAAQIECBAgQIDA2AT2/GVtTunUqlWdGb3722ML0cSLFZjafgoApnbpBE6AAAECBAgQIECAAAECoxcwIwECAxHYvLWzI6XTc1SvKeN1y64RIECAAAECBAgQqIFA3ksOuRspzmz9x//jV/bS0emxC0xvAAoApnftRE6AAAECBAgQIECAAAECoxYwHwEC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dTPfHgQUAOwBxykCBAgQIECAAAECBAgQmCYBsRKov8D6T3133xz5FfXPVIYECBAgQIAAAQIECEy4QDui//xYf9jBo4/TjHsSUACwJx3nCBAgQIAAAQIECBAgQGB6BERKoAECD/4ovTxS2q8BqUqRAAECBAgQIECAwBQK5CmMefkhp0jPiTz/pDJCKvvompn2KKAAYI88ThIgQIAAAQIECBAgQIDAtAiIk0DtBbbcN1OleFnJc33ZNQIECBAgQIAAAQIECIxb4AmR+y+IM3ozowzEXHsWUACwZx9nCRAgQIAAAQIECBAgQGA6BERJoPYC3QOqJ0eOE0uinbJrBAgQIECAAAECBAgQGLtASunV0Tps9QgDMdVeBBQA7AXIaQIECBAgQIAAAQIECBCYBgExEqi/QJXjOSXLhbfXLJ80AgQIECBAgAABAgQmT6CB74Sf4qTIDx0XI9tMtDcBBQB7E3KeAAECBAgQIECAAAECBCZfQIQE6i5w2R9tyCk9u6S5f9k1AgQIECBAgAABAgQmUiBPZFRDDSrHTBWtNw51jp0H93ivAgoA9kqkAwECBAgQIECAAAECBAhMuoD4CNRdoLs+PTEt/GRNRAN/pChsBAgQIECAAAECBAhMsECOeF1smuuOIkRz7F1AAcDejfQgQIAAAQIECBAgQIAAgckWEB2Begv0elWrv/3JKcdx9U5UdgQIECBAgAABAgQITKnAQbHmBy8ZQeymWISAAoBFIOlCgAABAgQIECBAgAABApMsIDYCdRd4yeqcq1NyxMawESBAgAABAgQIECBAYAIFqireNPywzLAYAQUAi1HShwABAgQIECBAgAABAgQmV0BkBGousCoe2Bg5Xho2AgQIECBAgAABAgQITKhAzvFL8Tuf22+o4Rl8UQIKABbFpBMBAgQIECBAgAABAgQITKqAuAjUX6B1RKQ4KWwECBAgQIAAAQIECBCYVIGU9otu+4XDDM/YixNQALA4J70IECBAgAABAgQIECBAYDIFREWg9gK5il8rSc6WXSNAgAABAgQIECBAgMCECuSZqh+/OsTgDL1IAQUAi4TSjQABAgQIECBAgAABAgQmUUBMBGousGmulSJeXfMspUeAAAECBAgQIECAwPQLtHPOp8TmrQcPJxWjLlZAAcBipfQjQIAAAQIECBAgQIAAgckTEBGBmgusPX7DsTny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AAEE0iJAnAgggAACyRXwoppZADDW+eEN6VjFaI8AAggggAAC+RAgSwQQQAABBBBAYBwCXig0ucQnAIzDjlMQQAABBBBoiACDIoAAAggkV8DCe6vygIltTAIsABgTF40RQAABBBBAIC8C5IkAAggggAACCIxHwF1FybneMh48zkEAAQQQQKABAgyJAAIIIJBkAS9oaJAFAGOcIt6QjhGM5ggggAACCCCQCwGSRAABBBBAAAEExicQR00RvwJgfHachQACCCCAQP0FGBEBBBBAIMkCbkVNmiS2sQlEY2tOawQQQAABBBBAIA8C5IgAAggggAACCIxPwK3c5C5+BcD4+DgLAQQQQACBOgswHAIIIIBAogUsvLcq8wkAGuPGAoAxgtEcAQQQQAABBHIgQIoIIIAAAggg8P/Z+w9wS6/yQND91j5VkgC73W57pt097r5z587cDtM9c++05+nu6X76tnpsAwIhkMQhKCEEKqIINgZsAxuUAygUChRJRuQyJtrYYIwAISRABCGBJCSEJJRjqdI5O/zrriPAShVO2OH///3uWqt2WuH73lUqndr7O/sQWLXA+nVlqtdbCoJGgAABAgQIECBAgACBNQks/Yi14ZwfAbBCxBX+g3SFqxtOgAABAgQIECBAgAABAgQINFBAyKsVmKvyXKTkBarVAppHgAABAgQIECBAgACBhwXWxXDg31cPeyzr1soKAJa1pEEECBAgQIAAAQIECBAgQIBAowUEv3qBTnnzP2cvUK1e0EwCBAgQIECAAAECBAj8UmAu9t0vXFYmsKICgJUtbTQBAgQIECBAgAABAgQIECDQRAExr14gR9WJVH6tfgkzCRAgQIAAAQIECBAgQGBJIMdcVP20dFNfvkBn+UPDUAIECBAgQIAAAQIECBAgQKD9AjJci0CVvDi1Fj9zCRAgQIAAAQIECBAg8EuBFOtiOOffWL/0WOb1CgoAlrmiYQQIECBAgAABAgQIECBAgECDBYS+JoE5nwCwJj+TCRAgQIAAAQIECBAg8LDAXKwbpIfvurUcgeUXACxnNWMIECBAgAABAgQIECBAgACBZguIfm0COaXIfgTA2hDNJkCAAAECBAgQIECAwEMCcw/97rcVCSy7AGBFqxpMgAABAgQIECBAgAABAgQINFJA0GsVyOW1Ft+gslZF8wkQIECAAAECBAgQIFAE/AiA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BAgQIECAAAECBNosILfJCywszt1Wdh2UrhEgQIAAAQIECBAgQIDAygS2xTDuX9kUo5cElroCgCUFnQABAgQIECBAgAABAgQItFdAZtMQ6O6/EJF8CkC4ECBAgAABAgQIECBAYIUCObbHnAKAFaotDX+oKwB4iMFvBAgQIECAAAECBAgQIECgrQLymp5A/un09rYzAQIECBAgQIAAAQIEGiqQYlssKABY+en9fIYCgJ87+J0AAQIECBAgQIAAAQIECLRTQFZTE8iRFABMTd/GBAgQIECAAAECBAg0VCCnSFuj/5sPNjT+6YX9i50VAPwCwhUBAgQIECBAgAABAgQIEGijgJymKJCHN01xd1sTIECAAAECBAgQIECgiQKDiHx3bJ4fNjH4acb8y70VAPxSwjUBAgQIECBAgAABAgQIEGifgIymKTDXuXGa29ubAAECBAgQIECAAAECzRPIvYh8Z/PinnrEfx+AAoC/p3CDAAECBAgQIECAAAECBAi0TUA+UxWoOn4EwFQPwOYECBAgQIAAAQIECDROIKVeykkBwIoP7uEJnYdvukWAAAECBAgQIECAAAECBAi0SkAyUxXIUS39CIA81SBsToAAAQIECBAgQIAAgSYJ5NQbZp8AsOIje8QEBQCPwHCTAAECBAgQIECAAAECBAi0SUAu0xXYZ65zX0TaFi4ECBAgQIAAAQIECMyIQJqRPMeZZu5HZ84nAKyQ+JHDFQA8UsNtAgQIECBAgAABAgQIECDQHgGZTFlg65Y8iMh3TDkM2xMgQIAAAQIECBAgQKBJAr3IlQKAlZ3Yo0YrAHgUhzsECBAgQIAAAQIECBAgQKAtAvKYusAT1g0jx21Tj0MABAgQIECAAAECBAgQaIxA6sU+nbsaE24tAn10EAoAHu3hHgECBAgQIECAAAECBAgQaIeALGogsK2KpACgBgchBAIECBAgQIAAAQIEmiKQ8r2xacOOpoRbizgfE4QCgMeAuEuAAAECBAgQIECAAAECBNogIIcaCPyjuWFExycA1OAohECAAAECBAgQIECAQDMEUs4/a0ak9YnysZEoAHisiPsECBAgQIAAAQIECBAgQKD5AjKog8BVt1SRvHhVh6MQAwECBAgQIECAAAECTRFINzUl0prE+bgwFAA8jsQDBAgQIECAAAECBAgQIECg6QLir4XAP719mHL101rE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" alt="Ripple logo">
      <div>
        <div class="pro-logo-text">PRO_RIPPLER</div>
        <div class="pro-logo-sub">XRP 프로리플러 커뮤니티 플랫폼</div>
      </div>
    </div>
  </div>
  <div class="pro-hero">
    <div class="hero-left">
      <div class="hero-title">XRP의 가치를 믿는<br>장기 홀더들의 공간</div>
      <div class="hero-desc">함께 배우고, 예측하고, 인사이트를 공유하며<br>더 나은 미래를 만들어 갑니다.</div>
      <button class="hero-btn">오늘도 존버하기</button>
    </div>
    <div class="hero-right">
      <div class="hero-card">
        <div class="hero-price-header">
        <div style="display:flex;align-items:center;gap:10px">
          <span class="hero-pair">XRP / USD</span>
          <div class="hero-live-area">
            <span class="hero-live-dot"></span>
            <span class="hero-live-text">실시간</span>
          </div>
        </div>
        <span class="hero-live-time" id="hero-updated">갱신 중...</span>
      </div>
      <div class="hero-price-row">
        <div style="display:flex;flex-direction:column;gap:4px">
          <span class="hero-price" id="hero-price">${price_usd:,.4f}</span>
        </div>
        <div class="hero-pct-wrap">
          <span class="hero-pct" id="hero-pct" style="color:{pct_color(info.get('price_change_24h'))}">{'▲' if (info.get('price_change_24h') or 0) >= 0 else '▼'} {fmt_pct(info.get('price_change_24h'))}</span>
          <span class="hero-pct-sub">24h 기준</span>
        </div>
      </div>
      <div class="hero-sparkline">
        <canvas id="sparkChart"></canvas>
      </div>
      <div class="hero-time-axis">
        <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
      </div>
      <div class="hero-metrics">
        <div class="hero-metric">
          <div class="hm-header">
            <div class="hm-icon-wrap" style="background:#fff7ed">⚡</div>
            <span class="hm-label">XRP Ledger TPS</span>
          </div>
          <div class="hm-row">
            <span class="hm-value" id="hero-tps">{fmt_tps_display(xrpl_stats)}</span>
            <span class="hm-pct" style="color:#22c55e" id="hero-tps-sub">{xrpl_stats.get('status_label','TPS')}</span>
          </div>
        </div>
        <div class="hero-metric">
          <div class="hm-header">
            <div class="hm-icon-wrap" style="background:#eff6ff">🗄️</div>
            <span class="hm-label">XRP 시가총액</span>
          </div>
          <div class="hm-row">
            <span class="hm-value" id="hero-mcap">{fmt_large(info.get('market_cap_usd',0))}</span>
            <span class="hm-pct" id="hero-mcap-pct" style="color:{pct_color(info.get('price_change_24h'))}">{fmt_pct(info.get('price_change_24h'))}</span>
          </div>
        </div>
      </div>
      </div>
    </div>
  </div>
  <p class="st">현재 시장 지표
    <span class="rt-badge"><span class="dot"></span>실시간 · <span id="last-updated">갱신 중...</span></span>
  </p>
  <div class="g4">
    <div class="card">
      <div class="cl">현재가 (USD)</div>
      <div class="cv" id="price-usd"><span class="cur">$</span><span class="num">{price_usd:,.4f}</span></div>
      <div class="cs" id="pct-24h" style="color:{pct_color(info.get('price_change_24h'))}">24h {fmt_pct(info.get('price_change_24h'))}</div>
    </div>
    <div class="card">
      <div class="cl">현재가 (KRW)</div>
      <div class="cv" id="price-krw"><span class="cur">₩</span><span class="num">{info.get('price_krw',0):,.0f}</span></div>
      <div class="cs" id="pct-7d" style="color:{pct_color(info.get('price_change_7d'))}">7d {fmt_pct(info.get('price_change_7d'))}</div>
    </div>
    <div class="card">
      <div class="cl">시가총액</div>
      <div class="cv" id="market-cap">{fmt_krw_large_html(market_cap_krw)}</div>
      <div class="cs">{fmt_large(info.get('market_cap_usd',0))} · 순위 #{info.get('market_cap_rank','—')}</div>
    </div>
    <div class="card">
      <div class="cl">24h 거래량</div>
      <div class="cv" id="volume-24h">{fmt_krw_large_html(volume_24h_krw)}</div>
      <div class="cs">{fmt_large(info.get('volume_24h',0))} · CMC KRW 환산</div>
    </div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="cl">ATH 대비 현재가</div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="cv">${ath_usd:,.4f} <span style="font-size:13px;color:var(--muted)">ATH</span></div>
        <div style="color:var(--muted);font-size:12px">{ath_pct:.1f}%</div>
      </div>
      <div class="bar6"><div class="bar6-fill" style="width:{min(ath_pct,100):.1f}%;background:var(--green)"></div></div>
      <div class="cs" style="margin-top:6px">ATH 대비 {ath_pct:.1f}% / 회복까지 {100-ath_pct:.1f}% 남음</div>
    </div>
    <div class="card">
      <div class="cl">유통 / 총 공급량</div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="cv">{circ/1e9:.1f}B XRP</div>
        <div style="color:var(--muted);font-size:12px">{supply_pct:.1f}%</div>
      </div>
      <div class="bar"><div class="bar-fill" style="width:{supply_pct:.1f}%;background:linear-gradient(90deg,var(--accent),var(--accent2))"></div></div>
      <div class="cs" style="margin-top:6px">총 {total/1e9:.0f}B XRP 중 유통 {supply_pct:.1f}%</div>
    </div>
  </div>

  <!-- ② 뉴스 -->
  <div class="news-box">
    <div class="news-hdr">
      <button class="tab-btn active">📰 국내 XRP / 리플 최신 뉴스</button>
      <span class="news-meta"><span class="dot"></span><span id="news-updated">최신순 · 갱신 중...</span></span>
    </div>
    <div id="gen-list">{gen_html}</div>
  </div>

  <!-- ③ 입법/규제 트래커 -->
  <p class="st">입법 / 규제 트래커</p>
  <div class="reg-grid">
    <div class="reg-card">
      <div class="reg-card-hdr">
        <span class="reg-title">CLARITY Act</span>
        <span class="status-badge" style="background:#f59e0b20;color:#f59e0b;border:1px solid #f59e0b40">상원 진행 중</span>
      </div>
      <div class="reg-body">
        <p class="reg-desc">디지털 자산 증권/상품 분류 기준 명확화 법안. 하원 통과 후 상원 심의 중. XRP 법적 지위에 직접 영향.</p>
        <div id="clarity-list">{clarity_html}</div>
      </div>
    </div>
    <div class="reg-card">
      <div class="reg-card-hdr">
        <span class="reg-title">GENIUS Act</span>
        <span class="status-badge" style="background:#10b98120;color:#10b981;border:1px solid #10b98140">상원 통과</span>
      </div>
      <div class="reg-body">
        <p class="reg-desc">스테이블코인 발행 규제 프레임워크 법안. RLUSD 규제 적합성에 직접 영향. 하원 심의 중.</p>
        <div id="genius-list">{genius_html}</div>
      </div>
    </div>
    <div class="reg-card">
      <div class="reg-card-hdr">
        <span class="reg-title">SEC / CFTC 동향</span>
        <span class="status-badge" style="background:#10b98120;color:#10b981;border:1px solid #10b98140">XRP 상품 확인</span>
      </div>
      <div class="reg-body">
        <p class="reg-desc">SEC 2026년 가이던스에서 XRP를 디지털 상품으로 재확인. 소송 종결 후 제도권 편입 가속화 국면.</p>
        <div id="sec-list">{sec_html}</div>
      </div>
    </div>
  </div>

  <!-- ④ 기관 자금 흐름 -->
  <p class="st">기관 자금 흐름</p>
  <div class="inst-grid">
    <div class="inst-card">
      <div class="ic-label">RLUSD 시가총액</div>
      <div class="ic-value" style="color:var(--accent)">{fmt_krw_large(rlusd_mcap_krw) if rlusd_mcap_krw else "수집 중"}</div>
      <div class="ic-sub">{fmt_large(rlusd_mcap) if rlusd_mcap else "—"} · CMC KRW 환산</div>
      <div class="ic-mini"><span>상태</span><b>모니터링</b></div>
    </div>
    <div class="inst-card">
      <div class="ic-label">XRPL 네트워크</div>
      <div class="ic-value" style="color:var(--green)">{xrpl_stats.get('tps_24h_avg',0):,.2f} TPS</div>
      <div class="ic-sub">24h TX {xrpl_stats.get('tx_today',0):,}건 · 7일 평균 {xrpl_stats.get('tx_7d_avg',0):,}건</div>
      <div class="ic-mini"><span>Ledger #{xrpl_stats.get('ledger_seq',0):,}</span><b>Close {xrpl_stats.get('ledger_close_sec',0):.2f}s</b></div>
    </div>
    <div class="inst-card">
      <div class="ic-label">XRP 현물 ETF 순유입</div>
      <div class="ic-value" style="color:var(--green)" id="etf-daily-inflow">{etf_daily_text}</div>
      <div class="ic-sub">일일 순유입</div>
      <div class="ic-sub">누적 순유입 <b id="etf-total-inflow" style="color:var(--text)">{etf_total_text}</b></div>
      <div class="ic-mini"><span>{etf_status_text}</span><b id="etf-flow-source">{etf_source_text}</b></div>
    </div>
  </div>
  <div class="etf-box">
    <div class="etf-hdr">기관 / ETF 관련 최신 동향</div>
    <div id="etf-list">{etf_html}</div>
  </div>

  <div class="disc">
    <strong style="color:var(--yellow)">⚠ 면책 고지</strong><br>
    본 리포트는 기술적 지표 기반 자동 분석 자료로, 투자 권유가 아닙니다. 입법/규제 정보는 공개 뉴스 기반이며 법적 효력이 없습니다. ETF 유입자금은 SoSoValue 상단 요약 카드값을 우선 사용하며, 접속 실패 시 캐시/뉴스 파싱값으로 대체됩니다. 암호화폐 투자는 원금 손실 위험이 있으며, 모든 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.
  </div>
</div>

<script>
function switchTab(id,btn){{
  document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
}}

// 히어로 스파크라인
const sparkCtx = document.getElementById('sparkChart');
if(sparkCtx) {{
  new Chart(sparkCtx, {{
    type:'line',
    data:{{
      labels: {json.dumps(labels[-24:])},
      datasets:[{{
        data: {json.dumps(prices_c[-24:])},
        borderColor:'#3b82f6',borderWidth:2,
        backgroundColor:'rgba(59,130,246,0.08)',
        fill:true,tension:0.4
      }}]
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{display:false}},tooltip:{{enabled:false}}}},
      scales:{{x:{{display:false}},y:{{display:false}}}},
      elements:{{point:{{radius:0}}}}
    }}
  }});
}}

// 가격/시총/거래량/24h/7d는 브라우저에서 CoinGecko API로 30초마다 갱신합니다.
// API 실패 시에는 Python이 생성한 기존 값을 그대로 유지합니다.
let liveHeroPriceUsd = Number({price_usd:.8f} || 0);
let priceBoostRunning = false;
function fL(v){{return v>=1e9?'$'+(v/1e9).toFixed(2)+'B':v>=1e6?'$'+(v/1e6).toFixed(2)+'M':'$'+Number(v||0).toFixed(2)}}
function fP(v){{v=Number(v||0);return(v>=0?'+':'')+v.toFixed(2)+'%'}}
function pC(v){{return Number(v||0)>=0?'#10b981':'#ef4444'}}
function fKrwLarge(v){{
  v=Number(v||0);
  if(!v)return '<span class="num">—</span>';
  const jo=Math.floor(v/1000000000000);
  let eok=Math.round((v-jo*1000000000000)/100000000);
  let j=jo;
  if(eok>=10000){{j+=1;eok-=10000;}}
  let body='';
  if(j>0) body=j+'조 '+(eok?eok.toLocaleString('ko-KR')+'억':'');
  else if(v>=100000000) body=Math.round(v/100000000).toLocaleString('ko-KR')+'억';
  else if(v>=10000) body=Math.round(v/10000).toLocaleString('ko-KR')+'만';
  else body=Math.round(v).toLocaleString('ko-KR');
  return '<span class="cur">₩</span><span class="num">'+body.trim()+'</span>';
}}
function setMoneyHTML(id, symbol, value, decimals){{
  const el=document.getElementById(id);
  if(!el || value===undefined || value===null || Number.isNaN(Number(value)))return;
  el.innerHTML='<span class="cur">'+symbol+'</span><span class="num">'+Number(value).toLocaleString('ko-KR',{{minimumFractionDigits:decimals,maximumFractionDigits:decimals}})+'</span>';
}}
function setText(id, text){{const el=document.getElementById(id);if(el)el.textContent=text;}}
function setHtml(id, html){{const el=document.getElementById(id);if(el)el.innerHTML=html;}}
function setPct(id, label, value){{
  const el=document.getElementById(id);
  if(!el || value===undefined || value===null || Number.isNaN(Number(value)))return;
  el.textContent=label+' '+fP(value);
  el.style.color=pC(value);
}}
async function updatePrice(){{
  const now=new Date();
  const hhmm=now.getHours().toString().padStart(2,'0')+':'+now.getMinutes().toString().padStart(2,'0');
  try{{
    const r=await fetch('https://api.coingecko.com/api/v3/coins/ripple?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false',{{cache:'no-store'}});
    if(!r.ok)throw new Error('CoinGecko '+r.status);
    const data=await r.json();
    const md=data.market_data||{{}};
    const price=md.current_price||{{}};
    const mcap=md.market_cap||{{}};
    const vol=md.total_volume||{{}};
    const pct24=md.price_change_percentage_24h;
    const pct7=md.price_change_percentage_7d;

    setMoneyHTML('price-usd','$',price.usd,4);
    setMoneyHTML('price-krw','₩',price.krw,0);
    setHtml('market-cap',fKrwLarge(mcap.krw));
    setHtml('volume-24h',fKrwLarge(vol.krw));
    setPct('pct-24h','24h',pct24);
    setPct('pct-7d','7d',pct7);

    liveHeroPriceUsd = Number(price.usd || liveHeroPriceUsd || 0);
    if(!priceBoostRunning){{
      setText('hero-price','$'+liveHeroPriceUsd.toLocaleString('en-US',{{minimumFractionDigits:4,maximumFractionDigits:4}}));
    }}
    const heroPct=document.getElementById('hero-pct');
    if(heroPct && pct24!==undefined && pct24!==null){{
      heroPct.textContent=(Number(pct24)>=0?'▲ ':'▼ ')+fP(pct24);
      heroPct.style.color=pC(pct24);
    }}
    setText('hero-mcap',fL(mcap.usd||0));
    const hm=document.getElementById('hero-mcap-pct');
    if(hm && pct24!==undefined && pct24!==null){{hm.textContent=fP(pct24);hm.style.color=pC(pct24);}}

    setText('last-updated',hhmm+' 실시간 가격');
    setText('hero-updated',hhmm);
  }}catch(e){{
    console.warn('가격 갱신 실패:',e);
    setText('last-updated',hhmm+' 가격 갱신 대기');
    setText('hero-updated',hhmm);
  }}
}}
updatePrice();
setInterval(updatePrice,30000);

// 국내 XRP / 리플 최신 뉴스 갱신 (5분)
const PROXY=url=>`https://api.allorigins.win/get?url=${{encodeURIComponent(url)}}`;
const RSS_GEN_LIST=[
  'https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=XRP+ETF+%EB%A6%AC%ED%94%8C&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+SEC+XRP&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=RLUSD+%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko'
];
const NEWS_PRIORITY_SOURCES=['연합뉴스','뉴스1','블로터','디지털애셋','매일경제','한국경제','이데일리','조선비즈','서울경제','코인데스크','토큰포스트'];
const NEWS_PRIORITY_TERMS=['ETF','SEC','리플','XRP','RLUSD','송금','기관','은행','업비트','빗썸','현물'];
const NEWS_BLOCK_TERMS=['prediction','forecast','price analysis','2030','2040','$50','$100','hit this price','crash','beyond'];

function timeAgo(d){{
  const s=(Date.now()-new Date(d).getTime())/1000;
  if(s<60)return '방금';if(s<3600)return Math.floor(s/60)+'분 전';
  if(s<86400)return Math.floor(s/3600)+'시간 전';return Math.floor(s/86400)+'일 전';
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
  const now=Date.now();
  items.sort((a,b)=>new Date(b.date)-new Date(a.date));
  el.innerHTML=items.slice(0,10).map((n,i)=>{{
    const ageSec=(now-new Date(n.date).getTime())/1000;
    const isHot=ageSec>=0 && ageSec<=1800;
    const isOld=ageSec>7200;
    const tagText=i===0?'🔴 최신':(isHot?'HOT':'#'+(i+1));
    return `<a class="ni${{isOld?' old-news':''}}" href="${{n.url}}" target="_blank" rel="noopener">
      <span class="ntag${{i===0?' latest':(isHot?' hot':'')}}">${{tagText}}</span>
      <span class="nt">${{n.title}}</span>
      <span class="nsrc">${{n.source||'Google News KR'}}${{n.date?' · '+timeAgo(n.date):''}}</span>
    </a>`;
  }}).join('');
}}

function scoreKoreanNews(n){{
  const text=((n.title||'')+' '+(n.source||'')).toLowerCase();
  if(NEWS_BLOCK_TERMS.some(t=>text.includes(t.toLowerCase()))) return -999;
  let score=0;
  if(NEWS_PRIORITY_SOURCES.some(src=>(n.source||'').includes(src))) score+=5;
  NEWS_PRIORITY_TERMS.forEach(t=>{{ if(text.includes(t.toLowerCase())) score+=1; }});
  return score;
}}

async function fetchNewsList(rssUrls,listId){{
  const merged=[];
  const seen=new Set();
  for(const rssUrl of rssUrls){{
    try{{
      const r=await fetch(PROXY(rssUrl));
      if(!r.ok) continue;
      const xml=(await r.json()).contents;
      if(!xml) continue;
      parseRSS(xml).forEach(n=>{{
        const key=(n.title||'').replace(/\s+/g,' ').trim().toLowerCase();
        if(!key || seen.has(key)) return;
        const score=scoreKoreanNews(n);
        if(score<0) return;
        n.score=score;
        seen.add(key);
        merged.push(n);
      }});
    }}catch(e){{}}
  }}
  // 최신 날짜순 정렬을 최우선으로 적용합니다.
  merged.sort((a,b)=>{{
    const dt=new Date(b.date)-new Date(a.date);
    if(dt!==0) return dt;
    return (b.score||0)-(a.score||0);
  }});
  if(merged.length) renderNews(merged,listId);
}}

async function updateNews(){{
  await fetchNewsList(RSS_GEN_LIST,'gen-list');
  const n=new Date();
  document.getElementById('news-updated').textContent=
    '국내 최신순 · '+n.getHours().toString().padStart(2,'0')+':'+n.getMinutes().toString().padStart(2,'0')+' 갱신';
}}


// 입법 / 규제 트래커도 국내 기사 기준으로 5분마다 갱신
const RSS_CLARITY_LIST=[
  'https://news.google.com/rss/search?q=CLARITY+Act+%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=%EB%94%94%EC%A7%80%ED%84%B8%EC%9E%90%EC%82%B0+%EC%8B%9C%EC%9E%A5%EA%B5%AC%EC%A1%B0%EB%B2%95+XRP&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=%EB%AF%B8%EA%B5%AD+%EA%B0%80%EC%83%81%EC%9E%90%EC%82%B0+CLARITY+Act&hl=ko&gl=KR&ceid=KR:ko'
];
const RSS_GENIUS_LIST=[
  'https://news.google.com/rss/search?q=GENIUS+Act+%EC%8A%A4%ED%85%8C%EC%9D%B4%EB%B8%94%EC%BD%94%EC%9D%B8+%EB%A6%AC%ED%94%8C+RLUSD&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=%EB%AF%B8%EA%B5%AD+%EC%8A%A4%ED%85%8C%EC%9D%B4%EB%B8%94%EC%BD%94%EC%9D%B8+%EB%B2%95%EC%95%88+RLUSD&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=%EC%8A%A4%ED%85%8C%EC%9D%B4%EB%B8%94%EC%BD%94%EC%9D%B8+%EA%B7%9C%EC%A0%9C+GENIUS+Act&hl=ko&gl=KR&ceid=KR:ko'
];
const RSS_SEC_LIST=[
  'https://news.google.com/rss/search?q=SEC+CFTC+%EB%A6%AC%ED%94%8C+XRP&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+SEC+%EC%86%8C%EC%86%A1+XRP&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=XRP+ETF+SEC+%EB%A6%AC%ED%94%8C&hl=ko&gl=KR&ceid=KR:ko'
];

function renderRegNews(items,listId){{
  const el=document.getElementById(listId);if(!el)return;
  items.sort((a,b)=>new Date(b.date)-new Date(a.date));
  el.innerHTML=items.slice(0,4).map(n=>
    `<a class="reg-ni" href="${{n.url}}" target="_blank" rel="noopener">
      <span class="rni-dot"></span>
      <span class="rni-content">
        <span class="rni-title">${{n.title}}</span>
        <span class="rni-src">${{n.source||'Google News KR'}}${{n.date?' · '+timeAgo(n.date):''}}</span>
      </span>
    </a>`
  ).join('');
}}

async function fetchRegNewsList(rssUrls,listId){{
  const merged=[];
  const seen=new Set();
  for(const rssUrl of rssUrls){{
    try{{
      const r=await fetch(PROXY(rssUrl));
      if(!r.ok) continue;
      const xml=(await r.json()).contents;
      if(!xml) continue;
      parseRSS(xml).forEach(n=>{{
        const key=(n.title||'').replace(/\s+/g,' ').trim().toLowerCase();
        if(!key || seen.has(key)) return;
        const score=scoreKoreanNews(n);
        if(score<0) return;
        n.score=score;
        seen.add(key);
        merged.push(n);
      }});
    }}catch(e){{}}
  }}
  merged.sort((a,b)=>{{
    const dt=new Date(b.date)-new Date(a.date);
    if(dt!==0) return dt;
    return (b.score||0)-(a.score||0);
  }});
  if(merged.length) renderRegNews(merged,listId);
}}

async function updateRegNews(){{
  await Promise.all([
    fetchRegNewsList(RSS_CLARITY_LIST,'clarity-list'),
    fetchRegNewsList(RSS_GENIUS_LIST,'genius-list'),
    fetchRegNewsList(RSS_SEC_LIST,'sec-list')
  ]);
}}

// 기관 / ETF 관련 최신 동향도 국내 기사 우선, 부족하면 해외 기사를 한국어 요약 제목으로 표시
const RSS_ETF_LIST=[
  'https://news.google.com/rss/search?q=XRP+ETF+%EB%A6%AC%ED%94%8C&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=%EB%A6%AC%ED%94%8C+%ED%98%84%EB%AC%BC+ETF&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=XRP+%ED%98%84%EB%AC%BC+ETF+SEC&hl=ko&gl=KR&ceid=KR:ko',
  'https://news.google.com/rss/search?q=XRP+ETF+%EC%88%9C%EC%9C%A0%EC%9E%85&hl=ko&gl=KR&ceid=KR:ko'
];
const RSS_ETF_OVERSEAS='https://news.google.com/rss/search?q=XRP+spot+ETF+inflow+AUM+institutional&hl=en&gl=US&ceid=US:en';

function hasKoreanText(t){{ return /[가-힣]/.test(t||''); }}
function translateEtfTitleKo(title){{
  const t=title||'';
  if(hasKoreanText(t)) return t;
  const low=t.toLowerCase();
  const money=(t.match(/\$\s*[0-9]+(?:\.[0-9]+)?\s*[MB]/i)||[''])[0];
  if(low.includes('outflow')) return money ? 'XRP 현물 ETF, 자금 유출 '+money+' 기록' : 'XRP 현물 ETF, 자금 유출 흐름 발생';
  if(low.includes('inflow')) return money ? 'XRP 현물 ETF, 순유입 '+money+' 기록' : 'XRP 현물 ETF, 자금 유입 흐름 지속';
  if(low.includes('aum')||low.includes('assets under management')) return 'XRP 현물 ETF, 운용자산 규모 변동';
  if(low.includes('institutional')) return 'XRP ETF, 기관 수요 관련 동향';
  if(low.includes('sec')&&low.includes('etf')) return 'SEC의 XRP ETF 심사 관련 동향';
  if(low.includes('approved')||low.includes('approval')) return 'XRP 현물 ETF 승인 관련 소식';
  if(low.includes('xrp etf')||low.includes('xrp spot etf')) return 'XRP 현물 ETF 관련 최신 동향';
  return t;
}}

async function updateEtfNews(){{
  const domestic=[];
  const seen=new Set();
  for(const rssUrl of RSS_ETF_LIST){{
    try{{
      const r=await fetch(PROXY(rssUrl));
      if(!r.ok) continue;
      const xml=(await r.json()).contents;
      if(!xml) continue;
      parseRSS(xml).forEach(n=>{{
        const key=(n.title||'').replace(/\s+/g,' ').trim().toLowerCase();
        if(!key || seen.has(key)) return;
        const score=scoreKoreanNews(n);
        if(score<0) return;
        n.score=score;
        seen.add(key);
        domestic.push(n);
      }});
    }}catch(e){{}}
  }}
  domestic.sort((a,b)=>new Date(b.date)-new Date(a.date));

  const merged=domestic.slice(0,6);
  if(merged.length<4){{
    try{{
      const r=await fetch(PROXY(RSS_ETF_OVERSEAS));
      if(r.ok){{
        const xml=(await r.json()).contents;
        parseRSS(xml).forEach(n=>{{
          if(merged.length>=6) return;
          const key=(n.title||'').replace(/\s+/g,' ').trim().toLowerCase();
          if(!key || seen.has(key)) return;
          n.title=translateEtfTitleKo(n.title);
          n.source=(n.source||'해외 뉴스')+' · 번역요약';
          seen.add(key);
          merged.push(n);
        }});
      }}
    }}catch(e){{}}
  }}
  merged.sort((a,b)=>new Date(b.date)-new Date(a.date));
  if(merged.length) renderRegNews(merged,'etf-list');
}}


// GitHub Pages용 정적 JSON 갱신 데이터. GitHub Actions가 5분마다 data/live_data.json을 새로 생성합니다.
function setText(id,value){{ const el=document.getElementById(id); if(el) el.textContent=value; }}
function fmtUsd(v){{ return Number(v||0).toLocaleString('en-US',{{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:4}}); }}
function fmtLargeUsd(v){{
  v=Number(v||0);
  if(v>=1e9) return '$'+(v/1e9).toFixed(2)+'B';
  if(v>=1e6) return '$'+(v/1e6).toFixed(2)+'M';
  return '$'+Math.round(v).toLocaleString('en-US');
}}
function fmtPctJs(v){{
  if(v===null || v===undefined || v==='') return '—';
  v=Number(v);
  return (v>=0?'+':'')+v.toFixed(2)+'%';
}}
function fmtClockKst(){{
  return new Intl.DateTimeFormat('ko-KR',{{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',hour12:false}}).format(new Date())+' 갱신';
}}
async function updatePagesLiveData(){{
  try{{
    const r=await fetch('data/live_data.json?ts='+Date.now(),{{cache:'no-store'}});
    if(!r.ok) throw new Error('live_data.json fetch failed');
    const data=await r.json();
    const info=data.info||{{}};
    const xrpl=data.xrpl_stats||{{}};
    if(info.price_usd){{ setText('hero-price',fmtUsd(info.price_usd)); }}
    if(info.market_cap_usd){{ setText('hero-mcap',fmtLargeUsd(info.market_cap_usd)); }}
    if(info.price_change_24h!==undefined){{
      const pct=document.getElementById('hero-pct');
      const mp=document.getElementById('hero-mcap-pct');
      const label=(Number(info.price_change_24h)>=0?'▲ ':'▼ ')+fmtPctJs(info.price_change_24h);
      if(pct) pct.textContent=label;
      if(mp) mp.textContent=fmtPctJs(info.price_change_24h);
    }}
    const tpsVal = xrpl.tps_24h_avg ?? xrpl.recent_tps;
    if(tpsVal && Number(tpsVal)>0){{
      setText('hero-tps',Number(tpsVal).toFixed(2));
      setText('hero-tps-sub',xrpl.status_label||'최근 ledger 평균');
    }}else{{
      setText('hero-tps','TPS 수집중');
      setText('hero-tps-sub','수집 대기');
    }}
    const etf=data.etf_flow||{{}};
    const daily=Number(etf.daily_inflow_usd||0);
    const total=Number(etf.total_net_inflow_usd||0);
    setText('etf-daily-inflow', daily ? fmtLargeUsd(daily) : '일일 순유입 수집중');
    setText('etf-total-inflow', total ? fmtLargeUsd(total) : '누적 순유입 수집중');
    setText('etf-flow-source', etf.updated_at || 'ETF 순유입 수집중');
    setText('hero-updated',fmtClockKst());
    setText('last-updated',fmtClockKst());
  }}catch(e){{
    setText('hero-tps','TPS 수집중');
    setText('hero-tps-sub','수집 실패');
  }}
}}


function formatHeroUsd(v){{
  return '$'+Number(v||0).toLocaleString('en-US',{{minimumFractionDigits:4,maximumFractionDigits:4}});
}}
function easeOutCubic(t){{return 1-Math.pow(1-t,3);}}
function easeInOutCubic(t){{return t<0.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;}}
function animateHeroPriceNumber(from,to,duration,onDone){{
  const el=document.getElementById('hero-price');
  if(!el){{if(onDone)onDone();return;}}
  const start=performance.now();
  function frame(now){{
    const t=Math.min(1,(now-start)/duration);
    const eased=duration<=600?easeInOutCubic(t):easeOutCubic(t);
    const value=from+(to-from)*eased;
    el.textContent=formatHeroUsd(value);
    if(t<1){{requestAnimationFrame(frame);}}
    else{{el.textContent=formatHeroUsd(to);if(onDone)onDone();}}
  }}
  requestAnimationFrame(frame);
}}
function runPriceBoostTo100(){{
  if(priceBoostRunning)return;
  const el=document.getElementById('hero-price');
  const fallback=el?Number(String(el.textContent||'').replace(/[^0-9.]/g,'')):0;
  const start=Number(liveHeroPriceUsd || fallback || 0);
  priceBoostRunning=true;
  if(el)el.classList.add('price-boosting');
  // 상승 2초 → $100 유지 1초 → 원래 실시간 가격으로 0.5초 복귀
  animateHeroPriceNumber(start,100,2000,()=>{{
    setTimeout(()=>{{
      const backTo=Number(liveHeroPriceUsd || start || 0);
      animateHeroPriceNumber(100,backTo,500,()=>{{
        priceBoostRunning=false;
        if(el)el.classList.remove('price-boosting');
        setText('hero-price',formatHeroUsd(liveHeroPriceUsd || backTo));
      }});
    }},1000);
  }});
}}

function attachHeroButtonEffects(){{
  document.querySelectorAll('.hero-btn').forEach(btn=>{{
    if(btn.dataset.rippleReady==='1') return;
    btn.dataset.rippleReady='1';
    btn.addEventListener('click',e=>{{
      const rect=btn.getBoundingClientRect();
      const size=Math.max(rect.width,rect.height)*1.15;
      const ripple=document.createElement('span');
      ripple.className='hero-ripple';
      ripple.style.width=size+'px';
      ripple.style.height=size+'px';
      // 버튼 내부 클릭점이 아니라 버튼 중심에서 바깥으로 퍼지는 shockwave 방식
      ripple.style.left='50%';
      ripple.style.top='50%';
      btn.appendChild(ripple);
      btn.classList.remove('flash-red');
      void btn.offsetWidth;
      btn.classList.add('flash-red');
      setTimeout(()=>btn.classList.remove('flash-red'),220);
      runPriceBoostTo100();
      ripple.addEventListener('animationend',()=>ripple.remove(),{{once:true}});
    }});
  }});
}}
attachHeroButtonEffects();

updatePagesLiveData();setInterval(updatePagesLiveData,5*60*1000);

updateNews();setInterval(updateNews,5*60*1000);
updateRegNews();setInterval(updateRegNews,5*60*1000);
updateEtfNews();setInterval(updateEtfNews,5*60*1000);
</script>
</body>
</html>"""


def write_github_pages_live_data(output_dir, info, xrpl_stats, etf_flow, etf_news, general_news):
    """GitHub Pages가 5분마다 읽을 정적 JSON 생성."""
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "timezone": "Asia/Seoul",
        "info": info or {},
        "xrpl_stats": xrpl_stats or {},
        "etf_flow": etf_flow or {},
        "etf_news": etf_news or [],
        "general_news": general_news or []
    }
    with open(os.path.join(data_dir, "live_data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "xrpl_stats.json"), "w", encoding="utf-8") as f:
        json.dump(xrpl_stats or {}, f, ensure_ascii=False, indent=2)
    return os.path.join(data_dir, "live_data.json")


# ─────────────────────────────────────────────────
# 5. 메인
# ─────────────────────────────────────────────────

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.getenv("PAGES_OUTPUT_DIR", base_dir)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")
    legacy_output_path = os.path.join(output_dir, "xrp_report.html")
    print("=" * 54)
    print("  XRP Daily Analyzer v2.1 · GitHub Pages 5min")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 54)

    df = fetch_ohlc(90)
    if df is None or len(df) < 30:
        print("❌ 가격 데이터 부족"); sys.exit(1)

    info                                    = fetch_current_info();      time.sleep(1)
    general_news                            = fetch_all_news();          time.sleep(1)
    clarity_news, genius_news, sec_news     = fetch_regulatory();        time.sleep(1)
    etf_news, xrpl_stats, rlusd_mcap, etf_flow = fetch_institutional();     time.sleep(1)
    fg_value, fg_label, fg_history          = fetch_fear_greed()

    df = calc_indicators(df)
    signals, score, direction, dir_color, dir_eng = gen_signals(df)

    print("\n▶ HTML 생성 중...")
    html = build_html(
        df, info, fg_value, fg_label, fg_history,
        signals, score, direction, dir_color, dir_eng,
        general_news,
        clarity_news, genius_news, sec_news,
        etf_news, xrpl_stats, rlusd_mcap, etf_flow
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(legacy_output_path, "w", encoding="utf-8") as f:
        f.write(html)
    live_json_path = write_github_pages_live_data(output_dir, info, xrpl_stats, etf_flow, etf_news, general_news)

    print(f"\n✅ 완료 → {output_path}")
    print(f"   호환 파일 → {legacy_output_path}")
    print(f"   5분 갱신 JSON → {live_json_path}")
    print(f"   방향성: {direction} ({score:+.1f}pt)")
    print("=" * 54)


if __name__ == "__main__":
    main()
