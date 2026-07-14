"""
nightgap.co.kr 사이트 빌더 v2
- 새벽에 폰으로 보는 데이터 도구
- 시그니처: 갭 자(Gap Ruler) — 불확실성을 눈에 보이게
"""
import json
import pathlib
import datetime
import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)
BASE = "https://nightgap.kr"
UA = {"User-Agent": "Mozilla/5.0"}
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

M = json.loads((ROOT / "data" / "model2.json").read_text(encoding="utf-8"))
FEAT = M["features"]
SYM = {"EWY_r": "EWY", "SOX_r": "^SOX", "NASDAQ_r": "^IXIC",
       "SP500_r": "^GSPC", "USDKRW_r": "KRW=X", "VIX_r": "^VIX"}
NAME = {"EWY_r": "EWY", "SOX_r": "반도체(SOX)", "NASDAQ_r": "나스닥",
        "SP500_r": "S&P 500", "USDKRW_r": "달러/원", "VIX_r": "VIX"}
DESC = {"EWY_r": "미국 상장 한국 ETF", "SOX_r": "필라델피아 반도체지수",
        "NASDAQ_r": "나스닥 종합", "SP500_r": "S&P 500",
        "USDKRW_r": "원달러 환율", "VIX_r": "변동성지수"}


# ═══════════ 1. 실시간 수집 ═══════════
def quote(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"interval": "1d", "range": "5d"}, headers=UA, timeout=20)
    res = r.json()["chart"]["result"][0]
    c = [x for x in res["indicators"]["quote"][0]["close"] if x]
    t = datetime.datetime.utcfromtimestamp(
        res["meta"]["regularMarketTime"]) + datetime.timedelta(hours=9)
    return {"price": c[-1], "pct": (c[-1] / c[-2] - 1) * 100, "at": t}


live, fail = {}, []
for f in FEAT:
    try:
        live[f] = quote(SYM[f])
        print(f"  OK  {NAME[f]:<12} {live[f]['price']:>11,.2f}  {live[f]['pct']:+.2f}%")
    except Exception as e:
        fail.append(f)
        print(f"  FAIL {NAME[f]:<12} {e}")

# ═══════════ 2. 국면 판정 ═══════════
kr = pd.read_csv(ROOT / "data" / "kr_index.csv", parse_dates=["date"]).sort_values("date")
kr["r"] = kr["kospi_close"].pct_change() * 100
rv = float(kr["r"].rolling(20).std().iloc[-1])
regime = "저변동" if rv <= M["rv_lo"] else ("고변동" if rv >= M["rv_hi"] else "중변동")
R = M["regimes"][regime]

# ═══════════ 3. 환산 + 기여도 분해 ═══════════
ok = not fail
gap = lo = hi = None
contrib = []
warn = None
if ok:
    co = R["gap_coef"]
    gap = co[0]
    for i, f in enumerate(FEAT):
        c = co[i + 1] * live[f]["pct"]
        gap += c
        contrib.append((f, live[f]["pct"], c))
    w = 1.28 * R["gap_se"]
    lo, hi = gap - w, gap + w
    for f in FEAT:
        if abs(live[f]["pct"]) > 6:
            warn = f"{NAME[f]} 등락 {live[f]['pct']:+.1f}%는 과거 관측 범위를 벗어납니다"

crosses_zero = ok and lo < 0 < hi


# ═══════════ 4. 시그니처: 갭 자 ═══════════
def ruler(gap, lo, hi):
    W, H = 640, 132
    span = max(3.0, abs(lo) * 1.35, abs(hi) * 1.35)
    px = lambda v: W / 2 + (v / span) * (W / 2 - 30)
    up = gap >= 0
    col = "var(--up)" if up else "var(--down)"
    bx0, bx1 = px(lo), px(hi)
    ticks = "".join(
        f'<line x1="{px(t)}" y1="74" x2="{px(t)}" y2="80" stroke="var(--faint)" stroke-width="1"/>'
        f'<text x="{px(t)}" y="98" fill="var(--faint)" font-size="11" '
        f'text-anchor="middle" class="mono">{t:+.0f}%</text>'
        for t in [-span * .66, -span * .33, span * .33, span * .66])
    return f'''<svg viewBox="0 0 {W} {H}" class="ruler" role="img"
 aria-label="개장 갭 예상 {gap:+.2f}%, 80% 구간 {lo:+.2f}% ~ {hi:+.2f}%">
<text x="14" y="20" fill="var(--down)" font-size="11" letter-spacing=".08em">◀ 갭하락</text>
<text x="{W-14}" y="20" fill="var(--up)" font-size="11" text-anchor="end" letter-spacing=".08em">갭상승 ▶</text>
<line x1="20" y1="74" x2="{W-20}" y2="74" stroke="var(--line)" stroke-width="1"/>
{ticks}
<rect x="{min(bx0,bx1)}" y="40" width="{abs(bx1-bx0)}" height="30" rx="2"
      fill="{col}" opacity="0.16"/>
<line x1="{bx0}" y1="38" x2="{bx0}" y2="72" stroke="{col}" stroke-width="1.5" opacity=".55"/>
<line x1="{bx1}" y1="38" x2="{bx1}" y2="72" stroke="{col}" stroke-width="1.5" opacity=".55"/>
<line x1="{W/2}" y1="30" x2="{W/2}" y2="82" stroke="var(--text)" stroke-width="1.5" opacity=".9"/>
<text x="{W/2}" y="118" fill="var(--dim)" font-size="11" text-anchor="middle" class="mono">0</text>
<circle cx="{px(gap)}" cy="55" r="6.5" fill="{col}"/>
<circle cx="{px(gap)}" cy="55" r="11" fill="none" stroke="{col}" stroke-width="1.5" opacity=".4"/>
</svg>'''


# ═══════════ 5. 자기채점 ═══════════
kr["gap"] = (kr["kospi_open"] / kr["kospi_close"].shift(1) - 1) * 100
recent = kr.dropna(subset=["gap"]).tail(8)[["date", "gap"]]

# ═══════════ 6. HTML ═══════════
CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&display=swap');

:root{
  --bg:#0B1120; --surf:#131B2E; --surf2:#1A2438; --line:#263149;
  --text:#E6EBF4; --dim:#8A96AC; --faint:#5A6780;
  --up:#FF5F56; --down:#46A2FF; --warn:#FFB84D; --good:#3DD68C;
  --mono:'JetBrains Mono',ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{
  font-family:Pretendard,-apple-system,'Malgun Gothic',sans-serif;
  background:var(--bg); color:var(--text);
  font-size:15px; line-height:1.65; padding:0 14px 40px;
  font-feature-settings:"tnum";
}
.mono{font-family:var(--mono);font-feature-settings:"tnum"}
.w{max-width:660px;margin:0 auto}

header{padding:26px 0 14px;border-bottom:1px solid var(--line)}
.brand{font-size:1.35rem;font-weight:800;letter-spacing:-.03em}
.brand span{color:var(--faint);font-weight:500}
.tag{color:var(--dim);font-size:.84rem;margin-top:4px}
nav{display:flex;gap:18px;margin-top:14px;flex-wrap:wrap}
nav a{color:var(--dim);text-decoration:none;font-size:.86rem;
  padding-bottom:4px;border-bottom:2px solid transparent}
nav a:hover,nav a.on{color:var(--text);border-color:var(--text)}

section{background:var(--surf);border:1px solid var(--line);
  border-radius:10px;padding:20px;margin:16px 0}
.eyebrow{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;
  color:var(--faint);font-weight:600;margin-bottom:14px}
h2{font-size:1rem;font-weight:700;margin-bottom:14px;letter-spacing:-.01em}

/* HERO */
.hero{background:linear-gradient(170deg,#141E36 0%,#0F1728 100%);
  border-color:#2C3A58;padding:22px 20px 16px}
.hero .num{font-family:var(--mono);font-size:3.4rem;font-weight:800;
  letter-spacing:-.04em;line-height:1;margin:4px 0 10px}
.hero .band{font-family:var(--mono);font-size:1rem;color:var(--dim)}
.hero .band b{color:var(--text);font-weight:600}
.ruler{width:100%;height:auto;margin:16px 0 6px;display:block}
.zero-warn{background:rgba(255,184,77,.09);border:1px solid rgba(255,184,77,.3);
  border-radius:7px;padding:11px 13px;margin-top:10px;
  font-size:.85rem;color:var(--warn);line-height:1.55}
.stat{display:flex;gap:20px;margin-top:14px;padding-top:14px;
  border-top:1px solid var(--line);flex-wrap:wrap}
.stat div{font-size:.78rem;color:var(--faint)}
.stat b{display:block;font-family:var(--mono);font-size:.98rem;
  color:var(--text);font-weight:600;margin-top:2px}

.up{color:var(--up)} .dn{color:var(--down)}

/* 지표 행 + 기여도 바 */
.ind{padding:12px 0;border-bottom:1px solid var(--line)}
.ind:last-child{border:0;padding-bottom:0}
.ind-top{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.ind-nm{font-weight:600;font-size:.92rem}
.ind-nm em{display:block;font-style:normal;font-size:.74rem;
  color:var(--faint);font-weight:400;margin-top:1px}
.ind-v{font-family:var(--mono);font-size:.95rem;font-weight:600;text-align:right;white-space:nowrap}
.ind-v em{display:block;font-style:normal;font-size:.74rem;color:var(--faint);font-weight:400}
.bar{height:5px;background:var(--surf2);border-radius:3px;margin-top:9px;
  position:relative;overflow:hidden}
.bar i{position:absolute;top:0;height:100%;border-radius:3px}
.bar .mid{position:absolute;left:50%;top:-2px;width:1px;height:9px;background:var(--faint)}
.bar-lb{display:flex;justify-content:space-between;font-size:.7rem;
  color:var(--faint);margin-top:4px;font-family:var(--mono)}

table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{padding:9px 4px;text-align:right;border-bottom:1px solid var(--line)}
th{color:var(--faint);font-weight:600;font-size:.74rem;
  letter-spacing:.05em;text-transform:uppercase}
td{font-family:var(--mono)}
td:first-child,th:first-child{text-align:left;font-family:Pretendard,sans-serif}
tbody tr:last-child td{border:0}
.now{display:inline-block;padding:1px 7px;border-radius:4px;
  background:var(--text);color:var(--bg);font-size:.68rem;
  font-weight:700;margin-left:5px;vertical-align:middle}

.limit{background:transparent;border-style:dashed;border-color:#3A2E1E}
.limit .eyebrow{color:var(--warn)}
.limit li{list-style:none;padding:11px 0;border-bottom:1px solid #24304A;
  font-size:.88rem;line-height:1.6;color:var(--dim)}
.limit li:last-child{border:0;padding-bottom:0}
.limit b{color:var(--text);font-weight:600}
.limit .r2{font-family:var(--mono);color:var(--warn);font-size:.82rem}

details{border-bottom:1px solid var(--line)}
details:last-child{border:0}
summary{cursor:pointer;padding:12px 0;font-weight:600;font-size:.9rem;
  list-style:none;display:flex;justify-content:space-between}
summary::after{content:'+';color:var(--faint);font-family:var(--mono)}
details[open] summary::after{content:'−'}
details p{font-size:.87rem;color:var(--dim);padding:0 0 13px;line-height:1.7}

.kv{display:flex;justify-content:space-between;padding:9px 0;
  border-bottom:1px solid var(--line);font-size:.88rem}
.kv:last-child{border:0}
.kv span{color:var(--dim)}
.kv b{font-family:var(--mono);font-weight:600}
.no{color:var(--up)} .yes{color:var(--good)}

.stamp{font-size:.74rem;color:var(--faint);margin-top:12px;font-family:var(--mono)}
footer{color:var(--faint);font-size:.76rem;padding:30px 0 10px;
  line-height:1.9;border-top:1px solid var(--line);margin-top:26px}
footer a{color:var(--dim)}
@media(max-width:420px){
  .hero .num{font-size:2.7rem}
  section{padding:17px 15px}
}
@media(prefers-reduced-motion:no-preference){
  section{animation:up .5s cubic-bezier(.2,.7,.3,1) backwards}
  section:nth-child(2){animation-delay:.05s}
  section:nth-child(3){animation-delay:.1s}
  @keyframes up{from{opacity:0;transform:translateY(10px)}}
}
"""


def page(title, desc, body, path, nav_on=""):
    nav = "".join(
        f'<a href="{u}" class="{"on" if u == nav_on else ""}">{t}</a>'
        for u, t in [("/", "대시보드"), ("/guide.html", "야간선물 제도"),
                     ("/methodology.html", "방법론과 한계")])
    (SITE / path).write_text(f'''<!DOCTYPE html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="{BASE}/{path}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:type" content="website"><meta property="og:url" content="{BASE}/{path}">
<meta name="theme-color" content="#0B1120">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<style>{CSS}</style></head><body><div class="w">
<header><div class="brand">nightgap<span>co.kr</span></div>
<div class="tag">간밤 해외 지표로 오늘 코스피 개장 갭을 환산합니다</div>
<nav>{nav}</nav></header>
{body}
<footer>
데이터 · 한국거래소 KRX Open API, Yahoo Finance<br>
이 사이트는 과거 데이터의 통계적 관계만 계산합니다. 투자 조언이나 매매 권유가 아니며,
투자 판단의 근거로 사용될 수 없습니다.<br>
갱신 {KST:%Y-%m-%d %H:%M} KST
</footer></div></body></html>''', encoding="utf-8")


# ── HERO ──
if ok and not warn:
    zw = ('<div class="zero-warn">예상 구간이 0을 가로지릅니다. '
          '상승·하락 <b>방향조차 확정할 수 없습니다.</b></div>') if crosses_zero else ""
    hero = f'''<section class="hero">
<div class="eyebrow">오늘 코스피 개장 갭 · 환산</div>
<div class="num mono {'up' if gap>=0 else 'dn'}">{gap:+.2f}%</div>
<div class="band">80% 구간 &nbsp;<b>{lo:+.2f}% ~ {hi:+.2f}%</b></div>
{ruler(gap, lo, hi)}{zw}
<div class="stat">
<div>국면<b>{regime}</b></div>
<div>설명력 R²<b>{R['gap_r2']:.2f}</b></div>
<div>오차<b>±{1.28*R['gap_se']:.2f}%p</b></div>
<div>표본<b>{R['n']}일</b></div>
</div></section>'''
elif ok and warn:
    hero = f'''<section class="hero">
<div class="eyebrow" style="color:var(--warn)">환산 보류</div>
<div class="num mono" style="font-size:1.5rem;color:var(--warn);line-height:1.4">
숫자를 제시하지 않습니다</div>
<p style="color:var(--dim);font-size:.9rem;margin-top:8px">{warn}.
모델은 과거 관측 범위 안에서만 신뢰할 수 있습니다.</p>
<div class="stat"><div>참고 계산값 (신뢰 불가)
<b style="color:var(--faint)">{gap:+.2f}%</b></div>
<div>국면<b>{regime}</b></div></div></section>'''
else:
    hero = '''<section class="hero"><div class="eyebrow" style="color:var(--warn)">데이터 수집 실패</div>
<div class="num mono" style="font-size:1.4rem;color:var(--warn)">환산 불가</div>
<p style="color:var(--dim);font-size:.9rem;margin-top:8px">
일부 지표를 가져오지 못했습니다. 부정확한 값을 제시하지 않습니다.</p></section>'''

# ── 기여도 ──
mx = max((abs(c) for _, _, c in contrib), default=1) or 1
inds = ""
for f, v, c in contrib:
    cls = "up" if v >= 0 else "dn"
    w = min(abs(c) / mx * 50, 50)
    left = 50 if c >= 0 else 50 - w
    bc = "var(--up)" if c >= 0 else "var(--down)"
    inds += f'''<div class="ind"><div class="ind-top">
<div class="ind-nm">{NAME[f]}<em>{DESC[f]}</em></div>
<div class="ind-v {cls}">{v:+.2f}%<em>{live[f]["price"]:,.2f}</em></div></div>
<div class="bar"><i style="left:{left}%;width:{w}%;background:{bc}"></i><span class="mid"></span></div>
<div class="bar-lb"><span>갭 기여도</span><span class="{cls}">{c:+.2f}%p</span></div></div>'''

at = max((live[f]["at"] for f in live), default=KST)

reg_rows = "".join(
    f'<tr><td>{k}{"<span class=now>현재</span>" if k == regime else ""}</td>'
    f'<td>{v["n"]}</td><td>{v["gap_r2"]:.2f}</td>'
    f'<td>±{1.28*v["gap_se"]:.2f}%p</td></tr>'
    for k, v in M["regimes"].items())

BODY = f'''{hero}

<section><div class="eyebrow">근거 · 간밤 해외 지표</div>
{inds}
<div class="stamp">미국장 마감 기준 · {at:%m월 %d일 %H:%M} KST</div></section>

<section><div class="eyebrow">국면별 정확도</div>
<h2>계수는 같지만, 오차는 국면마다 다릅니다</h2>
<table><thead><tr><th>국면</th><th>표본</th><th>R²</th><th>오차범위</th></tr></thead>
<tbody>{reg_rows}</tbody></table>
<p style="color:var(--dim);font-size:.84rem;margin-top:12px">
변동성이 큰 시기에는 같은 모델이라도 오차가 4배 가까이 커집니다.
그래서 하나의 오차범위를 쓰지 않고, 매일 국면을 판정해 다르게 적용합니다.</p></section>

<section><div class="eyebrow">과거 사례 · 코스피 종가</div>
<h2>야간선물이 이만큼 움직였던 날</h2>
<table><thead><tr><th>간밤 조건</th><th>횟수</th><th>종가 평균</th><th>상승 마감</th></tr></thead><tbody>
<tr><td>야간 +1% 이상</td><td>57</td><td class="up">+1.99%</td><td>82.5%</td></tr>
<tr><td>야간 +0.3~1%</td><td>64</td><td class="up">+0.84%</td><td>73.4%</td></tr>
<tr><td>야간 −0.3~−1%</td><td>36</td><td class="dn">−0.12%</td><td>47.2%</td></tr>
<tr><td>야간 −1% 이하</td><td>36</td><td class="dn">−2.47%</td><td>27.8%</td></tr>
</tbody></table>
<p style="color:var(--dim);font-size:.84rem;margin-top:12px">
하락한 날의 종가(−2.47%)가 개장 갭(−1.94%)보다 더 깊어지는 경향이 보입니다.
다만 표본이 36회로 작아 확정적으로 해석할 수 없습니다.</p></section>

<section class="limit"><div class="eyebrow">이 사이트가 하지 않는 것</div>
<ul>
<li><b>장중 흐름을 예측하지 않습니다.</b> 간밤 지표로 장중 등락을 설명하려 했으나 실패했습니다.
<span class="r2">R² 0.016</span> — 사실상 무관합니다.</li>
<li><b>종가를 숫자로 제시하지 않습니다.</b> 설명력이 <span class="r2">R² 0.19</span>에 그칩니다.
이 정도로 숫자를 내놓으면 오히려 오해를 만듭니다. 대신 과거 사례를 보여드립니다.</li>
<li><b>매매 조언을 하지 않습니다.</b> 간밤 등락은 개장 시점에 이미 가격에 반영됩니다.
아침에 이 값을 보고 매매해서 얻을 수 있는 것은 없습니다.</li>
<li><b>모르는 구간에서는 침묵합니다.</b> 지표가 과거 관측 범위를 벗어나면 숫자를 내지 않습니다.</li>
</ul></section>

<section><div class="eyebrow">자주 묻는 질문</div>
<details><summary>야간선물이 오르면 코스피도 오르나요</summary>
<p>개장 갭은 상당 부분 따라갑니다. 다만 이건 예측이 아니라 <b>이미 형성된 가격의 환산</b>에 가깝습니다.
밤사이 미국 시장에서 한국 자산이 재평가되고, 그 결과가 아침 개장가에 반영되는 것입니다.</p></details>
<details><summary>그럼 아침에 사면 수익이 나나요</summary>
<p>아닙니다. 간밤 등락은 개장가에 거의 전부 반영되어 있습니다.
개장 이후의 흐름은 간밤 지표와 통계적으로 무관했습니다.</p></details>
<details><summary>야간선물 거래시간은 언제인가요</summary>
<p>KRX 야간 파생상품시장은 18:00부터 익일 06:00까지 12시간 운영되며, 호가 접수는 17:50부터입니다.
야간거래는 T+1일 거래로 처리되어 익일 정규거래와 같은 거래일로 집계됩니다.</p></details>
<details><summary>왜 야간선물이 아니라 미국 지표를 쓰나요</summary>
<p>KRX 공식 야간선물 데이터는 익일 08시에 공개됩니다. 개장 전 시점에 확보할 수 있는 것은
미국 시장 데이터뿐입니다. 정확도는 야간선물 기준 모델의 약 60% 수준이며,
그만큼 오차범위를 넓게 잡습니다.</p></details>
</section>'''

page("야간 갭 | 간밤 해외지표로 보는 오늘 코스피 개장 갭",
     f"간밤 미국 지표로 오늘 코스피 개장 갭을 환산합니다. KRX 공식 데이터 {M['n']}거래일 회귀분석. "
     f"국면별 오차범위와 모델의 한계를 함께 공개합니다.",
     BODY, "index.html", "/")

# ── 제도 ──
page("코스피200 야간선물 제도 정리 (2026년 기준)",
     "2025년 6월 9일 KRX 자체 야간 파생상품시장 전환 이후 기준. 거래시간 18:00~06:00, T+1 거래일 처리.",
     '''<section><div class="eyebrow">먼저 알아야 할 것</div>
<h2>제도가 바뀌었습니다</h2>
<p style="color:var(--dim);font-size:.9rem;margin-bottom:14px">
코스피200 야간선물을 검색하면 설명이 제각각입니다. 제도가 여러 번 바뀌었기 때문입니다.
지금 보는 자료가 어느 시점 기준인지 확인하지 않으면 혼란스럽습니다.</p>
<div class="kv"><span>2009년 ~</span><b>CME 연계 야간시장</b></div>
<div class="kv"><span>이후</span><b>Eurex 연계 야간옵션</b></div>
<div class="kv"><span>2023 ~ 2025.5</span><b style="color:var(--faint)">야간시장 공백기</b></div>
<div class="kv"><span>2025.6.9 ~ 현재</span><b class="yes">KRX 자체 야간 파생상품시장</b></div>
<p style="color:var(--dim);font-size:.86rem;margin-top:14px">
증권사 안내 페이지 중에도 옛 CME 연계 시절 설명이 그대로 남아 있는 곳이 적지 않습니다.</p></section>

<section><div class="eyebrow">거래시간</div>
<div class="kv"><span>호가 접수</span><b>17:50 ~</b></div>
<div class="kv"><span>거래시간</span><b>18:00 ~ 익일 06:00</b></div>
<div class="kv"><span>총 운영</span><b>12시간</b></div>
<div class="kv"><span>거래일 처리</span><b>T+1일</b></div>
<p style="color:var(--dim);font-size:.88rem;margin-top:14px">
월요일 저녁 6시에 시작한 야간거래는 <b style="color:var(--text)">화요일 거래</b>로 집계되어,
화요일 정규거래분과 합산 정산됩니다.</p></section>

<section><div class="eyebrow">취급 상품</div>
<div class="kv"><span>지수선물</span><b>코스피200 · 미니코스피200 · 코스닥150</b></div>
<div class="kv"><span>통화선물</span><b>미국달러선물</b></div>
<div class="kv"><span>금리선물</span><b>3년 · 10년 국채선물</b></div></section>

<section><div class="eyebrow">왜 보는가</div>
<h2>한국 정규장이 닫힌 시간에도 가격은 움직입니다</h2>
<p style="color:var(--dim);font-size:.9rem">
야간 세션은 유럽·미국 거래시간과 겹칩니다. 한국 시장이 닫혀 있는 동안 나온 정보 —
미국 고용지표, 연준 금리 결정, 반도체 업황 뉴스 — 가 한국 자산 가격에 반영되는 통로입니다.</p>
<p style="color:var(--dim);font-size:.9rem;margin-top:10px">
그래서 야간에 형성된 가격은 다음 날 개장가에 <b style="color:var(--text)">갭(Gap)</b> 형태로 나타납니다.
<a href="/" style="color:var(--down)">대시보드</a>는 이 관계를 수치화한 것입니다.</p></section>''',
     "guide.html", "/guide.html")

# ── 방법론 ──
page("방법론과 한계 | nightgap.kr",
     "회귀 모델, 국면별 예측구간 산출 방법, 검증 후 기각한 가설, 그리고 이 모델의 한계를 공개합니다.",
     f'''<section><div class="eyebrow">데이터</div>
<div class="kv"><span>출처</span><b>KRX 공식 Open API</b></div>
<div class="kv"><span>기간</span><b>{M['start']} ~ {M['end']}</b></div>
<div class="kv"><span>표본</span><b>{M['n']}거래일</b></div>
<div class="kv"><span>갱신</span><b>매 영업일 자동</b></div></section>

<section><div class="eyebrow">두 개의 모델</div>
<h2>정확한 모델은 제시간에 쓸 수 없습니다</h2>
<table><thead><tr><th></th><th>Model 1</th><th>Model 2</th></tr></thead><tbody>
<tr><td>입력</td><td>야간선물</td><td>EWY·반도체·나스닥</td></tr>
<tr><td>사용 가능 시각</td><td>익일 08시</td><td class="yes">개장 전 07시</td></tr>
<tr><td>개장 갭 R²</td><td>0.67</td><td>0.40</td></tr>
<tr><td>종가 R²</td><td>0.37</td><td>0.19</td></tr>
<tr><td>장중 R²</td><td>0.02</td><td>0.02</td></tr>
</tbody></table>
<p style="color:var(--dim);font-size:.88rem;margin-top:14px">
야간선물 기준 모델이 더 정확하지만, 그 데이터는 개장 전에 구할 수 없습니다.
그래서 그 시각에 확보 가능한 미국 지표로 환산하고, 정확도가 낮아지는 만큼
<b style="color:var(--text)">오차범위를 넓게 잡습니다.</b></p></section>

<section><div class="eyebrow">검증 후 기각한 가설</div>
<h2>시도했다가 데이터에 부정당한 것들</h2>
<div class="kv"><span>갭은 장중에 되돌려진다</span><b class="no">기각 · t=0.5</b></div>
<div class="kv"><span>야간 프리미엄은 소멸한다</span><b class="no">기각 · 시험구간 붕괴</b></div>
<div class="kv"><span>20일 부분군별 국면 차이</span><b class="no">기각 · F=0.83</b></div>
<div class="kv"><span>20일 이동평균선이 특별하다</span><b class="no">기각</b></div>
<div class="kv"><span>야간 → 개장 갭 환산</span><b class="yes">채택</b></div>
<p style="color:var(--dim);font-size:.88rem;margin-top:14px">
기각한 가설을 숨기지 않는 이유는, 그것이 남은 하나의 신뢰성을 뒷받침하기 때문입니다.
모든 가설이 통과했다면 검증을 의심해야 합니다.</p></section>

<section class="limit"><div class="eyebrow">한계</div>
<ul>
<li>표본이 <b>{M['n']}거래일</b>로 크지 않습니다. KRX 자체 야간시장이 2025년 6월에 시작되었기 때문입니다.</li>
<li>회귀는 인과를 증명하지 않습니다. 야간선물과 개장가는 <b>같은 정보를 반영하는 관계</b>입니다.</li>
<li>고변동 국면에서는 오차범위가 <b>4배 가까이</b> 커집니다.</li>
<li>과거 관측 범위를 벗어난 급변 상황에서는 <b>환산값을 제시하지 않습니다.</b></li>
<li>제도나 시장 구조가 바뀌면 계수는 달라질 수 있습니다.</li>
</ul></section>''',
     "methodology.html", "/methodology.html")

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

print("\n" + "=" * 60)
print(f"  빌드 완료")
print(f"    국면      {regime} (rv20={rv:.2f})")
print(f"    환산 갭   {gap:+.2f}%  [{lo:+.2f} ~ {hi:+.2f}]" if ok else "    환산      보류")
print(f"    0 가로지름 {'예 — 방향 불확정' if crosses_zero else '아니오'}")
print(f"    경고      {warn or '없음'}")
print("=" * 60)
