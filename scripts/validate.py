"""
검증기 v3
1) 최근 데이터 이상 점검 (실시간 운영 가능성)
2) SOX가 S&P 대비 추가 정보를 주는가 (중복 제거)
3) 시대별 안정성 (지금도 유효한가)
4) 검증 vs 시험 분할 (과최적화 확인)
"""
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def load(name, start="2010-01-01"):
    df = pd.read_csv(RAW / f"{name}.csv", parse_dates=["Date"])
    df["Date"] = df["Date"].dt.tz_localize(None).dt.normalize()
    df = df.sort_values("Date").dropna(subset=["Close"])
    return df[df["Date"] >= start].reset_index(drop=True)


def build():
    base = None
    for m in ["KOSPI", "KOSDAQ"]:
        d = load(m)[["Date", "Close"]].copy()
        d[f"{m}_ret"] = d["Close"].pct_change() * 100
        d = d[["Date", f"{m}_ret"]]
        base = d if base is None else base.merge(d, on="Date", how="outer")
    base = base.sort_values("Date")

    for us in ["SOX", "SP500", "NASDAQ", "EWY"]:
        u = load(us)[["Date", "Close"]].copy()
        u[f"{us}_pct"] = u["Close"].pct_change() * 100
        u = u[["Date", f"{us}_pct"]].dropna().sort_values("Date")
        base = pd.merge_asof(base, u, on="Date", direction="backward",
                             allow_exact_matches=False)
    return base.dropna(subset=["KOSPI_ret", "SOX_pct", "SP500_pct"])


def tstat(s):
    s = s.dropna()
    if len(s) < 20:
        return np.nan, len(s)
    return s.mean() / (s.std() / np.sqrt(len(s))), len(s)


# ══════ 검사 1. 최근 데이터 이상 (가장 중요) ══════
def recent_check():
    print("=" * 76)
    print("  【검사 1】 최근 데이터 신뢰성  ← 실시간 운영 가능 여부")
    print("=" * 76)
    for m in ["KOSPI", "KOSDAQ"]:
        df = load(m, "2024-01-01")
        df["ret"] = df["Close"].pct_change() * 100
        print(f"\n  ── {m} 최근 2년 ──")
        big = df[df["ret"].abs() > 4][["Date", "Close", "ret"]]
        print(f"    |일간등락| > 4% 인 날: {len(big)}일 / {len(df)}일")
        if len(big):
            print("    (많으면 데이터 오류 의심)")
            for _, r in big.tail(10).iterrows():
                print(f"      {r['Date']:%Y-%m-%d}  종가 {r['Close']:>9,.2f}  {r['ret']:>+7.2f}%")

        d = load(m, "2026-06-01")
        print(f"\n    ── 최근 원자료 (직접 확인용) ──")
        print(d.tail(12)[["Date", "Open", "High", "Low", "Close"]]
              .to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


# ══════ 검사 2. SOX는 S&P 대비 추가 정보를 주는가 ══════
def incremental(df):
    print("\n\n" + "=" * 76)
    print("  【검사 2】 SOX가 S&P500 대비 '추가' 정보를 주는가")
    print("  → S&P를 고정하고 SOX만 다를 때 결과가 갈리는지 본다")
    print("=" * 76)
    mild = df["SP500_pct"].abs() < 0.5        # S&P는 조용했던 날만
    for lo, hi, lab in [(1.5, 99, "SOX 큰 상승 (+1.5%↑)"),
                        (-99, -1.5, "SOX 큰 하락 (-1.5%↓)")]:
        m = mild & df["SOX_pct"].between(lo, hi)
        t, n = tstat(df[m]["KOSPI_ret"])
        up = (df[m]["KOSPI_ret"] > 0).mean() * 100 if n else np.nan
        mark = "⭐" if abs(t) >= 2 else "  "
        print(f"\n  S&P 보합(±0.5%) & {lab}")
        print(f"    {n:>4}회 | 평균 {df[m]['KOSPI_ret'].mean():>+6.2f}% | "
              f"상승 {up:>5.1f}% | t={t:>+5.1f} {mark}")
    print("\n  ⭐가 있으면 → SOX 고유의 정보력 있음 (반도체=코스피 핵심)")
    print("  ⭐가 없으면 → SOX는 그냥 미국장 대리변수. S&P만 써도 됨")


# ══════ 검사 3. 시대별 안정성 ══════
def regime(df):
    print("\n\n" + "=" * 76)
    print("  【검사 3】 시대별 안정성  ← 지금도 유효한가?")
    print("=" * 76)
    eras = [("2010-2015", "2010-01-01", "2015-12-31"),
            ("2016-2020", "2016-01-01", "2020-12-31"),
            ("2021-2026", "2021-01-01", "2026-12-31")]
    print(f"\n  {'시기':<12} {'SOX+2%→KOSPI':>22} {'SOX-2%→KOSPI':>22}")
    print("  " + "-" * 60)
    for lab, s, e in eras:
        d = df[(df["Date"] >= s) & (df["Date"] <= e)]
        out = [lab]
        for cond in [d["SOX_pct"] >= 2, d["SOX_pct"] <= -2]:
            sub = d[cond]["KOSPI_ret"]
            t, n = tstat(sub)
            out.append(f"{sub.mean():+.2f}% ({n}회,t={t:+.1f})" if n >= 20 else "표본부족")
        print(f"  {out[0]:<12} {out[1]:>22} {out[2]:>22}")
    print("\n  → 세 시기 모두 같은 방향이면 안정. 최근이 약해지면 효과 소멸 중")


# ══════ 검사 4. 검증/시험 분할 ══════
def holdout(df):
    print("\n\n" + "=" * 76)
    print("  【검사 4】 과최적화 확인  (앞 70%로 정하고, 뒤 30%로 시험)")
    print("=" * 76)
    cut = df["Date"].quantile(0.7)
    for lab, d in [("학습구간(앞70%)", df[df["Date"] <= cut]),
                   ("시험구간(뒤30%)", df[df["Date"] > cut])]:
        print(f"\n  ── {lab}  ({d['Date'].min():%Y-%m} ~ {d['Date'].max():%Y-%m}) ──")
        for cond, name in [(d["SOX_pct"] >= 2, "SOX +2%↑"),
                           (d["SOX_pct"] <= -2, "SOX -2%↓")]:
            sub = d[cond]["KOSPI_ret"]
            t, n = tstat(sub)
            up = (sub > 0).mean() * 100 if n else np.nan
            mark = "⭐" if abs(t) >= 2 else "  "
            print(f"    {name:<10} {n:>4}회 | 평균 {sub.mean():>+6.2f}% | "
                  f"상승 {up:>5.1f}% | t={t:>+5.1f} {mark}")
    print("\n  → 시험구간에서도 ⭐면 진짜. 무너지면 과거에만 통한 것")


if __name__ == "__main__":
    recent_check()
    df = build()
    incremental(df)
    regime(df)
    holdout(df)
