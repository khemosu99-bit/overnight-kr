"""
KRX 야간 세션 정찰
1) 야간 데이터가 언제부터 존재하는가
2) 야간이 정규보다 먼저인가 (인과 순서 검증)
"""
import os
import time
import json
import pathlib
import datetime
import requests

AUTH = os.environ.get("KRX_AUTH_KEY", "").strip()
BASE = "https://data-dbg.krx.co.kr/svc/apis"

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "krx"
RAW.mkdir(parents=True, exist_ok=True)


def call(path, bas_dd):
    r = requests.post(BASE + path,
                      headers={"AUTH_KEY": AUTH, "Content-Type": "application/json"},
                      json={"basDd": bas_dd}, timeout=30)
    if r.status_code != 200:
        return None
    d = r.json()
    return d.get("OutBlock_1") or d.get("outBlock_1") or []


def fut(bas_dd):
    """코스피200 선물(미니 제외) 최근월물을 야간/정규로 나눠 반환"""
    rows = call("/drv/fut_bydd_trd", bas_dd)
    if not rows:
        return None, None
    out = {}
    for mkt in ("야간", "정규"):
        c = [r for r in rows
             if r.get("MKT_NM") == mkt
             and r.get("PROD_NM") == "코스피200 선물"
             and str(r.get("TDD_CLSPRC", "")).strip()]
        if c:  # 거래량 최대 = 최근월물
            out[mkt] = max(c, key=lambda r: float(
                str(r.get("ACC_TRDVOL", "0")).replace(",", "") or 0))
    return out.get("야간"), out.get("정규")


def idx200(bas_dd):
    rows = call("/idx/kospi_dd_trd", bas_dd)
    if not rows:
        return None
    for r in rows:
        if r.get("IDX_NM", "").strip() == "코스피 200":
            return r
    return None


def f(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


# ══════ PART 1. 야간 데이터 존재 범위 ══════
def scan():
    print("=" * 76)
    print("  【PART 1】 야간 데이터가 언제부터 있는가")
    print("=" * 76)
    probes = ["20100615", "20150617", "20200617", "20230615", "20240619",
              "20250408", "20250610", "20250915", "20260115", "20260610"]
    print(f"\n  {'기준일':<12} {'전체':>6} {'야간행':>7} {'정규행':>7}  판정")
    print("  " + "-" * 56)
    for d in probes:
        rows = call("/drv/fut_bydd_trd", d)
        time.sleep(0.4)
        if rows is None:
            print(f"  {d:<12} {'호출실패':>6}")
            continue
        n = len(rows)
        ni = sum(1 for r in rows if r.get("MKT_NM") == "야간")
        rg = sum(1 for r in rows if r.get("MKT_NM") == "정규")
        mark = "✅ 야간 있음" if ni else ("─ 정규만" if rg else "휴장")
        print(f"  {d:<12} {n:>6} {ni:>7} {rg:>7}  {mark}")


# ══════ PART 2. 인과 순서 검증 ══════
def order():
    print("\n\n" + "=" * 76)
    print("  【PART 2】 야간 → 정규 순서 검증  (최근 20영업일)")
    print("=" * 76)
    print("\n  가설: 야간종가(06시) 가 정규시가(09시) 를 예고한다")
    print(f"\n  {'날짜':<10} {'야간종가':>9} {'정규시가':>9} {'정규종가':>9} "
          f"{'갭%':>7} {'장중%':>7}")
    print("  " + "-" * 62)

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    got, prev_reg_close = 0, None
    rec = []

    for back in range(2, 45):
        d = today - datetime.timedelta(days=back)
        if d.weekday() >= 5:
            continue
        bas = d.strftime("%Y%m%d")
        n, rgl = fut(bas)
        time.sleep(0.4)
        if not rgl:
            continue
        rec.append((bas, n, rgl))
        got += 1
        if got >= 20:
            break

    rec.reverse()
    for bas, n, rgl in rec:
        nc = f(n["TDD_CLSPRC"]) if n else None
        ro = f(rgl["TDD_OPNPRC"])
        rc = f(rgl["TDD_CLSPRC"])
        gap = (ro / prev_reg_close - 1) * 100 if prev_reg_close and ro else None
        intra = (rc / ro - 1) * 100 if ro and rc else None
        print(f"  {bas:<10} {nc if nc else '  없음':>9} {ro:>9,.2f} {rc:>9,.2f} "
              f"{gap:>+7.2f} {intra:>+7.2f}" if gap is not None
              else f"  {bas:<10} {nc if nc else '  없음':>9} {ro:>9,.2f} {rc:>9,.2f}")
        prev_reg_close = rc

    print("\n  💡 확인 포인트")
    print("     · 야간종가가 정규시가와 가까우면 → 야간이 먼저 (가설 맞음) ✅")
    print("     · 야간종가가 정규종가와 가까우면 → 야간이 나중 (가설 틀림) ❌")


if __name__ == "__main__":
    if not AUTH:
        raise SystemExit("❌ KRX_AUTH_KEY 없음")
    scan()
    order()
