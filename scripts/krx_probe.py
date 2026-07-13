"""
KRX 탐침(probe)
- 어떤 API가 열려 있는지 전부 두드려보고 표로 보고한다
- 200이 뜬 것은 원본을 통째로 저장한다 (파싱은 나중에)
"""
import os
import json
import pathlib
import datetime
import requests

AUTH = os.environ.get("KRX_AUTH_KEY", "").strip()
BASE = "https://data-dbg.krx.co.kr/svc/apis"

# (분류, 이름, 경로)
TARGETS = [
    ("지수",     "KRX 지수 일별시세",   "/idx/krx_dd_trd"),
    ("지수",     "KOSPI 지수 일별시세", "/idx/kospi_dd_trd"),
    ("지수",     "KOSDAQ 지수 일별시세","/idx/kosdaq_dd_trd"),
    ("파생상품", "선물 일별매매정보",   "/drv/fut_bydd_trd"),
    ("파생상품", "옵션 일별매매정보",   "/drv/opt_bydd_trd"),
    ("주식",     "유가증권 일별매매",   "/sto/stk_bydd_trd"),
]

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "krx"
RAW.mkdir(parents=True, exist_ok=True)


def target_date():
    """직전 영업일(주말 제외). KRX는 익일 08시 갱신."""
    d = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    d -= datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y%m%d")


def probe(path, bas_dd):
    r = requests.post(
        BASE + path,
        headers={"AUTH_KEY": AUTH, "Content-Type": "application/json"},
        json={"basDd": bas_dd},
        timeout=30,
    )
    return r


def main():
    if not AUTH:
        raise SystemExit("❌ KRX_AUTH_KEY 시크릿이 비어 있습니다.")

    bas_dd = target_date()
    print(f"📅 기준일: {bas_dd}   (KRX는 전일자료를 익일 08시에 갱신)\n")
    print(f"  {'분류':<8} {'API 이름':<22} {'결과':<8} 비고")
    print("  " + "─" * 72)

    opened = []
    for cat, name, path in TARGETS:
        try:
            r = probe(path, bas_dd)
        except Exception as e:
            print(f"  {cat:<8} {name:<22} {'통신오류':<8} {e}")
            continue

        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                print(f"  {cat:<8} {name:<22} {'⚠️응답이상':<8} JSON 아님")
                continue

            rows = data.get("OutBlock_1") or data.get("outBlock_1") or []
            fn = path.strip("/").replace("/", "_")
            (RAW / f"{fn}_{bas_dd}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  {cat:<8} {name:<22} {'✅ 열림':<8} {len(rows):,}건 저장")
            opened.append((name, path, rows))

        elif r.status_code == 401:
            print(f"  {cat:<8} {name:<22} {'🔒 미승인':<8} 이 API는 신청 안 됨")
        elif r.status_code == 404:
            print(f"  {cat:<8} {name:<22} {'❔ 없음':<8} 경로가 다름")
        else:
            print(f"  {cat:<8} {name:<22} {'❌ ' + str(r.status_code):<8} {r.text[:60]}")

    print("\n" + "═" * 76)
    if not opened:
        raise SystemExit("❌ 열린 API가 없습니다. KRX '이용현황'에서 승인 상태를 확인하세요.")

    # 열린 API의 필드 구조를 보여준다 → 이걸로 파서를 만든다
    for name, path, rows in opened:
        print(f"\n▼ [{name}]  필드 구조")
        if not rows:
            print("   (해당일 데이터 없음 — 휴장일이거나 갱신 전)")
            continue
        print(f"   컬럼: {list(rows[0].keys())}\n")
        # 코스피/코스닥/코스피200 관련 행만 골라 보여준다
        kw = ("코스피", "코스닥", "KOSPI", "KOSDAQ", "200")
        hits = [r for r in rows
                if any(k in str(v) for v in r.values() for k in kw)][:6]
        for r in (hits or rows[:3]):
            print("   " + json.dumps(r, ensure_ascii=False)[:150])

    print("\n✅ 탐침 완료. 위 '필드 구조'를 그대로 복사해서 알려주세요.")


if __name__ == "__main__":
    main()
