"""
실시간 데이터 소스 실측
- 무엇이 실제로 되는지 두드려본다. 추측하지 않는다.
"""
import json
import datetime
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
print(f"🕐 현재 KST {KST:%Y-%m-%d %H:%M}\n")
print("=" * 74)

def probe(name, fn):
    try:
        v = fn()
        print(f"  ✅ {name:<34} {v}")
        return True
    except Exception as e:
        print(f"  ❌ {name:<34} {str(e)[:34]}")
        return False


# ── 1. Yahoo 실시간 (야간선물 후보 심볼 포함) ──
print("\n【1】 Yahoo Finance 실시간")
print("-" * 74)

def yq(sym):
    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
        params={"interval": "1m", "range": "1d"},
        headers=UA, timeout=15)
    m = r.json()["chart"]["result"][0]["meta"]
    p = m.get("regularMarketPrice")
    prev = m.get("chartPreviousClose") or m.get("previousClose")
    pct = (p / prev - 1) * 100 if p and prev else None
    t = datetime.datetime.utcfromtimestamp(
        m.get("regularMarketTime", 0)) + datetime.timedelta(hours=9)
    return (f"{p} (전일比 {pct:+.2f}%)  갱신 {t:%m-%d %H:%M} KST"
            if pct is not None else f"{p}")

for sym, nm in [("EWY", "EWY 한국ETF ⭐"),
                ("NQ=F", "나스닥 선물 (24h)"),
                ("ES=F", "S&P500 선물 (24h)"),
                ("^SOX", "필라델피아 반도체"),
                ("KRW=X", "달러/원"),
                ("^KS11", "코스피 지수"),
                ("^KS200", "코스피200 지수"),
                ("KSU26.CME", "CME 코스피200 선물?"),
                ("KS200=F", "코스피200 선물?")]:
    probe(nm, lambda s=sym: yq(s))


# ── 2. Stooq ──
print("\n【2】 Stooq")
print("-" * 74)

def sq(sym):
    r = requests.get("https://stooq.com/q/l/",
                     params={"s": sym, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
                     headers=UA, timeout=15)
    line = r.text.strip().splitlines()[-1]
    if not line or "N/D" in line:
        raise ValueError("데이터 없음")
    return line

for sym, nm in [("ewy.us", "EWY"), ("^spx", "S&P500"), ("usdkrw", "달러/원")]:
    probe(nm, lambda s=sym: sq(s))


# ── 3. 네이버 금융 (참고용 — 실제 사용은 별도 검토 필요) ──
print("\n【3】 네이버 금융 (접근 가능 여부만 확인)")
print("-" * 74)

def naver(code):
    r = requests.get(f"https://polling.finance.naver.com/api/realtime/domestic/index/{code}",
                     headers=UA, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    j = r.json()
    d = j["datas"][0]
    return f"{d.get('closePrice')} ({d.get('fluctuationsRatio')}%)"

for c, nm in [("KOSPI", "코스피"), ("KOSPI200", "코스피200")]:
    probe(nm, lambda x=c: naver(x))


# ── 4. TradingView 위젯 심볼 존재 확인 ──
print("\n【4】 TradingView 심볼 검색 (위젯 임베드용)")
print("-" * 74)

def tv(q):
    r = requests.get("https://symbol-search.tradingview.com/symbol_search/",
                     params={"text": q, "type": ""},
                     headers={**UA, "Referer": "https://www.tradingview.com/"},
                     timeout=15)
    j = r.json()
    if not j:
        raise ValueError("결과 없음")
    out = []
    for x in j[:4]:
        sym = x.get("symbol", "").replace("<em>", "").replace("</em>", "")
        out.append(f"{x.get('exchange')}:{sym}")
    return " | ".join(out)

for q in ["KOSPI 200", "KOSPI", "EWY", "KRX"]:
    probe(f"검색 '{q}'", lambda x=q: tv(x))

print("\n" + "=" * 74)
print("""
📌 판정 기준
  · ✅ EWY / 나스닥선물 / S&P선물  → 🅱️안 가능. 실시간 자동 환산 ⭐
  · ✅ 코스피200 선물 실시간 심볼   → 🅰️안 가능. 야간선물 직접 표시
  · TradingView에 KRX 심볼 존재    → 위젯 임베드 가능
  · 전부 ❌                        → 재설계 필요
""")
