"""
간밤 해외지표 수집기
- Stooq에서 과거 전체 히스토리 CSV를 통째로 받아 저장한다
- 심볼이 틀리면 그 항목만 건너뛰고, 로그에 표시한다
"""
import pathlib
import datetime
import requests

# ── 수집 대상 ────────────────────────────────
SYMBOLS = {
    "EWY":    "ewy.us",    # 미국 상장 한국 ETF ⭐ 핵심
    "SOX":    "^sox",      # 필라델피아 반도체지수 ⭐ 핵심
    "SP500":  "^spx",
    "NASDAQ": "^ndq",
    "DOW":    "^dji",
    "VIX":    "^vix",
    "USDKRW": "usdkrw",
    "KOSPI":  "^kospi",
    "KOSDAQ": "^kosdaq",
}

BASE = "https://stooq.com/q/d/l/"
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)


def fetch(symbol: str) -> str:
    r = requests.get(
        BASE,
        params={"s": symbol, "i": "d"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    r.raise_for_status()
    text = r.text.strip()
    if len(text.splitlines()) < 2:
        raise ValueError(f"빈 응답 (심볼 오류 가능): {text[:40]!r}")
    return text


def main():
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    print(f"🕕 수집 시작 (KST {kst:%Y-%m-%d %H:%M})\n")
    print(f"  {'항목':<8} {'심볼':<10} {'행수':>7}   최신 데이터")
    print("  " + "-" * 62)

    ok, fail = [], []
    for name, sym in SYMBOLS.items():
        try:
            text = fetch(sym)
            (RAW / f"{name}.csv").write_text(text, encoding="utf-8")
            lines = text.splitlines()
            print(f"  ✅ {name:<8} {sym:<10} {len(lines)-1:>6}행   {lines[-1]}")
            ok.append(name)
        except Exception as e:
            print(f"  ❌ {name:<8} {sym:<10}   실패: {e}")
            fail.append(name)

    print("\n" + "=" * 66)
    print(f"  ✅ 성공 {len(ok)}개: {', '.join(ok) if ok else '없음'}")
    if fail:
        print(f"  ❌ 실패 {len(fail)}개: {', '.join(fail)}  → 심볼 수정 필요")
    print("=" * 66)

    if not ok:
        raise SystemExit("❌ 전부 실패했습니다.")


if __name__ == "__main__":
    main()
