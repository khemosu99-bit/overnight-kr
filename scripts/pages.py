"""
확장 페이지 생성기
- /accuracy/   예측 적중 기록 (매일 누적)
- /archive/YYYY-MM/  월별 갭 아카이브
- /kosdaq/     코스닥
- /data/       데이터 공개
"""
import json
import pathlib
import datetime
import numpy as np
import pandas as pd
from theme import BASE, shell

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

M = json.loads((ROOT / "data" / "model2.json").read_text(encoding="utf-8"))
FEAT = M["features"]


def page(title, desc, body, path):
    shell(title, desc, body, path, SITE)


# ═══════════ 데이터 준비 ═══════════
kr = pd.read_csv(ROOT / "data" / "kr_index.csv", parse_dates=["date"]).sort_values("date")
nf = pd.read_csv(ROOT / "data" / "night_futures.csv", parse_dates=["date"])
nf = nf[["date", "night_close", "reg_close"]]
d = kr.merge(nf, on="date", how="left").sort_values("date").reset_index(drop=True)

for m in ["kospi", "kosdaq"]:
    p = d[f"{m}_close"].shift(1)
    d[f"{m}_gap"] = (d[f"{m}_open"] / p - 1) * 100
    d[f"{m}_full"] = (d[f"{m}_close"] / p - 1) * 100
    d[f"{m}_intra"] = (d[f"{m}_close"] / d[f"{m}_open"] - 1) * 100

d["night_r"] = (d["night_close"] / d["reg_close"].shift(1) - 1) * 100
d["rv20"] = d["kospi_full"].rolling(20).std()


def load_us(n):
    x = pd.read_csv(ROOT / "data" / "raw" / f"{n}.csv", parse_dates=["Date"])
    x["Date"] = x["Date"].dt.tz_localize(None).dt.normalize()
    x = x[["Date", "Close"]].dropna().sort_values("Date")
    x[f"{n}_r"] = x["Close"].pct_change() * 100
    return x[["Date", f"{n}_r"]].dropna().rename(columns={"Date": "date"})


for f in FEAT:
    d = pd.merge_asof(d.sort_values("date"), load_us(f.replace("_r", "")),
                      on="date", direction="backward", allow_exact_matches=False)

e = d.dropna(subset=["kospi_gap", "rv20"] + FEAT).copy()


def predict(row):
    rg = ("저변동" if row["rv20"] <= M["rv_lo"]
          else "고변동" if row["rv20"] >= M["rv_hi"] else "중변동")
    R = M["regimes"][rg]
    co = R["gap_coef"]
    v = co[0] + sum(co[i + 1] * row[f] for i, f in enumerate(FEAT))
    return pd.Series({"pred": v, "regime": rg, "band": 1.28 * R["gap_se"]})


e = pd.concat([e, e.apply(predict, axis=1)], axis=1)
e["err"] = (e["pred"] - e["kospi_gap"]).abs()
e["hit"] = e["err"] <= e["band"]
e["dir"] = (e["pred"] > 0) == (e["kospi_gap"] > 0)

# ═══════════ 1. /accuracy/ ═══════════
n = len(e)
hit = e["hit"].mean() * 100
mae = e["err"].mean()
dirr = e["dir"].mean() * 100
rmse = np.sqrt((e["pred"] - e["kospi_gap"]).pow(2).mean())
verdict = ("약속한 80%에 근접합니다" if 75 <= hit <= 87 else
           "약속한 80%보다 낮습니다. 모델이 오차를 과소평가하고 있습니다" if hit < 75 else
           "약속한 80%보다 높습니다. 오차범위를 보수적으로 잡고 있습니다")
vcol = "yes" if 75 <= hit <= 87 else "no"

rows = "".join(
    f'<tr><td>{r["date"]:%m-%d}</td>'
    f'<td class="{"up" if r["pred"]>=0 else "dn"}">{r["pred"]:+.2f}%</td>'
    f'<td class="{"up" if r["kospi_gap"]>=0 else "dn"}">{r["kospi_gap"]:+.2f}%</td>'
    f'<td>{r["err"]:.2f}%p</td>'
    f'<td class="{"yes" if r["hit"] else "no"}">{"적중" if r["hit"] else "벗어남"}</td></tr>'
    for _, r in e.tail(30).iloc[::-1].iterrows())

by_reg = "".join(
    f'<tr><td>{g}</td><td>{len(s)}</td>'
    f'<td class="{"yes" if 75 <= s["hit"].mean()*100 <= 87 else "no"}">'
    f'{s["hit"].mean()*100:.1f}%</td><td>{s["err"].mean():.2f}%p</td>'
    f'<td>{s["dir"].mean()*100:.1f}%</td></tr>'
    for g, s in e.groupby("regime") if len(s) > 5)

page("예측 적중 기록 | nightgap.co.kr",
     f"{n}거래일 전체 예측을 실제 결과와 대조합니다. 80% 구간 적중률 {hit:.1f}%, "
     f"평균 절대오차 {mae:.2f}%p. 틀린 날도 그대로 공개합니다.",
     f'''<section class="hero"><div class="eyebrow">예측 적중 기록</div>
<div class="lead">저희는 매일 <b>"80% 확률로 이 범위 안"</b>이라고 말합니다.<br>
그 약속이 실제로 지켜졌는지를 전체 표본에 대해 검증한 것이 이 페이지입니다.</div>
<div class="num mono {vcol}">{hit:.1f}%</div>
<div class="band">80% 구간 적중률 · 표본 <b>{n}일</b></div>
<div class="zero-warn" style="color:var(--{'good' if vcol == 'yes' else 'up'});
 background:rgba(61,214,140,.08);border-color:rgba(61,214,140,.3)">{verdict}</div>
<div class="stat">
<div>평균 절대오차<b>{mae:.2f}%p</b></div>
<div>RMSE<b>{rmse:.2f}%p</b></div>
<div>방향 적중<b>{dirr:.1f}%</b></div>
</div></section>

<section><div class="eyebrow">이 페이지의 존재 이유</div>
<h2>80%라고 했으면 80%가 맞아야 합니다</h2>
<p style="color:var(--dim);font-size:.9rem">
적중률이 80%보다 <b style="color:var(--text)">낮으면</b> 모델이 자신을 과신하는 것이고,
<b style="color:var(--text)">높으면</b> 오차를 지나치게 넓게 잡은 것입니다. 둘 다 문제입니다.</p>
<p style="color:var(--dim);font-size:.9rem;margin-top:10px">
<b style="color:var(--text)">틀린 날을 지우지 않습니다.</b>
아래 표에 벗어난 날이 그대로 남아 있습니다.</p></section>

<section><div class="eyebrow">국면별 적중률</div>
<table><thead><tr><th>국면</th><th>표본</th><th>구간 적중</th><th>평균오차</th><th>방향</th></tr></thead>
<tbody>{by_reg}</tbody></table>
<p style="color:var(--dim);font-size:.84rem;margin-top:12px">
어느 국면에서든 80%에 가까워야 정상입니다. 특정 국면에서 크게 벗어나면
그 구간의 오차범위 설정이 잘못된 것입니다.</p></section>

<section><div class="eyebrow">최근 30거래일</div>
<table><thead><tr><th>날짜</th><th>예측</th><th>실제</th><th>오차</th><th>판정</th></tr></thead>
<tbody>{rows}</tbody></table></section>''',
     "accuracy/index.html")

# ═══════════ 2. /archive/YYYY-MM/ ═══════════
e["ym"] = e["date"].dt.to_period("M")
months = [m for m in sorted(e["ym"].unique(), reverse=True) if len(e[e["ym"] == m]) >= 3]

for ym in months:
    s = e[e["ym"] == ym]
    y, mo = str(ym).split("-")
    up = int((s["kospi_gap"] > 0).sum())
    body_rows = ""
    for _, r in s.iterrows():
        nr = (f'<td class="{"up" if r["night_r"] >= 0 else "dn"}">{r["night_r"]:+.2f}%</td>'
              if pd.notna(r["night_r"]) else '<td style="color:var(--faint)">—</td>')
        body_rows += (
            f'<tr><td>{r["date"]:%m-%d}</td>{nr}'
            f'<td class="{"up" if r["kospi_gap"] >= 0 else "dn"}">{r["kospi_gap"]:+.2f}%</td>'
            f'<td class="{"up" if r["kospi_intra"] >= 0 else "dn"}">{r["kospi_intra"]:+.2f}%</td>'
            f'<td class="{"up" if r["kospi_full"] >= 0 else "dn"}">{r["kospi_full"]:+.2f}%</td>'
            f'<td>{r["kospi_close"]:,.0f}</td></tr>')

    page(f"{y}년 {int(mo)}월 코스피 개장 갭 기록 | nightgap.co.kr",
         f"{y}년 {int(mo)}월 코스피 개장 갭 전체 기록. {len(s)}거래일 중 갭상승 {up}일. "
         f"야간선물 등락, 개장 갭, 장중 흐름, 종가를 일별로 정리했습니다.",
         f'''<section class="hero"><div class="eyebrow">월별 아카이브</div>
<div class="num mono" style="font-size:2.2rem">{y}년 {int(mo)}월</div>
<div class="band">코스피 개장 갭 · <b>{len(s)}거래일</b></div>
<div class="stat">
<div>갭상승<b class="up">{up}일</b></div>
<div>갭하락<b class="dn">{len(s) - up}일</b></div>
<div>평균 갭<b>{s["kospi_gap"].mean():+.2f}%</b></div>
<div>월 등락<b class="{'up' if s["kospi_full"].sum() >= 0 else 'dn'}">{s["kospi_full"].sum():+.1f}%</b></div>
</div></section>

<section><div class="eyebrow">일별 기록</div>
<table><thead><tr><th>날짜</th><th>야간선물</th><th>개장 갭</th><th>장중</th><th>종가등락</th><th>코스피</th></tr></thead>
<tbody>{body_rows}</tbody></table>
<p style="color:var(--dim);font-size:.82rem;margin-top:12px">
야간선물 = 전일 정규 종가 대비 야간 종가 · 개장 갭 = 전일 종가 대비 시가 ·
장중 = 시가 대비 종가 · 종가등락 = 전일 종가 대비 종가</p></section>

<section><div class="eyebrow">이 달의 통계</div>
<div class="kv"><span>평균 개장 갭</span><b>{s["kospi_gap"].mean():+.2f}%</b></div>
<div class="kv"><span>갭 표준편차</span><b>{s["kospi_gap"].std():.2f}%</b></div>
<div class="kv"><span>최대 갭상승</span><b class="up">{s["kospi_gap"].max():+.2f}%</b></div>
<div class="kv"><span>최대 갭하락</span><b class="dn">{s["kospi_gap"].min():+.2f}%</b></div>
<div class="kv"><span>평균 장중 흐름</span><b>{s["kospi_intra"].mean():+.2f}%</b></div>
<div class="kv"><span>모델 구간 적중률</span>
<b class="{"yes" if s["hit"].mean() > 0.7 else "no"}">{s["hit"].mean()*100:.0f}%</b></div>
</section>''',
         f"archive/{ym}/index.html")

mlist = "".join(
    f'<div class="kv"><span><a href="/archive/{ym}/" style="color:var(--text);'
    f'text-decoration:none">{str(ym).replace("-", "년 ")}월</a></span>'
    f'<b>{len(e[e["ym"] == ym])}거래일 · 평균 갭 {e[e["ym"] == ym]["kospi_gap"].mean():+.2f}%</b></div>'
    for ym in months)

page("월별 갭 아카이브 | nightgap.co.kr",
     "코스피 개장 갭 월별 전체 기록. 야간선물 등락, 개장 갭, 장중 흐름, 종가를 일별로 보관합니다.",
     f'''<section class="hero"><div class="eyebrow">아카이브</div>
<div class="num mono" style="font-size:2.4rem">{len(e)}일</div>
<div class="band">기록된 거래일 · <b>{e["date"].min():%Y.%m} ~ {e["date"].max():%Y.%m}</b></div>
</section>
<section><div class="eyebrow">월별</div>{mlist}</section>
<section><div class="eyebrow">전체 통계</div>
<div class="kv"><span>평균 개장 갭</span><b>{e["kospi_gap"].mean():+.2f}%</b></div>
<div class="kv"><span>갭상승 비율</span><b>{(e["kospi_gap"] > 0).mean()*100:.1f}%</b></div>
<div class="kv"><span>평균 장중 흐름</span><b>{e["kospi_intra"].mean():+.2f}%</b></div>
<div class="kv"><span>갭 표준편차</span><b>{e["kospi_gap"].std():.2f}%</b></div>
</section>''',
     "archive/index.html")

# ═══════════ 3. /kosdaq/ ═══════════
q = e.dropna(subset=["kosdaq_gap"])
kq_rows = "".join(
    f'<tr><td>{r["date"]:%m-%d}</td>'
    f'<td class="{"up" if r["kosdaq_gap"] >= 0 else "dn"}">{r["kosdaq_gap"]:+.2f}%</td>'
    f'<td class="{"up" if r["kosdaq_intra"] >= 0 else "dn"}">{r["kosdaq_intra"]:+.2f}%</td>'
    f'<td class="{"up" if r["kosdaq_full"] >= 0 else "dn"}">{r["kosdaq_full"]:+.2f}%</td>'
    f'<td>{r["kosdaq_close"]:,.1f}</td></tr>'
    for _, r in q.tail(15).iloc[::-1].iterrows())

page("코스닥 개장 갭 | nightgap.co.kr",
     "간밤 해외 지표로 보는 코스닥 개장 갭. 코스피 대비 설명력이 낮으며, 그 차이를 함께 공개합니다.",
     f'''<section class="hero"><div class="eyebrow">코스닥</div>
<div class="lead">같은 방법을 코스닥에 적용하면 <b>설명력이 떨어집니다.</b><br>
그 사실을 숨기지 않고 그대로 보여드립니다.</div>
<div class="num mono" style="font-size:1.9rem;line-height:1.35">코스피보다<br>덜 설명됩니다</div>
<div class="band" style="margin-top:12px">개장 갭 R² <b>0.58</b> · 종가 R² <b>0.21</b></div>
</section>

<section><div class="eyebrow">왜 다른가</div>
<h2>코스닥은 국내 요인이 더 큽니다</h2>
<p style="color:var(--dim);font-size:.9rem">
코스피는 삼성전자·SK하이닉스 등 미국 반도체 업황에 직결된 대형주 비중이 큽니다.
반면 코스닥은 국내 중소형주·바이오·테마주 비중이 높아, 간밤 미국 지표로 설명되는 부분이 작습니다.</p>
<div class="kv" style="margin-top:14px"><span>코스피 개장 갭 R²</span><b>0.67</b></div>
<div class="kv"><span>코스닥 개장 갭 R²</span><b>0.58</b></div>
<div class="kv"><span>코스피 종가 R²</span><b>0.37</b></div>
<div class="kv"><span>코스닥 종가 R²</span><b>0.21</b></div></section>

<section><div class="eyebrow">과거 사례 · 코스닥 종가</div>
<table><thead><tr><th>간밤 조건</th><th>횟수</th><th>종가 평균</th><th>상승 마감</th></tr></thead><tbody>
<tr><td>야간 +1% 이상</td><td>57</td><td class="up">+0.88%</td><td>61.4%</td></tr>
<tr><td>야간 +0.3~1%</td><td>64</td><td class="up">+0.79%</td><td>67.2%</td></tr>
<tr><td>야간 −0.3~−1%</td><td>36</td><td class="dn">−0.40%</td><td>41.7%</td></tr>
<tr><td>야간 −1% 이하</td><td>36</td><td class="dn">−2.23%</td><td>33.3%</td></tr>
</tbody></table></section>

<section><div class="eyebrow">최근 15거래일</div>
<table><thead><tr><th>날짜</th><th>개장 갭</th><th>장중</th><th>종가등락</th><th>코스닥</th></tr></thead>
<tbody>{kq_rows}</tbody></table></section>''',
     "kosdaq/index.html")

# ═══════════ 4. /data/ ═══════════
page("데이터 공개 | nightgap.co.kr",
     "KRX 공식 야간선물·지수 데이터와 분석 코드를 전부 공개합니다. 누구나 검증할 수 있습니다.",
     f'''<section class="hero"><div class="eyebrow">데이터 공개</div>
<div class="lead">저희 주장을 믿지 마시고, <b>직접 확인하십시오.</b><br>
수집 스크립트부터 회귀 코드까지 전부 공개되어 있습니다.</div>
<div class="num mono" style="font-size:1.9rem;line-height:1.35">검증하십시오</div>
</section>

<section><div class="eyebrow">공개하는 것</div>
<div class="kv"><span>야간선물 일별 (KRX)</span><b>{len(nf)}일</b></div>
<div class="kv"><span>코스피·코스닥 지수 (KRX)</span><b>{len(kr)}일</b></div>
<div class="kv"><span>해외 지표 (Yahoo)</span><b>{len(FEAT)}종</b></div>
<div class="kv"><span>분석 코드</span><b>전체 공개</b></div>
<p style="margin-top:16px"><a href="https://github.com/khemosu99-bit/overnight-kr"
 style="color:var(--down)">GitHub 저장소 →</a></p></section>

<section class="limit"><div class="eyebrow">출처와 한계</div>
<ul>
<li>야간선물·지수 데이터는 <b>한국거래소(KRX) Open API</b>의 공식 데이터입니다.</li>
<li>해외 지표는 Yahoo Finance에서 수집하며, <b>비공식 경로</b>이므로 중단될 수 있습니다.</li>
<li>KRX 데이터는 <b>익일 08시</b>에 갱신됩니다. 실시간이 아닙니다.</li>
<li>데이터의 상업적 재배포는 각 제공처의 이용 조건을 따릅니다.</li>
</ul></section>''',
     "data/index.html")

# ═══════════ 사이트맵 ═══════════
today = KST.strftime("%Y-%m-%d")
urls = ["", "guide.html", "methodology.html", "accuracy/", "archive/", "kosdaq/", "data/"]
urls += [f"archive/{ym}/" for ym in months]
(SITE / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
    "".join(f'<url><loc>{BASE}/{u}</loc><lastmod>{today}</lastmod>'
            f'<changefreq>{"daily" if u in ("", "accuracy/", "kosdaq/") else "weekly"}</changefreq>'
            f'<priority>{"1.0" if u == "" else "0.8"}</priority></url>' for u in urls) +
    '</urlset>', encoding="utf-8")

print("=" * 62)
print(f"  페이지 생성 완료")
print(f"    /accuracy/   구간 적중률 {hit:.1f}%  (목표 80%)")
print(f"                 평균오차 {mae:.2f}%p · 방향 {dirr:.1f}%")
print(f"    /archive/    {len(months)}개월")
print(f"    /kosdaq/  /data/")
print(f"    sitemap      {len(urls)}개 URL")
print("=" * 62)
print(f"\n  판정: {verdict}")
