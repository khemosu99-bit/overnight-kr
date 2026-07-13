"""
실시간 값 정합성 교차검증
- Yahoo 실시간 vs KRX 공식 확정치를 대조한다
- -9% 같은 값이 진짜인지 오류인지 판정한다
"""
import os, time, datetime
import requests

UA = {"User-Agent": "Mozilla/5.0"}
AUTH = os.environ["KRX_AUTH_KEY"].strip()
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
print(f"🕐 KST {KST:%Y-%m-%d %H:%M}\n")


def yahoo(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"interval": "1d", "range": "10d"},
                     headers=UA, timeout=20)
    res = r.json()["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(ts):
        d = datetime.datetime.utcfromtimestamp(t) + datetime.timedelta(hours=9)
        c = q["close"][i]
        if c:
            out.append((d.strftime("%Y-%m-%d"), round(c, 2)))
    return out


def krx(bas):
    r = requests.post("https://data-dbg.krx.co.kr/svc/apis/idx/kospi_dd_trd",
                      headers={"AUTH_KEY": AUTH, "Content-Type": "application/json"},
                      json={"basDd": bas}, timeout=30)
    if r.status_code != 200:
        return None
    rows = r.json().get("OutBlock_1", [])
    m = next((x for x in rows if x.get("IDX_NM", "").strip() == "코스피"), None)
    return float(m["CLSPRC_IDX"].replace(",", "")) if m else None


print("=" * 72)
print("  【교차검증】 Yahoo 코스피 vs KRX 공식 코스피")
print("=" * 72)
print(f"\n  {'날짜':<12} {'Yahoo':>11} {'KRX 공식':>11} {'차이':>9}  판정")
print("  " + "-" * 58)

ya = dict(yahoo("^KS11"))
bad = 0
for d in sorted(ya)[-8:]:
    k = krx(d.replace("-", ""))
    time.sleep(0.4)
    if k is None:
        print(f"  {d:<12} {ya[d]:>11,.2f} {'(휴장)':>11}")
        continue
    diff = (ya[d] / k - 1) * 100
    ok = abs(diff) < 0.1
    if not ok:
        bad += 1
    print(f"  {d:<12} {ya[d]:>11,.2f} {k:>11,.2f} {diff:>+8.2f}%  "
          f"{'✅ 일치' if ok else '🚨 불일치'}")

print("\n" + "=" * 72)
if bad:
    print(f"  🚨 {bad}일 불일치 → Yahoo 코스피 데이터 신뢰 불가. KRX만 사용.")
else:
    print(f"  ✅ 전부 일치 → 최근 급락은 실제 시장 상황.")

# ── 미국 지표 일별 등락 (오류 여부 판정) ──
print("\n" + "=" * 72)
print("  【미국 지표】 최근 5일 등락률  ← 비정상 값 탐지")
print("=" * 72)
for sym, nm in [("EWY", "EWY 한국ETF"), ("^SOX", "필라델피아 반도체"),
                ("^GSPC", "S&P500")]:
    h = yahoo(sym)[-6:]
    print(f"\n  ── {nm} ──")
    for i in range(1, len(h)):
        d, c = h[i]
        pc = h[i - 1][1]
        r = (c / pc - 1) * 100
        flag = " 🚨" if abs(r) > 5 else ""
        print(f"    {d}  {c:>10,.2f}  {r:>+7.2f}%{flag}")

print("\n  💡 여러 지표가 동시에 급락했으면 → 실제 시장 사건")
print("     한 지표만 튀었으면 → 데이터 오류")
