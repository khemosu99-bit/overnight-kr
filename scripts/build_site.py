"""
nightgap.kr 사이트 빌더
- Yahoo 실시간 미국지표 → Model 2 환산 → 정적 HTML 생성
- 사용자 입력 0회. 열면 바로 답이 보인다.
"""
import json
import pathlib
import datetime
import numpy as np
import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)
BASE = "https://nightgap.kr"
UA = {"User-Agent": "Mozilla/5.0"}
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

M = json.loads((ROOT / "data" / "model2.json").read_text(encoding="utf-8"))
FEAT = M["features"]                       # ['EWY_r','SOX_r','NASDAQ_r',...]
SYM = {"EWY_r": "EWY", "SOX_r": "^SOX", "NASDAQ_r": "^IXIC",
       "SP500_r": "^GSPC", "USDKRW_r": "KRW=X", "VIX_r": "^VIX"}
NAME = {"EWY_r": "EWY (미국상장 한국ETF)", "SOX_r": "필라델피아 반도체",
        "NASDAQ_r": "나스닥", "SP500_r": "S&P 500",
        "USDKRW_r": "달러/원", "VIX_r": "VIX"}


# ═════ 1. 실시간 미국지표 ═════
def quote(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"interval": "1d", "range": "5d"},
                     headers=UA, timeout=20)
    res = r.json()["chart"]["result"][0]
    c = [x for x in res["indicators"]["quote"][0]["close"] if x]
    t = datetime.datetime.utcfromtimestamp(
        res["meta"]["regularMarketTime"]) + datetime.timedelta(hours=9)
    return {"price": c[-1], "pct": (c[-1] / c[-2] - 1) * 100, "at": t}


live, fail = {}, []
for f in FEAT:
    try:
        live[f] = quote(SYM[f])
        print(f"  ✅ {NAME[f]:<22} {live[f]['price']:>11,.2f}  {live[f]['pct']:+.2f}%")
    except Exception as e:
        fail.append(f)
        print(f"  ❌ {NAME[f]:<22} {e}")

# ═════ 2. 국면 판정 ═════
kr = pd.read_csv(ROOT / "data" / "kr_index.csv", parse_dates=["date"]).sort_values("date")
kr["r"] = kr["kospi_close"].pct_change() * 100
rv = float(kr["r"].rolling(20).std().iloc[-1])
regime = "저변동" if rv <= M["rv_lo"] else ("고변동" if rv >= M["rv_hi"] else "중변동")
R = M["regimes"][regime]

# ═════ 3. 환산 ═════
ok = not fail
gap = lo = hi = None
warn = None
if ok:
    x = [live[f]["pct"] for f in FEAT]
    gap = R["gap_coef"][0] + sum(c * v for c, v in zip(R["gap_coef"][1:], x))
    w = 1.28 * R["gap_se"]
    lo, hi = gap - w, gap + w
    # 학습범위 이탈 경고
    for f, v in zip(FEAT, x):
        k = f.replace("_r", "")
        if abs(v) > 6:
            warn = f"{NAME[f]} 등락({v:+.1f}%)이 과거 학습 범위를 크게 벗어납니다."

# ═════ 4. 자기채점 (최근 10일) ═════
nf = pd.read_csv(ROOT / "data" / "night_futures.csv", parse_dates=["date"])
kr2 = kr.copy()
kr2["gap"] = (kr2["kospi_open"] / kr2["kospi_close"].shift(1) - 1) * 100
recent = kr2.dropna(subset=["gap"]).tail(10)[["date", "gap"]]

# ═════ 5. HTML ═════
CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI','Malgun Gothic',sans-serif;line-height:1.7;
color:#16181d;background:#f5f6f8;padding:14px}
.w{max-width:680px;margin:0 auto}
header{padding:18px 0 6px}
h1{font-size:1.45rem;letter-spacing:-.02em}
.sub{color:#666;font-size:.86rem;margin-top:3px}
nav{margin-top:10px}nav a{color:#16181d;margin-right:14px;font-size:.86rem}
.card{background:#fff;border:1px solid #e3e5e9;border-radius:12px;padding:18px;margin:14px 0}
h2{font-size:1.05rem;margin-bottom:12px;padding-bottom:7px;border-bottom:2px solid #16181d;display:inline-block}
.hero{background:#16181d;color:#fff;border:0}
.hero h2{color:#fff;border-color:#fff}
.big{font-size:2.4rem;font-weight:700;letter-spacing:-.03em;margin:6px 0}
.rng{font-size:1rem;opacity:.9}
.meta{font-size:.8rem;opacity:.65;margin-top:10px}
.kv{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px dashed #eceef1;font-size:.9rem}
.kv:last-child{border:0}
.up{color:#c0392b}.dn{color:#1565c0}
.hero .up{color:#ff8a7a}.hero .dn{color:#7db8ff}
.warn{background:#fff8e6;border-color:#f0d9a0}
.warn h2{border-color:#c99700}
.stop{background:#fdf0f0;border-color:#e8c0c0}
.stop h2{border-color:#c0392b}
table{width:100%;border-collapse:collapse;font-size:.84rem;margin-top:6px}
th,td{padding:7px 5px;text-align:right;border-bottom:1px solid #f0f1f3}
th{background:#fafbfc;font-weight:600;color:#555}
td:first-child,th:first-child{text-align:left}
details{border-bottom:1px solid #eceef1;padding-bottom:6px}
summary{cursor:pointer;font-weight:600;padding:8px 0;font-size:.93rem}
details p{font-size:.88rem;color:#444;padding:2px 0 8px}
ul{margin-left:18px;font-size:.9rem}li{margin:5px 0}
footer{text-align:center;color:#8a8f98;font-size:.78rem;padding:26px 0;line-height:1.9}
.badge{display:inline-block;padding:2px 9px;border-radius:99px;background:#16181d;color:#fff;font-size:.72rem}
"""


def page(title, desc, body, path):
    html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="{BASE}/{path}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:type" content="website"><meta property="og:url" content="{BASE}/{path}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<style>{CSS}</style></head><body><div class="w">
<header><h1>야간 갭 (nightgap)</h1>
<div class="sub">간밤 해외 지표로 오늘 코스피 개장 갭을 환산합니다 · KRX 공식 데이터</div>
<nav><a href="/">대시보드</a><a href="/guide.html">야간선물 제도</a><a href="/methodology.html">방법론·한계</a></nav>
</header>{body}
<footer>데이터: 한국거래소(KRX) Open API · Yahoo Finance<br>
본 사이트는 과거 데이터의 통계적 관계만 계산합니다.<br>
투자 조언이나 매매 권유가 아니며, 투자 판단의 근거로 사용될 수 없습니다.<br>
갱신 {KST:%Y-%m-%d %H:%M} KST</footer></div></body></html>"""
    (SITE / path).write_text(html, encoding="utf-8")


# ── 실시간 표 ──
rows = "".join(
    f'<div class="kv"><span>{NAME[f]}</span>'
    f'<b class="{"up" if live[f]["pct"]>=0 else "dn"}">'
    f'{live[f]["price"]:,.2f} &nbsp; {live[f]["pct"]:+.2f}%</b></div>'
    for f in FEAT if f in live)

if ok and not warn:
    hero = f"""<div class="card hero"><h2>오늘 코스피 개장 갭 환산</h2>
<div class="big {'up' if gap>=0 else 'dn'}">{gap:+.2f}%</div>
<div class="rng">80% 예상 범위 &nbsp;<b>{lo:+.2f}% ~ {hi:+.2f}%</b></div>
<div class="meta">현재 국면 <b>{regime}</b> · 설명력 R² {R['gap_r2']:.2f} ·
표본 {R['n']}일 · 오차 ±{1.28*R['gap_se']:.2f}%p</div></div>"""
elif ok and warn:
    hero = f"""<div class="card stop"><h2>⚠️ 환산 보류</h2>
<p style="font-size:.95rem">{warn}</p>
<p style="font-size:.9rem;margin-top:8px;color:#666">모델은 과거 관측 범위 안에서만 신뢰할 수 있습니다.
범위를 벗어난 구간에서는 예측값을 제시하지 않습니다.</p>
<div class="meta" style="color:#666">참고용 계산값: {gap:+.2f}% (신뢰 불가)</div></div>"""
else:
    hero = """<div class="card stop"><h2>⚠️ 데이터 수집 실패</h2>
<p>일부 지표를 가져오지 못해 환산을 제공하지 않습니다.</p></div>"""

BODY = f"""{hero}

<div class="card"><h2>간밤 해외 지표</h2>{rows}
<div class="meta" style="color:#888;margin-top:8px">미국장 마감 기준 · 이 값들로 위 갭을 환산합니다</div></div>

<div class="card warn"><h2>이 사이트가 하지 않는 것</h2>
<ul>
<li><b>장중 흐름은 예측하지 않습니다.</b> 검증 결과 간밤 지표로 장중 등락을 설명할 수 없었습니다 (R² 0.016).</li>
<li><b>종가를 숫자로 예측하지 않습니다.</b> 설명력이 19%에 불과해, 숫자를 제시하는 것이 오히려 오해를 낳습니다.</li>
<li><b>매매 조언을 하지 않습니다.</b> 간밤 등락의 대부분은 개장 시점에 이미 가격에 반영됩니다.</li>
</ul></div>

<div class="card"><h2>과거 비슷했던 경우 (코스피 종가)</h2>
<p style="font-size:.88rem;color:#666">야간선물 기준 · {M['n']}거래일 표본</p>
<table><thead><tr><th>간밤 조건</th><th>횟수</th><th>종가 평균</th><th>상승 마감</th></tr></thead><tbody>
<tr><td>야간 +1% 이상</td><td>57회</td><td class="up">+1.99%</td><td>82.5%</td></tr>
<tr><td>야간 +0.3~1%</td><td>64회</td><td class="up">+0.84%</td><td>73.4%</td></tr>
<tr><td>야간 -0.3~-1%</td><td>36회</td><td class="dn">-0.12%</td><td>47.2%</td></tr>
<tr><td>야간 -1% 이하</td><td>36회</td><td class="dn">-2.47%</td><td>27.8%</td></tr>
</tbody></table>
<p style="font-size:.85rem;color:#666;margin-top:10px">
하락 시 종가(-2.47%)가 개장 갭(-1.94%)보다 더 깊어지는 경향이 관측됩니다.
다만 표본이 36회로 작아 확정적으로 해석하기 어렵습니다.</p></div>

<div class="card"><h2>국면별 정확도</h2>
<p style="font-size:.88rem;color:#666">계수는 어느 국면에서나 비슷하지만, <b>오차범위는 국면마다 크게 다릅니다.</b></p>
<table><thead><tr><th>국면</th><th>표본</th><th>R²</th><th>오차범위</th></tr></thead><tbody>
{"".join(f'<tr><td>{k}{" <span class=badge>현재</span>" if k==regime else ""}</td>'
         f'<td>{v["n"]}일</td><td>{v["gap_r2"]:.2f}</td>'
         f'<td>±{1.28*v["gap_se"]:.2f}%p</td></tr>' for k, v in M["regimes"].items())}
</tbody></table></div>

<div class="card"><h2>자주 묻는 질문</h2>
<details><summary>야간선물이 오르면 다음날 코스피는 오르나요?</summary>
<p>개장 갭은 상당 부분 따라갑니다. 다만 이는 <b>예측이 아니라 이미 형성된 가격의 환산</b>에 가깝습니다. 개장 이후의 흐름은 별개입니다.</p></details>
<details><summary>그럼 아침에 사면 수익이 나나요?</summary>
<p>아닙니다. 간밤 등락은 개장가에 대부분 반영되어 있습니다. 저희 검증에서 장중 흐름은 간밤 지표와 통계적으로 무관했습니다.</p></details>
<details><summary>야간선물 거래시간은 언제인가요?</summary>
<p>KRX 야간 파생상품시장은 18:00부터 익일 06:00까지 12시간 운영되며, 호가 접수는 17:50부터입니다. 야간거래는 T+1일 거래로 처리됩니다.</p></details>
<details><summary>왜 야간선물이 아니라 미국 지표를 쓰나요?</summary>
<p>KRX 공식 데이터는 익일 08시에 공개됩니다. 개장 전 시점(07시)에 확보 가능한 것은 미국 시장 데이터뿐이며, 그래서 EWY·반도체지수·나스닥으로 환산합니다. 정확도는 야간선물 기준 모델의 약 60% 수준입니다.</p></details>
</div>"""

page("야간 갭 | 간밤 해외지표로 보는 오늘 코스피 개장 갭",
     f"간밤 미국 시장 지표로 오늘 코스피 개장 갭을 환산합니다. KRX 공식 데이터 {M['n']}거래일 회귀. 국면별 오차범위와 모델 한계를 함께 공개합니다.",
     BODY, "index.html")

# ── 제도 안내 ──
page("코스피200 야간선물 제도 정리 (2026년 기준)",
     "2025년 6월 9일 KRX 자체 야간 파생상품시장 전환 이후 기준. 거래시간 18:00~06:00, T+1 거래일 처리.",
     """<div class="card"><h2>제도가 바뀌었습니다</h2>
<p>코스피200 야간선물을 검색하면 설명이 제각각입니다. 제도가 여러 번 바뀌었기 때문입니다.</p>
<div class="kv"><span>2009년~</span><b>CME 연계 야간시장</b></div>
<div class="kv"><span>이후</span><b>Eurex 연계 야간옵션</b></div>
<div class="kv"><span>2023~2025.5</span><b>야간시장 공백기</b></div>
<div class="kv"><span>2025.6.9 ~ 현재</span><b>KRX 자체 야간 파생상품시장</b></div>
<p style="margin-top:12px">현재 자료라면 <b>KRX 자체 야간거래 기준</b>으로 읽어야 합니다. 증권사 안내 페이지 중에도 옛 CME 연계 시절 설명이 그대로 남아 있는 곳이 많습니다.</p></div>

<div class="card"><h2>거래시간</h2>
<div class="kv"><span>호가 접수</span><b>17:50 ~</b></div>
<div class="kv"><span>거래시간</span><b>18:00 ~ 익일 06:00 (12시간)</b></div>
<div class="kv"><span>거래일 처리</span><b>T+1일</b></div>
<p style="margin-top:10px">월요일 저녁 6시에 시작한 야간거래는 <b>화요일 거래</b>로 집계되어, 화요일 정규거래분과 합산 정산됩니다.</p></div>

<div class="card"><h2>취급 상품</h2>
<p>코스피200 선물, 미니코스피200 선물, 코스닥150 선물, 미국달러선물, 3년·10년 국채선물 등이 야간에 거래됩니다.</p></div>

<div class="card"><h2>왜 보는가</h2>
<p>야간 세션은 유럽·미국 거래시간과 겹칩니다. 한국 정규장이 닫힌 시간에 나온 정보(미국 고용지표, 연준 결정 등)가 한국 주식 가격에 반영되는 통로입니다.</p>
<p style="margin-top:8px">그래서 야간에 형성된 가격은 다음 날 개장가에 갭(Gap) 형태로 나타납니다. <a href="/">대시보드</a>는 이 관계를 수치화한 것입니다.</p></div>""",
     "guide.html")

# ── 방법론 ──
page("방법론과 한계 | 야간 갭",
     "회귀 모델, 국면별 예측구간, 검증하고 기각한 가설, 그리고 한계를 공개합니다.",
     f"""<div class="card"><h2>데이터</h2>
<div class="kv"><span>출처</span><b>KRX 공식 Open API</b></div>
<div class="kv"><span>기간</span><b>{M['start']} ~ {M['end']}</b></div>
<div class="kv"><span>표본</span><b>{M['n']}거래일</b></div>
<div class="kv"><span>갱신</span><b>매 영업일 자동</b></div></div>

<div class="card"><h2>두 개의 모델</h2>
<table><thead><tr><th></th><th>Model 1</th><th>Model 2 (사용중)</th></tr></thead><tbody>
<tr><td>입력</td><td>야간선물</td><td>EWY·반도체·나스닥</td></tr>
<tr><td>사용 시각</td><td>익일 08시~</td><td><b>개장 전 07시</b></td></tr>
<tr><td>개장 갭 R²</td><td>0.67</td><td><b>0.40</b></td></tr>
<tr><td>종가 R²</td><td>0.37</td><td>0.19</td></tr>
<tr><td>장중 R²</td><td>0.02</td><td>0.02</td></tr>
</tbody></table>
<p style="margin-top:10px;font-size:.9rem">야간선물이 더 정확하지만 개장 전에는 구할 수 없습니다. 그래서 그 시각에 확보 가능한 미국 지표로 환산하며, 정확도가 낮아지는 만큼 <b>오차범위를 함께 제시</b>합니다.</p></div>

<div class="card"><h2>검증하고 기각한 가설</h2>
<p style="font-size:.88rem;color:#666">저희가 시도했다가 데이터로 <b>기각한</b> 가설을 공개합니다.</p>
<div class="kv"><span>갭은 장중에 되돌려진다</span><b style="color:#c0392b">기각 (t=0.5)</b></div>
<div class="kv"><span>야간 프리미엄은 소멸한다</span><b style="color:#c0392b">기각 (시험구간 붕괴)</b></div>
<div class="kv"><span>20일 부분군별 국면 차이</span><b style="color:#c0392b">기각 (F=0.83)</b></div>
<div class="kv"><span>20일선이 특별하다</span><b style="color:#c0392b">기각</b></div>
<div class="kv"><span>야간 → 개장 갭 환산</span><b style="color:#1b7a3d">채택</b></div>
<p style="margin-top:10px;font-size:.9rem">기각한 가설을 숨기지 않는 이유는, 그것이 남은 하나의 신뢰성을 뒷받침하기 때문입니다.</p></div>

<div class="card"><h2>한계</h2>
<ul>
<li>표본이 {M['n']}거래일로 크지 않습니다. KRX 자체 야간시장이 2025년 6월 시작되었기 때문입니다.</li>
<li>회귀는 인과를 증명하지 않습니다. 같은 정보를 반영하는 관계입니다.</li>
<li>고변동 국면에서는 오차범위가 4배 가까이 커집니다.</li>
<li>과거 관측 범위를 벗어난 급변 상황에서는 환산값을 제시하지 않습니다.</li>
<li>제도·시장구조가 바뀌면 계수는 달라질 수 있습니다.</li>
</ul></div>""",
     "methodology.html")

# ── robots / sitemap ──
(SITE / "robots.txt").write_text(
    f"User-agent: *\nAllow: /\n\nUser-agent: Yeti\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n",
    encoding="utf-8")
today = KST.strftime("%Y-%m-%d")
(SITE / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
    "".join(f'<url><loc>{BASE}/{p}</loc><lastmod>{today}</lastmod>'
            f'<changefreq>daily</changefreq></url>'
            for p in ["", "guide.html", "methodology.html"]) +
    '</urlset>', encoding="utf-8")
(SITE / ".nojekyll").write_text("", encoding="utf-8")

print("\n" + "=" * 62)
print(f"  ✅ 빌드 완료")
print(f"     국면      {regime}  (rv20={rv:.2f})")
print(f"     환산 갭   {gap:+.2f}%  [{lo:+.2f}% ~ {hi:+.2f}%]" if ok else "     환산    실패")
print(f"     경고      {warn if warn else '없음'}")
print(f"     URL       {BASE}/")
print("=" * 62)
