"""
검증기 v2 + 신뢰 가능한 분석
- 검사 스펙을 올바르게 재설계
- Open을 쓰지 않는 '종가 기준' 분석으로 결론을 낸다
"""
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
START = "2010-01-01"          # 옛 구간 결함 회피


def load(name):
    df = pd.read_csv(RAW / f"{name}.csv", parse_dates=["Date"])
    df["Date"] = df["Date"].dt.tz_localize(None).dt.normalize()
    df = df.sort_values("Date").dropna(subset=["Close"])
    return df[df["Date"] >= START].reset_index(drop=True)


# ══════════ PART A. 데이터 품질 검사 (올바른 스펙) ══════════
def quality(name):
    df = load(name)
    if len(df) < 100:
        print(f"\n  {name}: 데이터 부족")
        return

    ret = df["Close"].pct_change().dropna() * 100
    print(f"\n  ── {name}  ({len(df):,}일, {START} 이후) ──")
    print(f"    일간 변동성(표준편차)   {ret.std():>6.2f}%")
    print(f"    |일간등락| > 5% 인 날    {(ret.abs() > 5).mean()*100:>6.2f}%   (정상: 1% 미만)")
    print(f"    |일간등락| > 3% 인 날    {(ret.abs() > 3).mean()*100:>6.2f}%   (정상: 3% 미만)")

    if {"Open", "High", "Low"} <= set(df.columns):
        dup_h = (df["High"] == df["High"].shift(1)).mean() * 100
        eq_oc = (df["Open"] == df["Close"]).mean() * 100
        gap_up = (df["Open"] / df["Close"].shift(1) > 1).mean() * 100
        print(f"    전일과 고가 중복        {dup_h:>6.2f}%   (정상: 1% 미만)")
        print(f"    시가 == 종가            {eq_oc:>6.2f}%   (정상: 1% 미만)")
        print(f"    갭상승 비율             {gap_up:>6.1f}%   (정상: 45~55%)")

        bad = (ret.abs() > 5).mean() > 0.01 or dup_h > 1 or abs(gap_up - 50) > 8
        print(f"    ▶ 판정: {'❌ 사용 불가' if bad else '✅ 사용 가능'}")


# ══════════ PART B. Open 없는 분석 (신뢰 가능) ══════════
def build():
    kr = {}
    for m in ["KOSPI", "KOSDAQ"]:
        d = load(m)[["Date", "Close"]].rename(columns={"Close": m})
        kr[m] = d

    base = kr["KOSPI"].merge(kr["KOSDAQ"], on="Date", how="outer").sort_values("Date")
    for m in ["KOSPI", "KOSDAQ"]:
        base[f"{m}_ret"] = base[m].pct_change() * 100

    for us in ["SOX", "EWY", "NASDAQ", "SP500"]:
        u = load(us)[["Date", "Close"]].copy()
        u[f"{us}_pct"] = u["Close"].pct_change() * 100
        u = u[["Date", f"{us}_pct"]].dropna().sort_values("Date")
        base = pd.merge_asof(base, u, on="Date", direction="backward",
                             allow_exact_matches=False)
    return base.dropna(subset=["KOSPI_ret", "SOX_pct", "EWY_pct"])


def stat(df, target, label, mask):
    sub = df[mask][target].dropna()
    n = len(sub)
    if n < 30:
        print(f"    {label:<32} 표본부족({n})")
        return
    hit = (sub > 0).mean() * 100
    se = sub.std() / np.sqrt(n)
    t = sub.mean() / se if se else 0
    sig = "⭐" if abs(t) >= 2 else "  "
    print(f"    {label:<32} {n:>5}회 | 평균 {sub.mean():>+6.2f}% | "
          f"상승 {hit:>5.1f}% | t={t:>+5.1f} {sig}")


def main():
    print("=" * 78)
    print("  PART A. 데이터 품질 검사")
    print("=" * 78)
    for m in ["EWY", "SOX", "SP500", "NASDAQ", "KOSPI", "KOSDAQ"]:
        quality(m)

    df = build()
    print("\n\n" + "=" * 78)
    print(f"  PART B. 종가→종가 분석  (Open 미사용 = 오염 무관)")
    print(f"  표본 {len(df):,}일  |  t값 절대치 2 이상이면 통계적으로 유의(⭐)")
    print("=" * 78)

    for target, name in [("KOSPI_ret", "KOSPI"), ("KOSDAQ_ret", "KOSDAQ")]:
        print(f"\n  【{name} 다음날 종가 등락률】")
        stat(df, target, "◽ 기준선 (전체 평균)", pd.Series(True, index=df.index))
        stat(df, target, "간밤 SOX +2% 이상", df["SOX_pct"] >= 2)
        stat(df, target, "간밤 SOX -2% 이하", df["SOX_pct"] <= -2)
        stat(df, target, "간밤 EWY +1.5% 이상", df["EWY_pct"] >= 1.5)
        stat(df, target, "간밤 EWY -1.5% 이하", df["EWY_pct"] <= -1.5)
        stat(df, target, "SOX+2% & EWY+1.5% 동시", (df["SOX_pct"] >= 2) & (df["EWY_pct"] >= 1.5))
        stat(df, target, "SOX-2% & EWY-1.5% 동시", (df["SOX_pct"] <= -2) & (df["EWY_pct"] <= -1.5))


if __name__ == "__main__":
    main()
