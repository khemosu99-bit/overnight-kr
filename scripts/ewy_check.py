"""
EWY 이상치 원인 규명
- 배당락인가, 실제 급락인가, 데이터 오류인가
"""
import datetime
import requests
import pandas as pd
import yfinance as yf

UA = {"User-Agent": "Mozilla/5.0"}
print("=" * 76)
print("  【1】 EWY 배당 이력  ← 7/13 배당락 여부")
print("=" * 76)

t = yf.Ticker("EWY")
div = t.dividends
if len(div):
    print(f"\n  {'배당락일':<14} {'분배금':>10}")
    print("  " + "-" * 26)
    for d, v in div.tail(8).items():
        mark = "  🚨 여기!" if str(d)[:10] >= "2026-07-01" else ""
        print(f"  {str(d)[:10]:<14} ${v:>9.4f}{mark}")
else:
    print("  배당 이력 없음")

print("\n" + "=" * 76)
print("  【2】 원시가격 vs 배당조정가격 비교")
print("=" * 76)

raw = yf.download("EWY", period="15d", auto_adjust=False, progress=False)
adj = yf.download("EWY", period="15d", auto_adjust=True, progress=False)
for d in (raw, adj):
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)

print(f"\n  {'날짜':<12} {'원시종가':>10} {'원시%':>8} | {'조정종가':>10} {'조정%':>8}")
print("  " + "-" * 56)
rr = raw["Close"].pct_change() * 100
ar = adj["Close"].pct_change() * 100
for d in raw.index[-8:]:
    ds = str(d)[:10]
    f1 = " 🚨" if abs(rr.get(d, 0)) > 5 else "   "
    f2 = " 🚨" if abs(ar.get(d, 0)) > 5 else "   "
    print(f"  {ds:<12} {raw['Close'][d]:>10.2f} {rr.get(d,0):>+7.2f}%{f1}| "
          f"{adj['Close'][d]:>10.2f} {ar.get(d,0):>+7.2f}%{f2}")

print("\n  → 원시만 -8%이고 조정은 정상이면 → 배당락 확정. auto_adjust=True로 해결")
print("     둘 다 -8%이면 → 실제 급락 또는 데이터 오류")

print("\n" + "=" * 76)
print("  【3】 같은 날 한국 관련 지표 교차 확인 (7/13)")
print("=" * 76)


def last_ret(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"interval": "1d", "range": "5d"},
                     headers=UA, timeout=20)
    res = r.json()["chart"]["result"][0]
    c = [x for x in res["indicators"]["quote"][0]["close"] if x]
    return (c[-1] / c[-2] - 1) * 100, c[-1]


print(f"\n  {'지표':<28} {'최근 등락':>10}")
print("  " + "-" * 40)
for s, n in [("EWY", "EWY (한국 ETF)"), ("FLKR", "FLKR (한국 ETF 대체)"),
             ("^SOX", "필라델피아 반도체"), ("^GSPC", "S&P500"),
             ("KRW=X", "달러/원")]:
    try:
        r, v = last_ret(s)
        flag = " 🚨" if abs(r) > 5 else ""
        print(f"  {n:<28} {r:>+9.2f}%{flag}")
    except Exception as e:
        print(f"  {n:<28} {'조회실패':>10}")

print("\n  → 다른 한국 ETF(FLKR)도 -8%면 → 실제 한국 급락")
print("     EWY만 -8%면 → EWY 고유 이벤트(배당/분할)")

print("\n" + "=" * 76)
print("  【4】 265일 데이터에 배당락이 몇 번 섞였나")
print("=" * 76)
full_raw = yf.download("EWY", start="2025-06-01", auto_adjust=False, progress=False)
full_adj = yf.download("EWY", start="2025-06-01", auto_adjust=True, progress=False)
for d in (full_raw, full_adj):
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
r1 = (full_raw["Close"].pct_change() * 100).dropna()
r2 = (full_adj["Close"].pct_change() * 100).dropna()
gap = (r1 - r2).abs()
hits = gap[gap > 0.3]
print(f"\n  원시-조정 차이가 0.3%p 넘는 날: {len(hits)}일 / {len(r1)}일")
if len(hits):
    print(f"\n  {'날짜':<12} {'원시%':>8} {'조정%':>8} {'차이':>8}")
    print("  " + "-" * 38)
    for d in hits.index:
        print(f"  {str(d)[:10]:<12} {r1[d]:>+7.2f}% {r2[d]:>+7.2f}% {gap[d]:>7.2f}%p")
print(f"\n  → 이 날들이 우리 분석에 노이즈로 들어가 있었습니다.")
