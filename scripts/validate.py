"""
데이터 검증기 — 계측기 영점 조정
시가(Open) 데이터를 신뢰할 수 있는지 물리적으로 검사한다.
"""
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def load(name):
    df = pd.read_csv(RAW / f"{name}.csv", parse_dates=["Date"])
    df["Date"] = df["Date"].dt.tz_localize(None).dt.normalize()
    return df.sort_values("Date").dropna(subset=["Open", "Close"]).reset_index(drop=True)


def check(name):
    df = load(name)
    df["prev_close"] = df["Close"].shift(1)
    df = df.dropna(subset=["prev_close"])

    gap = df["Open"] / df["prev_close"] - 1
    intra = df["Close"] / df["Open"] - 1

    n = len(df)
    gap_cum = np.exp(np.log1p(gap).sum())
    intra_cum = np.exp(np.log1p(intra).sum())
    actual = df["Close"].iloc[-1] / df["Close"].iloc[0]

    print("\n" + "=" * 66)
    print(f"  {name}   {df['Date'].iloc[0]:%Y-%m-%d} ~ {df['Date'].iloc[-1]:%Y-%m-%d}  ({n:,}일)")
    print("=" * 66)

    print("\n  【검사 1】 물리 정합성  — 갭 × 장중 = 실제여야 함")
    print(f"    갭만 누적       {gap_cum:>18,.1f} 배")
    print(f"    장중만 누적     {intra_cum:>18,.4f} 배")
    print(f"    갭 × 장중       {gap_cum * intra_cum:>18,.2f} 배")
    print(f"    실제 지수 상승  {actual:>18,.2f} 배")
    ratio = gap_cum / actual if actual else float("inf")
    verdict = "🚨 오염 의심" if ratio > 5 or ratio < 0.2 else "✅ 정상 범위"
    print(f"    → 갭누적 / 실제 = {ratio:,.1f} 배   {verdict}")

    print("\n  【검사 2】 갭 방향 편향  — 50% 근처여야 정상")
    up = (gap > 0).mean() * 100
    v2 = "🚨 비정상" if abs(up - 50) > 8 else "✅ 정상"
    print(f"    갭상승 비율     {up:>6.1f}%   {v2}")

    print("\n  【검사 3】 시가 이상 패턴")
    print(f"    Open == 전일종가  {(df['Open'] == df['prev_close']).mean()*100:>6.2f}%")
    print(f"    Open == 당일저가  {(df['Open'] == df['Low']).mean()*100:>6.2f}%")
    print(f"    Open == 당일고가  {(df['Open'] == df['High']).mean()*100:>6.2f}%")
    print(f"    Open == 당일종가  {(df['Open'] == df['Close']).mean()*100:>6.2f}%")

    print("\n  【검사 4】 최근 8일 원자료 — 눈으로 확인")
    print(df.tail(8)[["Date", "Open", "High", "Low", "Close"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    for m in ["KOSPI", "KOSDAQ", "SP500", "EWY"]:
        check(m)
    print("\n\n💡 SP500·EWY(미국)는 '정상'이 나와야 합니다.")
    print("   미국은 정상인데 한국만 '오염 의심'이면 → 한국 시가 데이터 문제 확정.")
