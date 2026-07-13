"""
KRX 야간→정규 히스토리 수집기
- 2025-06-09 (KRX 자체 야간시장 개장) 이후 전 영업일
- 야간종가 / 정규시가 / 정규종가 를 한 행으로
- 이어받기 지원 (중단돼도 다시 돌리면 이어서 진행)
"""
import os
import csv
import time
import pathlib
import datetime
import requests

AUTH = os.environ.get("KRX_AUTH_KEY", "").strip()
BASE = "https://data-dbg.krx.co.kr/svc/apis"
START = datetime.date(2025, 6, 9)      # KRX 자체 야간시장 개장일

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "night_futures.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

COLS = ["date", "night_close", "reg_open", "reg_high", "reg_low", "reg_close",
        "reg_vol", "open_int", "k200_open", "k200_close", "kospi_close"]


def call(path, d):
    for _ in range(3):
        try:
            r = requests.post(BASE + path,
                              headers={"AUTH_KEY": AUTH,
                                       "Content-Type": "application/json"},
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


def pick(rows, mkt):
    """코스피200 선물 최근월물 (거래량 최대)"""
    c = [r for r in rows
         if r.get("MKT_NM") == mkt
         and r.get("PROD_NM") == "코스피200 선물"
         and f(r.get("TDD_CLSPRC"))]
    if not c:
        return None
    return max(c, key=lambda r: f(r.get("ACC_TRDVOL")) or 0)


def one_day(d):
    bas = d.strftime("%Y%m%d")
    fut = call("/drv/fut_bydd_trd", bas)
    if not fut:
        return None
    night, reg = pick(fut, "야간"), pick(fut, "정규")
    if not reg:
        return None

    idx = call("/idx/kospi_dd_trd", bas)
    k200 = next((r for r in idx if r.get("IDX_NM", "").strip() == "코스피 200"), {})
    kospi = next((r for r in idx if r.get("IDX_NM", "").strip() == "코스피"), {})

    return {
        "date":        d.isoformat(),
        "night_close": f(night["TDD_CLSPRC"]) if night else "",
        "reg_open":    f(reg.get("TDD_OPNPRC")),
        "reg_high":    f(reg.get("TDD_HGPRC")),
        "reg_low":     f(reg.get("TDD_LWPRC")),
        "reg_close":   f(reg.get("TDD_CLSPRC")),
        "reg_vol":     f(reg.get("ACC_TRDVOL")),
        "open_int":    f(reg.get("ACC_OPNINT_QTY")),
        "k200_open":   f(k200.get("OPNPRC_IDX")) if k200 else "",
        "k200_close":  f(k200.get("CLSPRC_IDX")) if k200 else "",
        "kospi_close": f(kospi.get("CLSPRC_IDX")) if kospi else "",
    }


def main():
    if not AUTH:
        raise SystemExit("❌ KRX_AUTH_KEY 없음")

    # 이어받기
    done = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8") as fp:
            for r in csv.DictReader(fp):
                done[r["date"]] = r
        print(f"📂 기존 {len(done)}일 보유. 빠진 날만 채웁니다.\n")

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    d, added, night_cnt = START, 0, 0

    while d < today:
        if d.weekday() >= 5 or d.isoformat() in done:
            d += datetime.timedelta(days=1)
            continue

        row = one_day(d)
        time.sleep(0.35)
        if row:
            done[d.isoformat()] = row
            added += 1
            if row["night_close"]:
                night_cnt += 1
            if added % 20 == 0:
                print(f"  ... {added}일 수집 (최근: {d})")
        d += datetime.timedelta(days=1)

    rows = [done[k] for k in sorted(done)]
    with OUT.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    have_night = sum(1 for r in rows if r.get("night_close"))
    print("\n" + "=" * 60)
    print(f"  ✅ 총 {len(rows)}일 저장  →  data/night_futures.csv")
    print(f"     이번에 추가:  {added}일")
    print(f"     야간종가 보유: {have_night}일")
    print("=" * 60)

    print(f"\n  ── 최근 5일 ──")
    for r in rows[-5:]:
        print(f"  {r['date']}  야간 {str(r['night_close']):>8}  "
              f"시가 {str(r['reg_open']):>8}  종가 {str(r['reg_close']):>8}")


if __name__ == "__main__":
    main()
