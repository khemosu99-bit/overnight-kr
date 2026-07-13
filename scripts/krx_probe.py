"""
KRX 탐침 v2
- 데이터가 나올 때까지 날짜를 거슬러 올라간다 (휴장일 자동 회피)
- 승인된 API의 필드 구조를 정확히 보고한다
"""
import os
import json
import pathlib
import datetime
import requests

AUTH = os.environ.get("KRX_AUTH_KEY", "").strip()
BASE = "https://data-dbg.krx.co.kr/svc/apis"

TARGETS = [
    ("KOSPI 지수",   "/idx/kospi_dd_trd"),
    ("KOSDAQ 지수",  "/idx/kosdaq_dd_trd"),
    ("선물",         "/drv/fut_bydd_trd"),
]

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "krx"
RAW.mkdir(parents=True, exist_ok=True)


def call(path, bas_dd):
    r = requests.post(
        BASE + path,
        headers={"AUTH_KEY": AUTH, "Content-Type": "application/json"},
        json={"basDd": bas_dd},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    data = r.json()
    return data, (data.get("OutBlock_1") or data.get("outBlock_1") or [])


def main():
    if not AUTH:
        raise SystemExit("❌ KRX_AUTH_KEY 시크릿이 비어 있습니다.")

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    print(f"🕘 현재 KST 날짜: {today}\n")

    for label, path in TARGETS:
        print("═" * 74)
        print(f"  ▼ {label}   ({path})")
        print("═" * 74)

        found = False
        for back in range(1, 11):          # 최대 10일 거슬러 올라감
            d = today - datetime.timedelta(days=back)
            bas_dd = d.strftime("%Y%m%d")
            wd = "월화수목금토일"[d.weekday()]

            try:
                data, rows = call(path, bas_dd)
            except Exception as e:
                print(f"    {bas_dd}({wd})  ❌ {e}")
                break

            if not rows:
                print(f"    {bas_dd}({wd})  ─ 0건 (휴장/미갱신)")
                continue

            # ── 데이터 발견 ──
            print(f"    {bas_dd}({wd})  ✅ {len(rows):,}건 발견!\n")
            fn = path.strip("/").replace("/", "_")
            (RAW / f"{fn}_{bas_dd}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"    【컬럼 목록】")
            for k in rows[0].keys():
                print(f"      · {k}")

            print(f"\n    【샘플 데이터】")
            kw = ("코스피 200", "코스피200", "KOSPI 200", "코스피", "코스닥")
            hits = [r for r in rows
                    if any(k in str(v) for v in r.values() for k in kw)]
            for r in (hits[:5] or rows[:3]):
                print("      " + json.dumps(r, ensure_ascii=False)[:170])

            found = True
            break

        if not found:
            print("    ⚠️ 10일간 데이터 없음 — 갱신 지연 또는 권한 문제")
        print()

    print("✅ 탐침 완료. 위 【컬럼 목록】과 【샘플 데이터】를 복사해 주세요.")


if __name__ == "__main__":
    main()
