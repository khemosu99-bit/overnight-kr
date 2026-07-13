"""
간밤 해외지표 수집기 v2
- 공급처 이중화: Yahoo(1순위) → Stooq(2순위)
- 수입검사(IQC): 진짜 주가표인지 확인한 뒤에만 입고
- 불합격 시 '서버가 실제로 뭐라고 답했는지' 로그에 남긴다
"""
import io
import pathlib
import datetime

import pandas as pd
import requests
import yfinance as yf

# 이름      (야후 심볼,  스투 심볼)
SYMBOLS = {
    "EWY":    ("EWY",   "ewy.us"),    # 미국상장 한국ETF ⭐
    "SOX":    ("^SOX",  "^sox"),      # 필라델피아 반도체 ⭐
    "SP500":  ("^GSPC", "^spx"),
    "NASDAQ": ("^IXIC", "^ndq"),
    "DOW":    ("^DJI",  "^dji"),
    "VIX":    ("^VIX",  "^vix"),
    "USDKRW": ("KRW=X", "usdkrw"),
    "KOSPI":  ("^KS11", "^kospi"),
    "KOSDAQ": ("^KQ11", "^kosdaq"),
}

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

MUST_HAVE = {"Date", "Open", "High", "Low", "Close"}
MIN_ROWS = 100


def iqc(df: pd.DataFrame) -> pd.DataFrame:
    """수입검사. 불합격이면 예외를 던진다."""
    if df is None or df.empty:
        raise ValueError("빈 데이터")
    missing = MUST_HAVE - set(df.columns)
    if missing:
        raise ValueError(f"컬럼 누락 {sorted(missing)} / 실제={list(df.columns)[:8]}")
    if len(df) < MIN_ROWS:
        raise ValueError(f"행수 부족 ({len(df)}행 < {MIN_ROWS}행)")
    if df["Close"].isna().all():
        raise ValueError("종가가 전부 비어있음")
    return df


def from_yahoo(sym: str) -> pd.DataFrame:
    df = yf.download(sym, period="max", interval="1d",
                     auto_adjust=False, progress=False, threads=False)
    if df is None or df.empty:
        raise ValueError("야후 빈 응답")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.reset_index()


def from_stooq(sym: str) -> pd.DataFrame:
    r = requests.get("https://stooq.com/q/d/l/",
                     params={"s": sym, "i": "d"},
                     headers={"User-Agent": "Mozilla/5.0"},
                     timeout=30)
    head = r.text.lstrip()[:60].replace("\n", " ")
    if not head.lower().startswith("date,"):
        # ⭐ 서버가 실제로 뭐라고 답했는지 그대로 보여준다
        raise ValueError(f"CSV 아님 → 서버응답: {head!r}")
    return pd.read_csv(io.StringIO(r.text))


def main():
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    print(f"수집 시작 (KST {kst:%Y-%m-%d %H:%M})\n")

    ok, fail = [], []
    for name, (ysym, ssym) in SYMBOLS.items():
        print(f"── {name} " + "─" * 50)
        df, used, errs = None, None, []

        for label, fn, sym in (("Yahoo", from_yahoo, ysym),
                               ("Stooq", from_stooq, ssym)):
            try:
                df = iqc(fn(sym))
                used = label
                break
            except Exception as e:
                errs.append(f"{label}({sym}): {e}")
                df = None

        if df is None:
            for e in errs:
                print(f"   ❌ {e}")
            fail.append(name)
            continue

        path = RAW / f"{name}.csv"
        df.to_csv(path, index=False)
        last = df.iloc[-1]
        print(f"   ✅ {used} 사용 | {len(df):,}행 | "
              f"최신 {str(last['Date'])[:10]} 종가 {float(last['Close']):,.2f}")
        ok.append(name)

    print("\n" + "=" * 60)
    print(f"  ✅ 합격 {len(ok)}/{len(SYMBOLS)}: {', '.join(ok) if ok else '없음'}")
    if fail:
        print(f"  ❌ 불합격: {', '.join(fail)}")
    print("=" * 60)

    if not ok:
        raise SystemExit("전 항목 불합격 — 저장하지 않았습니다.")


if __name__ == "__main__":
    main()
