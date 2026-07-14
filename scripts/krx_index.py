"""
KRX 지수(코스피·코스닥) 일별 수집기
- kr_index.csv 를 매일 이어서 채운다 (누락된 날짜만)
- 이게 없으면 아카이브가 멈춘다
"""
import os
import csv
import time
import pathlib
import datetime
import requests

AUTH = os.environ.get("KRX_AUTH_KEY", "").strip()
BASE = "https://data-dbg.krx.co.kr/svc/apis"
ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "kr_index.csv"
COLS = ["date", "kospi_open", "kospi_close", "kosdaq_open", "kosdaq_close"]

START = datetime.date(2025, 6, 9)   # KRX 자체 야간시장 개장일


def call(path, d):
    for _ in range(3):
        try:
            r = requests.post(
                BASE + path,
                headers={"AUTH_KEY": AUTH, "Content-Type": "application/json"},
                json={"basDd": d}, timeout=30)
            if r.status_code == 200:
                j = r.json()
                return j.get("OutBlock_1") or j.get("outBlock_1") or []
        except Exception:
            pass
        time.sleep(2)
    return []


def f(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def main():
    if not AUTH:
        raise SystemExit("KRX_AUTH_KEY 없음")

    have = {}
    if CACHE.exists():
        for r in csv.DictReader(CACHE.open(encoding="utf-8")):
            have[r["date"]] = r
    print(f"기존 보유 {len(have)}일" + (f" (최신 {max(have)})" if have else ""))

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    start = (max(datetime.date.fromisoformat(max(have)), START)
             if have else START)

    added = 0
    d = start + datetime.timedelta(days=1) if have else START
    while d < today:
        if d.weekday() >= 5 or d.isoformat() in have:
            d += datetime.timedelta(days=1)
            continue

        bas = d.strftime("%Y%m%d")
        rec = {"date": d.isoformat()}
        for api, nm, pre in [("/idx/kospi_dd_trd", "코스피", "kospi"),
                             ("/idx/kosdaq_dd_trd", "코스닥", "kosdaq")]:
            rows = call(api, bas)
            time.sleep(0.3)
            m = next((r for r in rows if r.get("IDX_NM", "").strip() == nm), None)
            if m:
                rec[f"{pre}_open"] = f(m.get("OPNPRC_IDX"))
                rec[f"{pre}_close"] = f(m.get("CLSPRC_IDX"))

        if rec.get("kospi_close"):
            have[rec["date"]] = rec
            added += 1
            print(f"  + {rec['date']}  코스피 {rec['kospi_close']:,.2f}")
        d += datetime.timedelta(days=1)

    with CACHE.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=COLS)
        w.writeheader()
        for k in sorted(have):
            w.writerow({c: have[k].get(c, "") for c in COLS})

    print("=" * 52)
    print(f"  총 {len(have)}일 (신규 {added}일)  최신 {max(have)}")
    print("=" * 52)


if __name__ == "__main__":
    main()
