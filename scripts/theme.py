"""
공통 테마 — 브랜드·주소·메뉴·CSS를 여기서만 관리한다.
build_site.py / pages.py / posts.py 가 전부 이 파일을 참조한다.
"""
import datetime

BASE = "https://nightgap.co.kr"
BRAND_MAIN = "nightgap"
BRAND_SUB = ".co.kr"
TAGLINE = "간밤 해외 지표로 오늘 코스피 개장 갭을 환산합니다"

NAV = [("/", "대시보드"), ("/accuracy/", "적중 기록"), ("/archive/", "아카이브"),
       ("/posts/", "글"), ("/guide.html", "제도"), ("/methodology.html", "방법론")]

CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&display=swap');
:root{--bg:#0B1120;--surf:#131B2E;--surf2:#1A2438;--line:#263149;
--text:#E6EBF4;--dim:#8A96AC;--faint:#5A6780;--up:#FF5F56;--down:#46A2FF;
--warn:#FFB84D;--good:#3DD68C;--mono:'JetBrains Mono',ui-monospace,monospace}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font-family:Pretendard,-apple-system,'Malgun Gothic',sans-serif;
background:var(--bg);color:var(--text);font-size:15px;line-height:1.65;
padding:0 14px 40px;font-feature-settings:"tnum"}
.mono{font-family:var(--mono);font-feature-settings:"tnum"}
.w{max-width:660px;margin:0 auto}
header{padding:26px 0 14px;border-bottom:1px solid var(--line)}
.brand{font-size:1.35rem;font-weight:800;letter-spacing:-.03em}
.brand span{color:var(--faint);font-weight:500}
.tag{color:var(--dim);font-size:.84rem;margin-top:4px}
nav{display:flex;gap:16px;margin-top:14px;flex-wrap:wrap}
nav a{color:var(--dim);text-decoration:none;font-size:.85rem;
padding-bottom:4px;border-bottom:2px solid transparent}
nav a:hover,nav a.on{color:var(--text);border-color:var(--text)}
section{background:var(--surf);border:1px solid var(--line);
border-radius:10px;padding:20px;margin:16px 0}
.eyebrow{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;
color:var(--faint);font-weight:600;margin-bottom:14px}
h2{font-size:1rem;font-weight:700;margin-bottom:14px;letter-spacing:-.01em}
.hero{background:linear-gradient(170deg,#141E36 0%,#0F1728 100%);
border-color:#2C3A58;padding:22px 20px 18px}
.lead{color:var(--dim);font-size:.9rem;line-height:1.7;margin-bottom:18px;
padding-bottom:16px;border-bottom:1px solid rgba(255,255,255,.06)}
.lead b{color:var(--text);font-weight:600}
.hero .num{font-family:var(--mono);font-size:3.2rem;font-weight:800;
letter-spacing:-.04em;line-height:1;margin:4px 0 10px}
.hero .band{font-family:var(--mono);font-size:1rem;color:var(--dim)}
.hero .band b{color:var(--text);font-weight:600}
.pts{display:flex;gap:22px;margin:16px 0 4px;padding:14px 16px;
background:rgba(255,255,255,.03);border-radius:8px;flex-wrap:wrap}
.pts div{font-size:.76rem;color:var(--faint)}
.pts b{display:block;font-family:var(--mono);font-size:1.15rem;
color:var(--text);font-weight:700;margin-top:3px}
.pts em{display:block;font-style:normal;font-family:var(--mono);
font-size:.74rem;color:var(--faint);margin-top:2px}
.ruler{width:100%;height:auto;margin:14px 0 6px;display:block}
.howto{margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,.06)}
.howto .t{font-size:.72rem;letter-spacing:.12em;color:var(--faint);
font-weight:600;margin-bottom:9px}
.howto li{list-style:none;font-size:.84rem;color:var(--dim);
padding:4px 0 4px 14px;position:relative;line-height:1.6}
.howto li:before{content:'·';position:absolute;left:2px;color:var(--faint)}
.howto li b{color:var(--text);font-weight:600;font-family:var(--mono)}
.zero-warn{background:rgba(255,184,77,.09);border:1px solid rgba(255,184,77,.3);
border-radius:7px;padding:11px 13px;margin-top:12px;font-size:.85rem;
color:var(--warn);line-height:1.55}
.stat{display:flex;gap:20px;margin-top:14px;padding-top:14px;
border-top:1px solid var(--line);flex-wrap:wrap}
.stat div{font-size:.78rem;color:var(--faint)}
.stat b{display:block;font-family:var(--mono);font-size:.98rem;
color:var(--text);font-weight:600;margin-top:2px}
.up{color:var(--up)}.dn{color:var(--down)}
.ind{padding:12px 0;border-bottom:1px solid var(--line)}
.ind:last-child{border:0;padding-bottom:0}
.ind-top{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.ind-nm{font-weight:600;font-size:.92rem}
.ind-nm em{display:block;font-style:normal;font-size:.74rem;
color:var(--faint);font-weight:400;margin-top:1px}
.ind-v{font-family:var(--mono);font-size:.95rem;font-weight:600;
text-align:right;white-space:nowrap}
.ind-v em{display:block;font-style:normal;font-size:.74rem;
color:var(--faint);font-weight:400}
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
list-style:none;display:flex;justify-content:space-between;gap:12px}
summary::after{content:'+';color:var(--faint);font-family:var(--mono)}
details[open] summary::after{content:'−'}
details p{font-size:.87rem;color:var(--dim);padding:0 0 13px;line-height:1.7}
.kv{display:flex;justify-content:space-between;padding:9px 0;
border-bottom:1px solid var(--line);font-size:.88rem}
.kv:last-child{border:0}
.kv span{color:var(--dim)}
.kv b{font-family:var(--mono);font-weight:600}
.no{color:var(--up)}.yes{color:var(--good)}
.stamp{font-size:.74rem;color:var(--faint);margin-top:12px;font-family:var(--mono)}
footer{color:var(--faint);font-size:.76rem;padding:30px 0 10px;
line-height:1.9;border-top:1px solid var(--line);margin-top:26px}
footer a{color:var(--dim)}
@media(max-width:420px){.hero .num{font-size:2.6rem}section{padding:17px 15px}
.pts{gap:16px}}
"""


def shell(title, desc, body, path, site_dir, schema="", extra_css="", nav_on=""):
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    p = site_dir / path
    p.parent.mkdir(parents=True, exist_ok=True)
    url = path.replace("index.html", "")
    nav = "".join(f'<a href="{u}" class="{"on" if u == nav_on else ""}">{t}</a>'
                  for u, t in NAV)
    p.write_text(f'''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="{BASE}/{url}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:type" content="website"><meta property="og:url" content="{BASE}/{url}">
<meta name="theme-color" content="#0B1120">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
{schema}
<style>{CSS}{extra_css}</style></head><body><div class="w">
<header><div class="brand">{BRAND_MAIN}<span>{BRAND_SUB}</span></div>
<div class="tag">{TAGLINE}</div>
<nav>{nav}</nav></header>
{body}
<footer>데이터 · 한국거래소 KRX Open API, Yahoo Finance<br>
이 사이트는 과거 데이터의 통계적 관계만 계산합니다. 투자 조언이나 매매 권유가 아니며,
투자 판단의 근거로 사용될 수 없습니다.<br>
갱신 {kst:%Y-%m-%d %H:%M} KST</footer></div></body></html>''', encoding="utf-8")
