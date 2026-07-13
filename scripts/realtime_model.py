"""
Model 2 — 07:00 골든타임 모델
※ 그 시각에 실제로 손에 있는 데이터만 쓴다 (미국 지표)
※ 타깃은 KRX 공식 코스피/코스닥 (오염 없음)
"""
import json
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

US = ["EWY", "SOX", "SP500", "NASDAQ", "VIX", "USDKRW"]


def load_us(name):
    d = pd.read_csv(RAW / f"{name}.csv", parse_dates=["Date"])
    d["Date"] = d["Date"].dt.tz_localize(None).dt.normalize()
    d = d[["Date", "Close"]].dropna().sort_values("Date")
    d[f"{name}_r"] = d["Close"].pct_change() * 100
    return d[["Date", f"{name}_r"]].dropna().rename(columns={"Date": "date"})


# ── 한국 (KRX 공식) ──
kr = pd.read_csv(ROOT / "data" / "kr_index.csv", parse_dates=["date"]).sort_values("date")
nf = pd.read_csv(ROOT / "data" / "night_futures.csv", parse_dates=["date"])
nf = nf[["date", "night_close", "reg_close"]].sort_values("date")

d = kr.merge(nf, on="date", how="inner")
for m in ["kospi", "kosdaq"]:
    p = d[f"{m}_close"].shift(1)
    d[f"{m}_gap"] = (d[f"{m}_open"] / p - 1) * 100
    d[f"{m}_close_r"] = (d[f"{m}_close"] / p - 1) * 100
    d[f"{m}_intra"] = (d[f"{m}_close"] / d[f"{m}_open"] - 1) * 100

d["night_r"] = (d["night_close"] / d["reg_close"].shift(1) - 1) * 100
d["rv20"] = d["kospi_close_r"].rolling(20).std()

# ── 미국 지표 붙이기 (전일 미국장 = 오늘 새벽 마감분) ──
for u in US:
    d = pd.merge_asof(d.sort_values("date"), load_us(u),
                      on="date", direction="backward", allow_exact_matches=False)

e = d.dropna(subset=["kospi_gap", "kospi_close_r", "EWY_r", "SOX_r", "rv20"]).copy()


def ols(X, y):
    """X: (n,k) DataFrame, y: Series → 계수, R², 잔차σ"""
    A = np.column_stack([np.ones(len(X)), X.values])
    coef, *_ = np.linalg.lstsq(A, y.values, rcond=None)
    pred = A @ coef
    res = y.values - pred
    r2 = 1 - (res ** 2).sum() / ((y.values - y.mean()) ** 2).sum()
    return coef, r2, res.std()


print("=" * 82)
print(f"  Model 2 검증  |  {e['date'].min():%Y-%m-%d} ~ {e['date'].max():%Y-%m-%d} ({len(e)}일)")
print("  ⚠️ 07:00 KST에 실제로 손에 있는 데이터만 사용")
print("=" * 82)

# ── 【1】 단일 변수 ──
print("\n【1】 미국 지표 하나씩 → 코스피")
print(f"  {'입력':<12} {'→ 갭 R²':>10} {'→ 종가 R²':>11} {'상관(갭)':>10}")
print("  " + "-" * 46)
for u in US:
    if f"{u}_r" not in e:
        continue
    s = e.dropna(subset=[f"{u}_r"])
    _, r2g, _ = ols(s[[f"{u}_r"]], s["kospi_gap"])
    _, r2c, _ = ols(s[[f"{u}_r"]], s["kospi_close_r"])
    c = s[[f"{u}_r", "kospi_gap"]].corr().iloc[0, 1]
    print(f"  {u:<12} {r2g:>10.3f} {r2c:>11.3f} {c:>10.3f}")

# ── 【2】 조합 모델 ──
print("\n【2】 조합 모델 (다중회귀)")
COMBOS = [
    (["EWY_r"], "EWY 단독"),
    (["EWY_r", "SOX_r"], "EWY + SOX"),
    (["EWY_r", "SOX_r", "NASDAQ_r"], "EWY + SOX + 나스닥"),
    (["EWY_r", "SOX_r", "NASDAQ_r", "USDKRW_r"], "EWY + SOX + 나스닥 + 환율"),
]
print(f"  {'모델':<26} {'갭 R²':>8} {'갭 ±80%':>10} {'종가 R²':>9} {'종가 ±80%':>11}")
print("  " + "-" * 68)
best = None
for cols, lab in COMBOS:
    if not all(c in e for c in cols):
        continue
    s = e.dropna(subset=cols)
    cg, r2g, seg = ols(s[cols], s["kospi_gap"])
    cc, r2c, sec = ols(s[cols], s["kospi_close_r"])
    print(f"  {lab:<26} {r2g:>8.3f} ±{1.28*seg:>7.2f}%p {r2c:>9.3f} ±{1.28*sec:>8.2f}%p")
    if best is None or r2g > best[1]:
        best = (cols, r2g, cg, seg, cc, r2c, sec, lab)

# ── 【3】 천장 비교 ──
print("\n【3】 천장 비교  ← Model 1(야간선물)에 얼마나 근접하나")
s = e.dropna(subset=["night_r"])
_, r2n_g, sen_g = ols(s[["night_r"]], s["kospi_gap"])
_, r2n_c, sen_c = ols(s[["night_r"]], s["kospi_close_r"])
print(f"  Model 1 (야간선물, 07시엔 없음)   갭 R² {r2n_g:.3f}   종가 R² {r2n_c:.3f}")
print(f"  Model 2 ({best[7]})".ljust(36) + f"갭 R² {best[1]:.3f}   종가 R² {best[5]:.3f}")
print(f"\n  → Model 2가 Model 1의 {best[1]/r2n_g*100:.0f}% 수준을 회복")

# ── 【4】 장중 (예측 안 함 확인) ──
print("\n【4】 장중 흐름  ← 예측 불가 재확인")
for cols, lab in [(["EWY_r", "SOX_r"], "EWY+SOX"), (["night_r"], "야간선물")]:
    s = e.dropna(subset=cols)
    _, r2, _ = ols(s[cols], s["kospi_intra"])
    print(f"  {lab:<14} → 코스피 장중  R² {r2:.4f}")
print("  → 둘 다 0에 가까우면 '장중은 아무도 모른다' 확정")

# ── 【5】 과최적화 검증 ──
print("\n【5】 과최적화 검증 (앞60 학습 / 뒤40 시험)")
cut = e["date"].quantile(0.6)
cols = best[0]
for lab, s in [("학습", e[e["date"] <= cut]), ("시험", e[e["date"] > cut])]:
    s = s.dropna(subset=cols)
    _, r2g, _ = ols(s[cols], s["kospi_gap"])
    _, r2c, _ = ols(s[cols], s["kospi_close_r"])
    print(f"  {lab}  갭 R²={r2g:.3f}   종가 R²={r2c:.3f}   (n={len(s)})")
print("  → 시험구간에서 유지되면 진짜")

# ── 【6】 국면별 오차범위 ──
print("\n【6】 국면별 예측폭 (Model 2)")
lo, hi = e["rv20"].quantile([0.33, 0.67])
print(f"  {'국면':<12} {'n':>4} {'갭 R²':>8} {'갭 ±80%':>10} {'종가 ±80%':>11}")
print("  " + "-" * 48)
REG = {}
for lab, m in [("저변동", e["rv20"] <= lo),
               ("중변동", (e["rv20"] > lo) & (e["rv20"] < hi)),
               ("고변동", e["rv20"] >= hi)]:
    s = e[m].dropna(subset=cols)
    cg, r2g, seg = ols(s[cols], s["kospi_gap"])
    cc, r2c, sec = ols(s[cols], s["kospi_close_r"])
    REG[lab] = dict(n=len(s), gap_coef=cg.tolist(), gap_r2=round(r2g, 3),
                    gap_se=round(seg, 3), close_coef=cc.tolist(),
                    close_r2=round(r2c, 3), close_se=round(sec, 3))
    print(f"  {lab:<12} {len(s):>4} {r2g:>8.3f} ±{1.28*seg:>7.2f}%p ±{1.28*sec:>8.2f}%p")

# ── 모델 저장 ──
OUT = {
    "features": cols,
    "label": best[7],
    "gap": {"coef": best[2].tolist(), "r2": round(best[1], 3), "se": round(best[3], 3)},
    "close": {"coef": best[4].tolist(), "r2": round(best[5], 3), "se": round(best[6], 3)},
    "regimes": REG,
    "rv_lo": round(float(lo), 3), "rv_hi": round(float(hi), 3),
    "n": len(e),
    "start": e["date"].min().strftime("%Y-%m-%d"),
    "end": e["date"].max().strftime("%Y-%m-%d"),
    "range": {k: round(float(e[k].quantile(q)), 2)
              for k in cols for q in [0.05, 0.95]
              for k, q in [(k, q)]},
}
(ROOT / "data" / "model2.json").write_text(
    json.dumps(OUT, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n✅ data/model2.json 저장 완료")
