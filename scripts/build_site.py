"""
nightgap.co.kr 대시보드 빌더 v4
- 기준 종가: Yahoo(즉시) 우선, KRX(정본)와 교차검증
- 데이터가 오래되면 환산을 보류한다
"""
import json
import pathlib
import datetime
import pandas as pd
import requests
from theme import BASE, shell

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)
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


# ═══════════ 1. 실시간 해외지표 ═══════════
def quote(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"interval": "1d", "range": "5d"}, headers=UA, timeout=20)
    res = r.json()["chart"]["result"][0]
    c = [x for x in res["indicators"]["quote"][0]["close"] if x]
    t = datetime.datetime.utcfromtimestamp(
        res["meta"]["regularMarketTime"]) + datetime.timedelta(hours=9)
    return {"price": c[-1], "pct": (c[-1] / c[-2] - 1) * 100, "at": t}


def kospi_latest():
    """최신 코스피 종가.

    ⚠️ Yahoo 차트 API의 indicators.quote[].close 배열은 한국 지수의
       전일 값을 늦게 채운다 (Open/High/Low가 0.00으로 남고 날짜가 빠짐).
       반면 같은 응답의 meta.regularMarketPrice 는 마감 직후 즉시 갱신된다.
       야후 웹 화면이 보여주는 값이 바로 이 meta 값이다.

    3단계로 시도하고, 어느 경로가 쓰였는지 로그에 남긴다.
    ※ 시가(Open)는 Yahoo에서 절대 쓰지 않는다. KRX 공식만 사용한다.
    """
    # ① 차트 API의 meta 블록  (가장 신뢰. 인증 불필요)
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/^KS11",
                         params={"interval": "1d", "range": "5d"},
                         headers=UA, timeout=20)
        meta = r.json()["chart"]["result"][0]["meta"]
        px, ts = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
        if px and ts:
            d = (datetime.datetime.utcfromtimestamp(ts)
                 + datetime.timedelta(hours=9))
            print(f"    [소스] chart/meta  →  {d:%Y-%m-%d %H:%M} KST  {px:,.2f}")
            return d.date(), float(px)
        print("    [소스] chart/meta 실패: regularMarketPrice 없음")
    except Exception as e:
        print(f"    [소스] chart/meta 실패: {str(e)[:60]}")

    # ② 차트 API의 close 배열  (하루 늦을 수 있음)
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/^KS11",
                         params={"interval": "1d", "range": "1mo"},
                         headers=UA, timeout=20)
        res = r.json()["chart"]["result"][0]
        rows = [((datetime.datetime.utcfromtimestamp(t)
                  + datetime.timedelta(hours=9)).date(), c)
                for t, c in zip(res["timestamp"],
                                res["indicators"]["quote"][0]["close"]) if c]
        if rows:
            print(f"    [소스] chart/close 배열  →  {rows[-1][0]}  {rows[-1][1]:,.2f}")
            return rows[-1]
    except Exception as e:
        print(f"    [소스] chart/close 실패: {str(e)[:60]}")

    raise ValueError("Yahoo 코스피 종가 확보 실패")

live, fail = {}, []
for f in FEAT:
    try:
        live[f] = quote(SYM[f])
        print(f"  OK   {NAME[f]:<12} {live[f]['price']:>11,.2f}  {live[f]['pct']:+.2f}%")
    except Exception as e:
        fail.append(f)
        print(f"  FAIL {NAME[f]:<12} {e}")

# ═══════════ 2. 국면 판정 ═══════════
kr = pd.read_csv(ROOT / "data" / "kr_index.csv", parse_dates=["date"]).sort_values("date")
kr["r"] = kr["kospi_close"].pct_change() * 100
rv = float(kr["r"].rolling(20).std().iloc[-1])
regime = "저변동" if rv <= M["rv_lo"] else ("고변동" if rv >= M["rv_hi"] else "중변동")
R = M["regimes"][regime]

# ═══════════ 3. 기준 종가 (Yahoo 우선 + KRX 교차검증) ═══════════
krx_close = float(kr["kospi_close"].iloc[-1])
krx_date = kr["date"].iloc[-1].date()
stale = None

try:
    y_date, y_close = kospi_latest()
    last_close, last_date = y_close, y_date
    m = kr[kr["date"].dt.date == y_date]
    if len(m):
        diff = abs(float(m["kospi_close"].iloc[0]) / y_close - 1) * 100
        if diff > 0.1:
            stale = f"기준 종가 소스 간 불일치 {diff:.2f}% — 검증이 필요합니다"
        print(f"  기준종가  {y_date} {y_close:,.2f}  (KRX 대조 차이 {diff:+.3f}%)")
    else:
        print(f"  기준종가  {y_date} {y_close:,.2f}  (KRX 미공개 — Yahoo 단독)")
except Exception as e:
    last_close, last_date = krx_close, krx_date
    print(f"  Yahoo 실패 → KRX 사용: {e}")

age = (KST.date() - last_date).days
if age > 4:
    stale = f"기준 종가가 {age}일 전({last_date}) 데이터입니다"
print(f"  KRX 아카이브 최신 {krx_date} | 기준종가 경과 {age}일 | 국면 {regime}")

# ═══════════ 4. 환산 ═══════════
ok = not fail
gap = lo = hi = None
contrib, warn = [], None
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
    if stale:
        warn = stale

crosses = ok and lo < 0 < hi


def ruler(gap, lo, hi):
    W, H = 640, 132
    span = max(3.0, abs(lo) * 1.35, abs(hi) * 1.35)
    px = lambda v: W / 2 + (v / span) * (W / 2 - 30)
    col = "var(--up)" if gap >= 0 else "var(--down)"
    b0, b1 = px(lo), px(hi)
    ticks = "".join(
        f'<line x1="{px(t)}" y1="74" x2="{px(t)}" y2="80" stroke="var(--faint)" stroke-width="1"/>'
        f'<text x="{px(t)}" y="98" fill="var(--faint)" font-size="11" text-anchor="middle" '
        f'class="mono">{t:+.0f}%</text>'
        for t in [-span * .66, -span * .33, span * .33, span * .66])
    return f'''<svg viewBox="0 0 {W} {H}" class="ruler" role="img"
 aria-label="개장 갭 예상 {gap:+.2f}%, 80% 구간 {lo:+.2f}% ~ {hi:+.2f}%">
<text x="14" y="20" fill="var(--down)" font-size="11" letter-spacing=".08em">◀ 갭하락</text>
<text x="{W-14}" y="20" fill="var(--up)" font-size="11" text-anchor="end" letter-spacing=".08em">갭상승 ▶</text>
<line x1="20" y1="74" x2="{W-20}" y2="74" stroke="var(--line)" stroke-width="1"/>{ticks}
<rect x="{min(b0,b1)}" y="40" width="{abs(b1-b0)}" height="30" rx="2" fill="{col}" opacity="0.16"/>
<line x1="{b0}" y1="38" x2="{b0}" y2="72" stroke="{col}" stroke-width="1.5" opacity=".55"/>
<line x1="{b1}" y1="38" x2="{b1}" y2="72" stroke="{col}" stroke-width="1.5" opacity=".55"/>
<line x1="{W/2}" y1="30" x2="{W/2}" y2="82" stroke="var(--text)" stroke-width="1.5" opacity=".9"/>
<text x="{W/2}" y="118" fill="var(--dim)" font-size="11" text-anchor="middle" class="mono">0</text>
<circle cx="{px(gap)}" cy="55" r="6.5" fill="{col}"/>
<circle cx="{px(gap)}" cy="55" r="11" fill="none" stroke="{col}" stroke-width="1.5" opacity=".4"/>
</svg>'''


# ═══════════ 5. HERO ═══════════
LEAD = ('<div class="lead"><b>개장 갭</b>은 오늘 아침 코스피가 직전 종가보다 '
        '얼마나 높게(또는 낮게) 시작하는지를 말합니다.<br>'
        '아래 숫자는 <b>간밤 미국 시장 지표</b>로 환산한 값입니다. '
        '예측이 아니라, 이미 형성된 가격을 코스피 단위로 옮긴 것에 가깝습니다.</div>')

if ok and not warn:
    op = last_close * (1 + gap / 100)
    op_lo = last_close * (1 + lo / 100)
    op_hi = last_close * (1 + hi / 100)
    zw = ('<div class="zero-warn">예상 구간이 <b>0을 가로지릅니다.</b> '
          '상승·하락 방향조차 확정할 수 없습니다.</div>') if crosses else ""
    hero = f'''<section class="hero">
<div class="eyebrow">오늘 코스피 개장 갭 · 환산</div>
{LEAD}
<div class="num mono {'up' if gap >= 0 else 'dn'}">{gap:+.2f}%</div>
<div class="band">80% 구간 &nbsp;<b>{lo:+.2f}% ~ {hi:+.2f}%</b></div>

<div class="pts">
<div>직전 종가<b>{last_close:,.2f}</b><em>{last_date:%Y-%m-%d} 마감</em></div>
<div>환산 예상 시가<b class="{'up' if gap >= 0 else 'dn'}">{op:,.0f}</b>
<em>{op_lo:,.0f} ~ {op_hi:,.0f}</em></div>
</div>

{ruler(gap, lo, hi)}{zw}

<div class="howto"><div class="t">읽는 법</div><ul>
<li><b>{gap:+.2f}%</b> — 직전 종가보다 약 {abs(gap):.1f}% {'높게' if gap >= 0 else '낮게'} 시작할 것으로 환산됩니다</li>
<li><b>80% 구간</b> — 과거 사례 10번 중 약 8번은 이 범위 안에서 열렸습니다</li>
<li><b>구간이 0을 가로지르면</b> — 상승·하락 방향조차 확정할 수 없다는 뜻입니다</li>
<li><b>장중 흐름</b> — 개장 이후는 예측하지 않습니다 (R² 0.02, 무관)</li>
</ul></div>

<div class="stat">
<div>국면<b>{regime}</b></div>
<div>설명력 R²<b>{R['gap_r2']:.2f}</b></div>
<div>오차<b>±{1.28 * R['gap_se']:.2f}%p</b></div>
<div>표본<b>{R['n']}일</b></div>
</div></section>'''
elif ok and warn:
    hero = f'''<section class="hero">
<div class="eyebrow" style="color:var(--warn)">환산 보류</div>
{LEAD}
<div class="num mono" style="font-size:1.4rem;color:var(--warn);line-height:1.45">
숫자를 제시하지 않습니다</div>
<p style="color:var(--dim);font-size:.9rem;margin-top:10px">{warn}.
모델은 검증된 조건 안에서만 신뢰할 수 있습니다. 그 밖에서는
예측값을 내지 않는 것이 정직한 대응이라고 판단했습니다.</p>
<div class="stat">
<div>참고 계산값 (신뢰 불가)<b style="color:var(--faint)">{gap:+.2f}%</b></div>
<div>직전 종가<b>{last_close:,.2f}</b></div>
<div>기준일<b>{last_date:%m-%d}</b></div>
</div></section>'''
else:
    hero = f'''<section class="hero">
<div class="eyebrow" style="color:var(--warn)">데이터 수집 실패</div>{LEAD}
<div class="num mono" style="font-size:1.4rem;color:var(--warn)">환산 불가</div>
<p style="color:var(--dim);font-size:.9rem;margin-top:8px">
일부 지표를 가져오지 못했습니다. 부정확한 값을 제시하지 않습니다.</p></section>'''

# ═══════════ 6. 기여도 ═══════════
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
# ── 지표 신선도 판정: 미국장이 마감된 이후의 값인가 ──
hours_old = (KST - at).total_seconds() / 3600
if hours_old > 20:
    warn = (f"간밤 미국 지표가 {hours_old:.0f}시간 전 값입니다. "
            f"미국장이 아직 마감되지 않았거나 데이터가 지연되었습니다")
    print(f"  ⚠️ 지표 노후 {hours_old:.1f}시간")
else:
    print(f"  지표 신선도  {hours_old:.1f}시간 전 ({at:%m-%d %H:%M} KST 마감)")
reg_rows = "".join(
    f'<tr><td>{k}{"<span class=now>현재</span>" if k == regime else ""}</td>'
    f'<td>{v["n"]}</td><td>{v["gap_r2"]:.2f}</td><td>±{1.28 * v["gap_se"]:.2f}%p</td></tr>'
    for k, v in M["regimes"].items())

BODY = f'''{hero}

<section><div class="eyebrow">근거 · 간밤 해외 지표</div>
<h2>이 숫자들이 위의 갭을 만들었습니다</h2>
<p style="color:var(--dim);font-size:.88rem;margin-bottom:6px">
각 지표가 갭에 얼마나 기여했는지 분해했습니다. 막대가 오른쪽이면 갭을 위로,
왼쪽이면 아래로 밀었다는 뜻입니다.</p>
{inds}
<div class="stamp">미국장 마감 기준 · {at:%m월 %d일 %H:%M} KST
&nbsp;({hours_old:.0f}시간 전)</div></section>

<section><div class="eyebrow">국면별 정확도</div>
<h2>계수는 같지만, 오차는 국면마다 다릅니다</h2>
<table><thead><tr><th>국면</th><th>표본</th><th>R²</th><th>오차범위</th></tr></thead>
<tbody>{reg_rows}</tbody></table>
<p style="color:var(--dim);font-size:.84rem;margin-top:12px">
변동성이 큰 시기에는 같은 모델이라도 오차가 4배 가까이 커집니다.
하나의 오차범위를 고정하면 어느 한쪽에서는 반드시 거짓말이 됩니다.
그래서 매일 국면을 판정해 다르게 적용합니다.</p></section>

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
이 정도로 숫자를 내놓으면 오히려 오해를 만듭니다.</li>
<li><b>매매 조언을 하지 않습니다.</b> 간밤 등락은 개장 시점에 이미 가격에 반영됩니다.
아침에 이 값을 보고 매매해서 얻을 수 있는 것은 없습니다.</li>
<li><b>모르는 구간에서는 침묵합니다.</b> 지표가 과거 관측 범위를 벗어나거나
기준 데이터가 오래되면 숫자를 내지 않습니다.</li>
</ul></section>

<section><div class="eyebrow">자주 묻는 질문</div>
<details><summary>개장 갭이 정확히 무엇인가요</summary>
<p>오늘 코스피 시가를 직전 종가로 나눈 값입니다. 어제 7,400으로 끝났는데 오늘 7,474로 시작하면
갭은 +1%입니다. 한국 정규장이 닫힌 밤사이 나온 정보가 아침에 한꺼번에 반영되면서 생깁니다.</p></details>
<details><summary>이 숫자를 믿어도 되나요</summary>
<p>저희는 매일 예측과 실제를 대조해 공개합니다.
<a href="/accuracy/" style="color:var(--down)">적중 기록</a>에서 확인하실 수 있습니다.
80% 구간이라고 말한 범위의 실제 적중률은 80.2%였습니다.</p></details>
<details><summary>야간선물이 오르면 코스피도 오르나요</summary>
<p>개장 갭은 상당 부분 따라갑니다. 다만 이건 예측이 아니라 이미 형성된 가격의 환산에 가깝습니다.
개장 이후의 흐름은 별개이며, 저희는 예측하지 않습니다.</p></details>
<details><summary>그럼 아침에 사면 수익이 나나요</summary>
<p>아닙니다. 간밤 등락은 개장가에 거의 전부 반영되어 있습니다.
시가가 이미 그만큼 올라서 시작하므로, 그 가격에 사는 것으로는 아무것도 얻지 못합니다.</p></details>
<details><summary>야간선물 거래시간은 언제인가요</summary>
<p>KRX 야간 파생상품시장은 18:00부터 익일 06:00까지 12시간 운영되며, 호가 접수는 17:50부터입니다.
야간거래는 T+1일 거래로 처리되어 익일 정규거래와 같은 거래일로 집계됩니다.</p></details>
<details><summary>왜 야간선물이 아니라 미국 지표를 쓰나요</summary>
<p>KRX 공식 야간선물 데이터는 익일 08시에 공개됩니다. 개장 전에는 구할 수 없습니다.
그 시각에 확보 가능한 것은 미국 시장 데이터뿐이며, 정확도는 야간선물 기준 모델의
약 60% 수준입니다. 그만큼 오차범위를 넓게 잡습니다.</p></details>
</section>'''

shell("야간 갭 | 간밤 해외지표로 보는 오늘 코스피 개장 갭",
      f"간밤 미국 지표로 오늘 코스피 개장 갭을 환산합니다. "
      f"KRX 공식 데이터 {M['n']}거래일 기준, 오차범위와 한계를 함께 공개합니다.",
      BODY, "index.html", SITE, nav_on="/")

# ═══════════ 제도 ═══════════
shell("코스피200 야간선물 제도 정리 (2026년 기준)",
      "2025년 6월 9일 KRX 자체 야간 파생상품시장 전환 이후 기준. 거래시간 18:00~06:00, T+1 처리.",
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
      "guide.html", SITE, nav_on="/guide.html")

# ═══════════ 방법론 ═══════════
shell("방법론과 한계 | nightgap.co.kr",
      "회귀 모델, 국면별 예측구간 산출 방법, 검증 후 기각한 가설, 그리고 이 모델의 한계를 공개합니다.",
      f'''<section><div class="eyebrow">데이터</div>
<div class="kv"><span>출처</span><b>KRX 공식 Open API</b></div>
<div class="kv"><span>기간</span><b>{M['start']} ~ {M['end']}</b></div>
<div class="kv"><span>표본</span><b>{M['n']}거래일</b></div>
<div class="kv"><span>갱신</span><b>매 영업일 자동</b></div>
<p style="color:var(--dim);font-size:.86rem;margin-top:14px">
KRX 공식 데이터는 익일 08시에 공개됩니다. 개장 전 대시보드의 기준 종가는
Yahoo Finance 값을 쓰되, KRX 공식값과 교차검증합니다. 두 값이 0.1% 이상
어긋나면 환산을 보류합니다.</p></section>

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
모든 가설이 통과했다면 검증 자체를 의심해야 합니다.</p></section>

<section class="limit"><div class="eyebrow">한계</div>
<ul>
<li>표본이 <b>{M['n']}거래일</b>로 크지 않습니다. KRX 자체 야간시장이 2025년 6월에 시작되었기 때문입니다.</li>
<li>회귀는 인과를 증명하지 않습니다. 야간선물과 개장가는 <b>같은 정보를 반영하는 관계</b>입니다.</li>
<li>고변동 국면에서는 오차범위가 <b>4배 가까이</b> 커집니다.</li>
<li>과거 관측 범위를 벗어난 급변 상황에서는 <b>환산값을 제시하지 않습니다.</b></li>
<li>제도나 시장 구조가 바뀌면 계수는 달라질 수 있습니다.</li>
</ul></section>''',
      "methodology.html", SITE, nav_on="/methodology.html")

# ═══════════ robots / sitemap ═══════════
(SITE / "robots.txt").write_text(
    f"User-agent: *\nAllow: /\n\nUser-agent: Yeti\nAllow: /\n\n"
    f"User-agent: Googlebot\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n",
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
print("  빌드 완료")
print(f"    기준 종가  {last_close:,.2f}  ({last_date})  경과 {age}일")
print(f"    국면       {regime} (rv20={rv:.2f})")
if ok:
    print(f"    환산 갭    {gap:+.2f}%  [{lo:+.2f} ~ {hi:+.2f}]")
    print(f"    예상 시가  {last_close * (1 + gap / 100):,.0f}")
print(f"    0 가로지름 {'예 — 방향 불확정' if crosses else '아니오'}")
print(f"    경고       {warn or '없음'}")
print("=" * 60)
