"""
야간선물 → 실제 지수(코스피/코스닥) 연결 검증

※ 지금까지는 '선물 → 선물'만 봤다. (사실상 같은 상품끼리 비교)
※ 사람들이 진짜 궁금한 건 '야간선물 → 내일 코스피 종가'다.
"""
import os
import csv
import time
import pathlib
import numpy as np
import pandas as pd
import requests

AUTH = os.environ["KRX_AUTH_KEY"].strip()
BASE = "https://data-dbg.krx.co.kr/svc/apis"
ROOT = pathlib.Path(__file__).resolve().parent.parent

df = pd.read_csv(ROOT / "data" / "night_futures.csv", parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)


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


# ═══════ 코스피/코스닥 지수 OHLC 수집 (이어받기 지원) ═══════
CACHE = ROOT / "data" / "kr_index.csv"
COLS = ["date", "kospi_open", "kospi_close", "kosdaq_open", "kosdaq_close"]

have = {}
if CACHE.exists():
    for r in csv.DictReader(CACHE.open(encoding="utf-8")):
        have[r["date"]] = r

need = [d for d in df["date"] if d.strftime("%Y-%m-%d") not in have]
print(f"📥 지수 데이터 보강: {len(need)}일 필요 (기존 {len(have)}일 보유)\n")

for i, dt in enumerate(need):
    bas = dt.strftime("%Y%m%d")
    rec = {"date": dt.strftime("%Y-%m-%d")}
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
    if (i + 1) % 40 == 0:
        print(f"   ... {i+1}/{len(need)} 완료")

with CACHE.open("w", newline="", encoding="utf-8") as fp:
    w = csv.DictWriter(fp, fieldnames=COLS)
    w.writeheader()
    for k in sorted(have):
        w.writerow({c: have[k].get(c, "") for c in COLS})
print(f"✅ 지수 {len(have)}일 확보 → data/kr_index.csv\n")


# ═══════ 병합 & 지표 계산 ═══════
idx = pd.read_csv(CACHE, parse_dates=["date"])

# ⚠️ night_futures.csv에 이미 kospi_close 등이 있어 이름이 충돌한다.
#    kr_index.csv 쪽이 정본이므로, df에서 중복 컬럼을 먼저 버린다.
dup = [c for c in idx.columns if c != "date" and c in df.columns]
if dup:
    print(f"⚠️ 중복 컬럼 제거 (kr_index 쪽을 정본으로 사용): {dup}")
    df = df.drop(columns=dup)

d = df.merge(idx, on="date", how="inner").sort_values("date").reset_index(drop=True)
print(f"✅ 병합 완료: {len(d)}일\n")

d["fut_prev"] = d["reg_close"].shift(1)
d["night_ret"] = (d["night_close"] / d["fut_prev"] - 1) * 100

for m in ["kospi", "kosdaq"]:
    p = d[f"{m}_close"].shift(1)
    d[f"{m}_gap"] = (d[f"{m}_open"] / p - 1) * 100       # 개장 갭
    d[f"{m}_full"] = (d[f"{m}_close"] / p - 1) * 100     # 하루 전체 (종가!)
    d[f"{m}_intra"] = (d[f"{m}_close"] / d[f"{m}_open"] - 1) * 100  # 장중

e = d.dropna(subset=["night_ret", "kospi_gap", "kospi_full"]).copy()


def fit(x, y):
    b = np.polyfit(x, y, 1)
    pred = np.polyval(b, x)
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return b[0], b[1], r2, (y - pred).std()


def tt(s):
    s = s.dropna()
    if len(s) < 15:
        return np.nan, len(s)
    return s.mean() / (s.std() / np.sqrt(len(s))), len(s)


print("=" * 80)
print(f"  야간선물 → 실제 지수  |  {e['date'].min():%Y-%m-%d} ~ "
      f"{e['date'].max():%Y-%m-%d}  ({len(e)}일)")
print("=" * 80)

# ── 【1】 회귀 요약 ──
print("\n【1】 야간선물 → 지수 (회귀)")
print(f"  {'대상':<24} {'베타':>7} {'R²':>7} {'80%폭':>9} {'상관':>7}")
print("  " + "-" * 58)
for m, nm in [("kospi", "코스피"), ("kosdaq", "코스닥")]:
    for k, lab in [("gap", "개장갭"), ("full", "종가(하루전체)")]:
        s = e.dropna(subset=[f"{m}_{k}"])
        b, a, r2, se = fit(s["night_ret"], s[f"{m}_{k}"])
        c = s[["night_ret", f"{m}_{k}"]].corr().iloc[0, 1]
        print(f"  {nm + ' ' + lab:<24} {b:>7.3f} {r2:>7.3f}  "
              f"±{1.28*se:>6.2f}%p {c:>7.3f}")

# ── 【2】 핵심: 종가 설명력 ──
print("\n【2】 ⭐ 핵심: 종가는 얼마나 설명되나?")
for m, nm in [("kospi", "코스피"), ("kosdaq", "코스닥")]:
    s = e.dropna(subset=[f"{m}_full", f"{m}_gap", f"{m}_intra"])
    _, _, r2g, _ = fit(s["night_ret"], s[f"{m}_gap"])
    _, _, r2f, _ = fit(s["night_ret"], s[f"{m}_full"])
    _, _, r2i, _ = fit(s["night_ret"], s[f"{m}_intra"])
    ti, _ = tt(s[f"{m}_intra"])
    same = ((s["night_ret"] > 0) == (s[f"{m}_full"] > 0)).mean() * 100
    print(f"\n  ── {nm} ──")
    print(f"    개장갭 설명력   R² {r2g:.3f}")
    print(f"    종가   설명력   R² {r2f:.3f}   ← 사람들이 궁금한 것")
    print(f"    장중   설명력   R² {r2i:.3f}   ← 0에 가까우면 '장중은 모른다' 확정")
    print(f"    방향 일치율(종가) {same:.1f}%")

# ── 【3】 조건별 종가 (사이트 문장 재료) ──
print("\n【3】 조건별 종가 결과  ← 사이트에 쓸 문장")
for m, nm in [("kospi", "코스피"), ("kosdaq", "코스닥")]:
    print(f"\n  ── {nm} ──")
    for lo, hi, lab in [(1, 99, "야간 +1% 이상"),
                        (0.3, 1, "야간 +0.3~1%"),
                        (-1, -0.3, "야간 -0.3~-1%"),
                        (-99, -1, "야간 -1% 이하")]:
        s = e[e["night_ret"].between(lo, hi)].dropna(subset=[f"{m}_full"])
        if len(s) < 15:
            continue
        up = (s[f"{m}_full"] > 0).mean() * 100
        _, n = tt(s[f"{m}_full"])
        print(f"    {lab:<16} {n:>4}회 | 종가평균 {s[f'{m}_full'].mean():>+6.2f}% | "
              f"상승 {up:>5.1f}% | 갭평균 {s[f'{m}_gap'].mean():>+6.2f}%")

# ── 【4】 과최적화 검증 ──
print("\n【4】 과최적화 검증 (앞60% 학습 / 뒤40% 시험)")
cut = e["date"].quantile(0.6)
for lab, s in [("학습", e[e["date"] <= cut]), ("시험", e[e["date"] > cut])]:
    b, a, r2, se = fit(s["night_ret"], s["kospi_full"])
    bg, _, r2g, _ = fit(s["night_ret"], s["kospi_gap"])
    print(f"  {lab}  종가: β={b:.3f} R²={r2:.3f}  |  갭: β={bg:.3f} R²={r2g:.3f}")
print("  → 시험구간에서도 R²가 유지되면 진짜")

# ── 【5】 학습 범위 (안전장치용) ──
print("\n【5】 학습 데이터 범위  ← 모델 적용 한계 설정")
q = e["night_ret"].quantile([0.01, 0.05, 0.95, 0.99])
print(f"  야간등락  1% 분위 {q[0.01]:+.2f}%   99% 분위 {q[0.99]:+.2f}%")
print(f"            5% 분위 {q[0.05]:+.2f}%   95% 분위 {q[0.95]:+.2f}%")
print(f"  최소 {e['night_ret'].min():+.2f}%  최대 {e['night_ret'].max():+.2f}%")
print(f"\n  → 이 범위를 벗어나면 사이트에서 '보증 불가' 경고를 띄웁니다")
