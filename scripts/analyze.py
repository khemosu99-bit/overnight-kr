"""
갭 통계 분석기
- 간밤 미국 지표(전일) → 다음날 한국 시가 갭(당일) 의 관계를 통계로 뽑는다
- 전망하지 않는다. 과거 사실만 센다.
"""
import pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def load(name):
    df = pd.read_csv(RAW / f"{name}.csv", parse_dates=["Date"])
    df = df[["Date", "Open", "Close"]].dropna()
    df["Date"] = df["Date"].dt.tz_localize(None).dt.normalize()
    return df.sort_values("Date").reset_index(drop=True)


def build(kr_name="KOSPI"):
    kr = load(kr_name).rename(columns={"Open": "kr_open", "Close": "kr_close"})

    # 한국: 전일 종가 → 당일 시가 = 갭
    kr["prev_close"] = kr["kr_close"].shift(1)
    kr["gap_pct"] = (kr["kr_open"] / kr["prev_close"] - 1) * 100
    # 시가 → 종가 = 장중 흐름 (갭을 지켰는지)
    kr["intra_pct"] = (kr["kr_close"] / kr["kr_open"] - 1) * 100

    # 미국 지표들의 '전일 등락률'을 붙인다
    for us in ["SOX", "EWY", "NASDAQ", "SP500", "VIX"]:
        u = load(us)
        u[f"{us}_pct"] = (u["Close"] / u["Close"].shift(1) - 1) * 100
        u = u[["Date", f"{us}_pct"]]
        # 미국 T일 종가 → 한국 T+1일 시가에 대응 (merge_asof)
        kr = pd.merge_asof(
            kr, u.sort_values("Date"),
            on="Date", direction="backward", allow_exact_matches=False,
        )

    return kr.dropna(subset=["gap_pct", "SOX_pct", "EWY_pct"])


def report(df, label, mask):
    sub = df[mask]
    n = len(sub)
    if n < 10:
        print(f"\n[{label}]  표본 부족 ({n}건)")
        return
    up = (sub["gap_pct"] > 0).sum()
    held = (sub["intra_pct"] > 0).sum()
    print(f"\n[{label}]")
    print(f"  과거 발생        {n:>6}회")
    print(f"  갭상승 출발      {up:>6}회  ({up/n*100:.1f}%)")
    print(f"  평균 시가 갭     {sub['gap_pct'].mean():>+6.2f}%")
    print(f"  중앙값 갭        {sub['gap_pct'].median():>+6.2f}%")
    print(f"  최대/최소        {sub['gap_pct'].max():+.2f}% / {sub['gap_pct'].min():+.2f}%")
    print(f"  ⚠️ 시가 후 상승   {held:>6}회  ({held/n*100:.1f}%)  ← 갭을 지켰나")


def main():
    for market in ["KOSPI", "KOSDAQ"]:
        df = build(market)
        print("\n" + "=" * 62)
        print(f"  {market}  |  분석 표본 {len(df):,}일  "
              f"({df['Date'].min():%Y-%m-%d} ~ {df['Date'].max():%Y-%m-%d})")
        print("=" * 62)

        print(f"\n  ── 전체 기준선 ──")
        print(f"  전체 평균 갭     {df['gap_pct'].mean():+.2f}%")
        print(f"  전체 갭상승률    {(df['gap_pct'] > 0).mean()*100:.1f}%")

        report(df, "간밤 SOX(반도체) +2% 이상", df["SOX_pct"] >= 2)
        report(df, "간밤 SOX(반도체) -2% 이하", df["SOX_pct"] <= -2)
        report(df, "간밤 EWY(한국ETF) +1.5% 이상", df["EWY_pct"] >= 1.5)
        report(df, "간밤 EWY(한국ETF) -1.5% 이하", df["EWY_pct"] <= -1.5)
        report(df, "⭐ SOX +2% & EWY +1.5% 동시",
               (df["SOX_pct"] >= 2) & (df["EWY_pct"] >= 1.5))
        report(df, "⭐ SOX -2% & EWY -1.5% 동시",
               (df["SOX_pct"] <= -2) & (df["EWY_pct"] <= -1.5))


if __name__ == "__main__":
    main()
