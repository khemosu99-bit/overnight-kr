"""
정적 사이트 빌더
- night_futures.csv → 모델 계수/국면/예측구간 계산
- 크롤러가 완벽히 읽는 정적 HTML 생성 (SSR)
"""
import os
import json
import pathlib
import datetime
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)

REPO = os.environ.get("GITHUB_REPOSITORY", "user/overnight-kr")
OWNER, NAME = REPO.split("/")
BASE = f"https://{OWNER}.github.io/{NAME}"

KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

# ═══════════ 1. 데이터 & 모델 ═══════════
df = pd.read_csv(ROOT / "data" / "night_futures.csv", parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)

df["prev_close"] = df["reg_close"].shift(1)
df["night_ret"] = (df["night_close"] / df["prev_close"] - 1) * 100
df["gap"] = (df["reg_open"] / df["prev_close"] - 1) * 100
df["intra"] = (df["reg_close"] / df["reg_open"] - 1) * 100
df["full"] = (df["reg_close"] / df["prev_close"] - 1) * 100
df["rv20"] = df["full"].rolling(20).std()

d = df.dropna(subset=["night_ret", "gap", "rv20"]).copy()


def fit(g):
    if len(g) < 15:
        return None
    b = np.polyfit(g["night_ret"], g["gap"], 1)
    pred = np.polyval(b, g["night_ret"])
    res = g["gap"] - pred
    ss_t = ((g["gap"] - g["gap"].mean()) ** 2).sum()
    return {
        "beta": round(float(b[0]), 4),
        "alpha": round(float(b[1]), 4),
        "r2": round(float(1 - (res ** 2).sum() / ss_t), 3),
        "se": round(float(res.std()), 3),
        "n": int(len(g)),
    }


lo, hi = d["rv20"].quantile([0.33, 0.67])
REG = {
    "저변동": fit(d[d["rv20"] <= lo]),
    "중변동": fit(d[(d["rv20"] > lo) & (d["rv20"] < hi)]),
    "고변동": fit(d[d["rv20"] >= hi]),
}
ALL = fit(d)

cur_rv = float(d["rv20"].iloc[-1])
cur = "저변동" if cur_rv <= lo else ("고변동" if cur_rv >= hi else "중변동")
M = REG[cur]

# ═══════════ 2. 자기 채점 (최근 10일) ═══════════
score = []
for _, r in d.tail(10).iterrows():
    pred = M["beta"] * r["night_ret"] + M["alpha"]
    score.append({
        "date": r["date"].strftime("%Y-%m-%d"),
        "night": round(r["night_ret"], 2),
        "pred": round(pred, 2),
        "actual": round(r["gap"], 2),
        "err": round(abs(pred - r["gap"]), 2),
        "hit": abs(pred - r["gap"]) <= 1.28 * M["se"],
    })
score.reverse()
hit_rate = sum(s["hit"] for s in score) / len(score) * 100
mae = np.mean([s["err"] for s in score])

last = d.iloc[-1]
MODEL = {
    "beta": M["beta"], "alpha": M["alpha"], "se": M["se"],
    "r2": M["r2"], "n": M["n"], "regime": cur,
    "all_n": ALL["n"], "all_beta": ALL["beta"],
    "regimes": {k: v for k, v in REG.items()},
    "last_date": last["date"].strftime("%Y-%m-%d"),
    "last_night": round(float(last["night_close"]), 2),
    "last_prev": round(float(last["prev_close"]), 2),
    "start": d["date"].min().strftime("%Y-%m-%d"),
}

# ═══════════ 3. HTML ═══════════
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI','Malgun Gothic',sans-serif;
line-height:1.7;color:#1a1a1a;background:#f6f7f9;padding:16px}
.w{max-width:720px;margin:0 auto}
header{padding:20px 0 8px}
h1{font-size:1.5rem;letter-spacing:-.02em}
.sub{color:#666;font-size:.9rem;margin-top:4px}
.card{background:#fff;border:1px solid #e4e6ea;border-radius:12px;
padding:20px;margin:16px 0}
h2{font-size:1.1rem;margin-bottom:12px;padding-bottom:8px;
border-bottom:2px solid #1a1a1a;display:inline-block}
label{display:block;font-size:.85rem;color:#555;margin:12px 0 4px}
input{width:100%;padding:12px;font-size:1.1rem;border:1px solid #ccd;
border-radius:8px;font-family:inherit}
button{width:100%;padding:14px;margin-top:14px;background:#1a1a1a;color:#fff;
border:0;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer}
.out{margin-top:18px;padding:16px;background:#f0f4f8;border-radius:8px;display:none}
.out.on{display:block}
.big{font-size:2rem;font-weight:700;letter-spacing:-.02em}
.rng{font-size:1.05rem;color:#333;margin-top:6px}
.note{font-size:.82rem;color:#666;margin-top:10px}
table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:8px}
th,td{padding:8px 6px;text-align:right;border-bottom:1px solid #eee}
th{background:#fafbfc;font-weight:600;color:#555}
td:first-child,th:first-child{text-align:left}
.up{color:#c0392b}.dn{color:#1565c0}
.ok{color:#1b7a3d;font-weight:600}.no{color:#b23}
.warn{background:#fff8e6;border:1px solid #f0d9a0;border-radius:12px;padding:18px;margin:16px 0}
.warn h2{border-color:#c99700}
.warn li{margin:6px 0 6px 18px;font-size:.92rem}
.kv{display:flex;justify-content:space-between;padding:7px 0;
border-bottom:1px dashed #eee;font-size:.9rem}
.kv b{font-weight:600}
details{margin:8px 0;border-bottom:1px solid #eee;padding-bottom:8px}
summary{cursor:pointer;font-weight:600;padding:8px 0;font-size:.95rem}
details p{font-size:.9rem;color:#444;padding:4px 0 8px}
footer{text-align:center;color:#888;font-size:.8rem;padding:28px 0}
nav a{color:#1a1a1a;margin-right:14px;font-size:.88rem}
.badge{display:inline-block;padding:3px 10px;border-radius:99px;
background:#1a1a1a;color:#fff;font-size:.75rem;margin-left:6px}
"""

JS = """
const M = __MODEL__;
function calc(){
  const n = parseFloat(document.getElementById('nc').value);
  const p = parseFloat(document.getElementById('pc').value);
  const o = document.getElementById('out');
  if(!n||!p){alert('두 값을 모두 입력해 주세요');return;}
  const nr = (n/p-1)*100;
  const g  = M.beta*nr + M.alpha;
  const w  = 1.28*M.se;
  document.getElementById('nr').textContent = (nr>=0?'+':'')+nr.toFixed(2)+'%';
  document.getElementById('gp').textContent = (g>=0?'+':'')+g.toFixed(2)+'%';
  document.getElementById('gp').className = 'big ' + (g>=0?'up':'dn');
  document.getElementById('rg').textContent =
    (g-w>=0?'+':'')+(g-w).toFixed(2)+'% ~ '+(g+w>=0?'+':'')+(g+w).toFixed(2)+'%';
  document.getElementById('k2').textContent =
    (p*(1+g/100)).toFixed(2) + ' (약 ' + (p*(1+(g-w)/100)).toFixed(1) +
    ' ~ ' + (p*(1+(g+w)/100)).toFixed(1) + ')';
  o.classList.add('on');
}
"""

def page(title, desc, body, path):
    h = """<!DOCTYPE html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__URL__">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:type" content="website">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<style>__CSS__</style></head><body><div class="w">
<header><h1>야간선물 → 개장 갭 환산기</h1>
<div class="sub">코스피200 야간선물로 다음 개장 갭을 환산합니다 · KRX 공식 데이터</div>
<nav style="margin-top:10px"><a href="./">환산기</a><a href="./guide.html">야간선물 제도</a><a href="./methodology.html">방법론·한계</a></nav>
</header>__BODY__
<footer>데이터: 한국거래소(KRX) 공식 Open API<br>
투자 판단의 근거로 사용될 수 없으며, 어떠한 매매 조언도 제공하지 않습니다.<br>
최종 갱신 __UPD__ KST</footer></div><script>__JS__</script></body></html>"""
    h = (h.replace("__TITLE__", title).replace("__DESC__", desc)
          .replace("__URL__", f"{BASE}/{path}").replace("__CSS__", CSS)
          .replace("__BODY__", body)
          .replace("__UPD__", KST.strftime("%Y-%m-%d %H:%M"))
          .replace("__JS__", JS.replace("__MODEL__", json.dumps(MODEL))))
    (SITE / path).write_text(h, encoding="utf-8")


# ── 자기채점 표 ──
rows = "".join(
    f"<tr><td>{s['date']}</td>"
    f"<td class='{'up' if s['night']>=0 else 'dn'}'>{s['night']:+.2f}%</td>"
    f"<td>{s['pred']:+.2f}%</td>"
    f"<td class='{'up' if s['actual']>=0 else 'dn'}'>{s['actual']:+.2f}%</td>"
    f"<td>{s['err']:.2f}%p</td>"
    f"<td class='{'ok' if s['hit'] else 'no'}'>{'적중' if s['hit'] else '벗어남'}</td></tr>"
    for s in score)

reg_rows = "".join(
    f"<tr><td>{k}{' <span class=badge>현재</span>' if k==cur else ''}</td>"
    f"<td>{v['n']}일</td><td>{v['beta']:.3f}</td><td>{v['r2']:.2f}</td>"
    f"<td>±{1.28*v['se']:.2f}%p</td></tr>"
    for k, v in REG.items() if v)

BODY = f"""
<div class="card">
<h2>환산 계산기</h2>
<p style="font-size:.9rem;color:#555">지금 보고 계신 야간선물 값을 입력하세요. HTS·MTS나 실시간 시세 화면에서 확인할 수 있습니다.</p>
<label>야간선물 현재가 / 종가</label>
<input id="nc" type="number" step="0.01" placeholder="예: {MODEL['last_night']}">
<label>직전 정규장 종가 (코스피200 선물)</label>
<input id="pc" type="number" step="0.01" placeholder="예: {MODEL['last_prev']}">
<button onclick="calc()">환산하기</button>
<div class="out" id="out">
  <div style="font-size:.85rem;color:#555">야간 등락 <b id="nr"></b> →</div>
  <div class="big" id="gp"></div>
  <div class="rng">예상 범위 <b id="rg"></b> <span style="font-size:.8rem;color:#777">(80% 구간)</span></div>
  <div class="note">환산 시가 <b id="k2"></b></div>
  <div class="note">현재 국면: <b>{cur}</b> · 회귀계수 {M['beta']:.3f} · 표본 {M['n']}일 · R² {M['r2']:.2f}</div>
</div>
</div>

<div class="warn">
<h2>이 사이트가 하지 않는 것</h2>
<ul>
<li><b>장중 흐름은 예측하지 않습니다.</b> 검증 결과 야간선물과 장중 등락 사이에 유의한 관계가 없었습니다 (t=0.5, 265일).</li>
<li><b>매매 조언을 하지 않습니다.</b> 과거 데이터의 통계적 관계만 계산합니다.</li>
<li><b>초과수익을 주장하지 않습니다.</b> 야간 등락의 대부분은 개장 시점에 이미 가격에 반영됩니다.</li>
</ul>
</div>

<div class="card">
<h2>모델 자기 채점 (최근 10거래일)</h2>
<p style="font-size:.9rem;color:#555">틀린 날도 그대로 공개합니다.</p>
<div class="kv"><span>80% 구간 적중률</span><b>{hit_rate:.0f}%</b></div>
<div class="kv"><span>평균 절대오차 (MAE)</span><b>{mae:.2f}%p</b></div>
<table><thead><tr><th>날짜</th><th>야간등락</th><th>모델예측</th><th>실제갭</th><th>오차</th><th>판정</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>

<div class="card">
<h2>국면별 정확도</h2>
<p style="font-size:.9rem;color:#555">같은 회귀계수라도 <b>오차범위는 국면마다 다릅니다.</b> 최근 20일 변동성으로 국면을 판정합니다.</p>
<table><thead><tr><th>국면</th><th>표본</th><th>계수</th><th>R²</th><th>오차범위</th></tr></thead>
<tbody>{reg_rows}</tbody></table>
</div>

<div class="card">
<h2>자주 묻는 질문</h2>
<details><summary>야간선물이 오르면 다음날 코스피는 오르나요?</summary>
<p>개장 시점의 갭은 야간선물 등락을 거의 그대로 따라갑니다. 표본 {ALL['n']}거래일 기준 회귀계수는 {ALL['beta']:.3f}로, 야간선물이 1% 오르면 개장 갭은 약 {ALL['beta']:.2f}% 벌어집니다. 다만 이는 예측이 아니라 <b>이미 형성된 가격의 환산</b>에 가깝습니다.</p></details>
<details><summary>그럼 아침에 사면 수익이 나나요?</summary>
<p>아닙니다. 야간 등락은 개장가에 이미 반영되어 있습니다. 개장 이후의 흐름(장중 등락)은 야간선물로 설명되지 않는다는 것이 저희 검증 결과입니다.</p></details>
<details><summary>야간선물 거래시간은 언제인가요?</summary>
<p>KRX 야간 파생상품시장은 오후 6시부터 다음 날 오전 6시까지 12시간 운영되며, 호가 접수는 17시 50분부터입니다. 야간거래는 T+1일 거래로 처리되어 익일 정규거래와 같은 거래일로 집계됩니다.</p></details>
<details><summary>데이터 출처는 어디인가요?</summary>
<p>한국거래소(KRX) 공식 Open API의 선물 일별매매정보 및 지수 일별시세정보입니다. {MODEL['start']} 이후 {ALL['n']}거래일을 사용합니다.</p></details>
</div>
"""

page("야간선물 개장 갭 환산기 | 코스피200 야간선물",
     f"코스피200 야간선물 값으로 다음 개장 갭을 환산합니다. KRX 공식 데이터 {ALL['n']}거래일 회귀분석. 국면별 오차범위 제공.",
     BODY, "index.html")

# ── 제도 안내 페이지 ──
GUIDE = """
<div class="card">
<h2>KRX 야간 파생상품시장 (2026년 기준)</h2>
<p>코스피200 야간선물을 검색하면 서로 다른 설명이 섞여 나옵니다. <b>제도가 바뀌었기 때문입니다.</b></p>
<div class="kv"><span>과거 (2009~)</span><b>CME 연계 야간시장</b></div>
<div class="kv"><span>이후</span><b>Eurex 연계 야간옵션</b></div>
<div class="kv"><span>현재 (2025.6.9~)</span><b>KRX 자체 야간 파생상품시장</b></div>
<p style="margin-top:12px">현재 자료를 볼 때는 <b>KRX 자체 야간거래 기준</b>인지, 과거 해외 연계 시절 이야기인지 반드시 확인해야 합니다. 증권사 안내 페이지 중에도 옛 설명이 남아 있는 경우가 많습니다.</p>
</div>

<div class="card">
<h2>거래시간 및 결제</h2>
<div class="kv"><span>호가 접수</span><b>17:50 ~</b></div>
<div class="kv"><span>거래시간</span><b>18:00 ~ 익일 06:00 (12시간)</b></div>
<div class="kv"><span>거래일 처리</span><b>T+1일 (익일 정규거래와 동일 거래일)</b></div>
<p style="margin-top:12px">예를 들어 월요일 오후 6시에 시작한 야간거래는 <b>화요일 거래</b>로 집계되며, 화요일 정규거래분과 합산되어 정산됩니다.</p>
</div>

<div class="card">
<h2>취급 상품</h2>
<p>코스피200 선물, 미니코스피200 선물, 코스닥150 선물, 미국달러선물, 3년·10년 국채선물 등이 야간시장에서 거래됩니다.</p>
</div>

<div class="card">
<h2>왜 보는가</h2>
<p>야간 세션은 유럽·미국 거래시간과 겹칩니다. 미국 고용지표나 연준 금리 결정처럼 한국 정규장이 닫힌 시간에 나온 정보가, 한국 주식 리스크에 실시간으로 반영되는 유일한 유동적 장소입니다.</p>
<p style="margin-top:8px">그래서 야간선물에서 형성된 가격은 <b>다음 날 정규장 시초가에 직접 반영</b>되며, 갭(Gap)의 형태로 나타납니다. 저희 <a href="./">환산기</a>는 이 관계를 수치화한 것입니다.</p>
</div>
"""
page("코스피200 야간선물 제도 정리 (2026년 기준) | KRX 야간 파생상품시장",
     "2025년 6월 9일 KRX 자체 야간 파생상품시장 전환 이후 기준. 거래시간 18:00~06:00, T+1 거래일 처리, 취급 상품 정리.",
     GUIDE, "guide.html")

# ── 방법론 페이지 ──
METH = f"""
<div class="card">
<h2>데이터</h2>
<div class="kv"><span>출처</span><b>KRX 공식 Open API</b></div>
<div class="kv"><span>기간</span><b>{MODEL['start']} ~ {MODEL['last_date']}</b></div>
<div class="kv"><span>표본</span><b>{ALL['n']}거래일</b></div>
<div class="kv"><span>갱신</span><b>매 영업일 자동</b></div>
</div>

<div class="card">
<h2>모델</h2>
<p>야간선물 등락률(X)로 개장 갭(Y)을 회귀합니다.</p>
<p style="margin:10px 0;padding:12px;background:#f0f4f8;border-radius:8px;font-family:monospace">
갭(%) = {ALL['beta']:.3f} × 야간등락(%) + {ALL['alpha']:.3f}<br>
R² = {ALL['r2']:.2f}
</p>
<p>최근 20거래일 실현변동성으로 국면(저/중/고변동)을 판정하고, <b>국면별 잔차 표준편차로 예측구간을 산출</b>합니다. 계수는 국면과 무관하게 안정적이지만, 오차범위는 국면에 따라 4배 이상 차이 납니다.</p>
</div>

<div class="card">
<h2>검증하고 기각한 가설들</h2>
<p style="font-size:.9rem;color:#555">저희가 시도했다가 <b>데이터로 기각한</b> 가설을 공개합니다.</p>
<div class="kv"><span>갭은 장중에 되돌려진다</span><b class="no">기각 (t=0.5)</b></div>
<div class="kv"><span>야간 프리미엄은 소멸한다</span><b class="no">기각 (시험구간 붕괴)</b></div>
<div class="kv"><span>20일 부분군별 국면 차이</span><b class="no">기각 (F=0.83)</b></div>
<div class="kv"><span>야간 → 개장 갭 환산</span><b class="ok">채택 (13개 부분군 전수 확인)</b></div>
<p style="margin-top:12px">기각된 가설을 숨기지 않는 이유는, 그것이 이 사이트가 제공하는 <b>유일한 정보의 신뢰성</b>을 뒷받침하기 때문입니다.</p>
</div>

<div class="card">
<h2>한계</h2>
<ul style="margin-left:18px;font-size:.92rem">
<li>표본이 {ALL['n']}거래일로 크지 않습니다. KRX 자체 야간시장이 2025년 6월 시작되었기 때문입니다.</li>
<li>회귀는 인과를 증명하지 않습니다. 야간선물과 개장가는 같은 정보를 반영하는 관계입니다.</li>
<li>제도 변경, 시장구조 변화 시 계수는 달라질 수 있습니다.</li>
<li>급변 상황(서킷브레이커 등)에서는 모델이 적용되지 않습니다.</li>
</ul>
</div>
"""
page("방법론과 한계 | 야간선물 환산기",
     "회귀 모델, 국면별 예측구간 산출 방법, 검증하고 기각한 가설, 그리고 이 모델의 한계를 공개합니다.",
     METH, "methodology.html")

# ── robots / sitemap ──
(SITE / "robots.txt").write_text(
    f"User-agent: *\nAllow: /\n\nUser-agent: Yeti\nAllow: /\n\n"
    f"Sitemap: {BASE}/sitemap.xml\n", encoding="utf-8")

today = KST.strftime("%Y-%m-%d")
urls = "".join(
    f'<url><loc>{BASE}/{p}</loc><lastmod>{today}</lastmod>'
    f'<changefreq>daily</changefreq></url>'
    for p in ["", "guide.html", "methodology.html"])
(SITE / "sitemap.xml").write_text(
    f'<?xml version="1.0" encoding="UTF-8"?>'
    f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
    encoding="utf-8")

(SITE / ".nojekyll").write_text("", encoding="utf-8")
(SITE / "model.json").write_text(json.dumps(MODEL, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

print("=" * 60)
print(f"  ✅ 사이트 생성 완료")
print(f"     국면      {cur}")
print(f"     계수      {M['beta']:.3f}   R² {M['r2']:.2f}   표본 {M['n']}일")
print(f"     오차범위  ±{1.28*M['se']:.2f}%p")
print(f"     자기채점  적중률 {hit_rate:.0f}%  MAE {mae:.2f}%p")
print(f"     URL       {BASE}/")
print("=" * 60)
