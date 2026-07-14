"""
글 발행 시스템
- posts/*.md 를 읽어 HTML 페이지로 자동 변환
- 목록 페이지 생성, 사이트맵 등록
- 마크다운 라이브러리 없이 순수 파이썬으로 처리 (의존성 최소화)
"""
import re
import html
import pathlib
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
POSTS = ROOT / "posts"
POSTS.mkdir(exist_ok=True)
BASE = "https://nightgap.kr"
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

CSS = (SITE / "index.html").read_text(encoding="utf-8").split("<style>")[1].split("</style>")[0]

EXTRA = """
.prose h2{font-size:1.15rem;margin:30px 0 12px;padding-bottom:0;border:0;
  letter-spacing:-.01em;color:var(--text)}
.prose h2:first-child{margin-top:0}
.prose h3{font-size:1rem;font-weight:600;margin:22px 0 8px;color:var(--text)}
.prose p{color:var(--dim);margin:12px 0;line-height:1.85;font-size:.95rem}
.prose strong{color:var(--text);font-weight:600}
.prose ul,.prose ol{margin:12px 0 12px 20px;color:var(--dim);font-size:.95rem}
.prose li{margin:7px 0;line-height:1.8}
.prose a{color:var(--down);text-decoration:none;border-bottom:1px solid rgba(70,162,255,.3)}
.prose a:hover{border-color:var(--down)}
.prose code{font-family:var(--mono);background:var(--surf2);padding:2px 6px;
  border-radius:4px;font-size:.86em;color:var(--text)}
.prose blockquote{border-left:3px solid var(--line);padding:4px 0 4px 16px;
  margin:18px 0;color:var(--faint);font-size:.93rem}
.prose hr{border:0;border-top:1px solid var(--line);margin:26px 0}
.prose table{margin:18px 0}
.post-meta{color:var(--faint);font-size:.8rem;font-family:var(--mono);
  padding-bottom:16px;margin-bottom:22px;border-bottom:1px solid var(--line)}
.post-item{display:block;padding:16px 0;border-bottom:1px solid var(--line);
  text-decoration:none;color:inherit}
.post-item:last-child{border:0}
.post-item h3{font-size:1rem;font-weight:600;color:var(--text);margin-bottom:5px;
  letter-spacing:-.01em}
.post-item p{color:var(--dim);font-size:.87rem;line-height:1.6}
.post-item time{font-family:var(--mono);font-size:.74rem;color:var(--faint);
  display:block;margin-top:7px}
.post-item:hover h3{color:var(--down)}
"""


def md(text):
    """최소 마크다운 → HTML. 필요한 것만."""
    out, in_ul, in_ol = [], False, False
    for ln in text.split("\n"):
        s = ln.rstrip()

        def close():
            nonlocal in_ul, in_ol
            if in_ul:
                out.append("</ul>"); in_ul = False
            if in_ol:
                out.append("</ol>"); in_ol = False

        if not s.strip():
            close(); continue
        if s.startswith("### "):
            close(); out.append(f"<h3>{inline(s[4:])}</h3>"); continue
        if s.startswith("## "):
            close(); out.append(f"<h2>{inline(s[3:])}</h2>"); continue
        if s.startswith("> "):
            close(); out.append(f"<blockquote>{inline(s[2:])}</blockquote>"); continue
        if s.strip() in ("---", "***"):
            close(); out.append("<hr>"); continue
        if re.match(r"^[-*] ", s):
            if not in_ul:
                close(); out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(s[2:])}</li>"); continue
        if re.match(r"^\d+\. ", s):
            if not in_ol:
                close(); out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(re.sub(r'^\d+\. ', '', s))}</li>"); continue
        close()
        out.append(f"<p>{inline(s)}</p>")
    if in_ul: out.append("</ul>")
    if in_ol: out.append("</ol>")
    return "\n".join(out)


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


def parse(p):
    """--- 로 감싼 머리말(front matter) + 본문"""
    raw = p.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for ln in parts[1].strip().split("\n"):
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"').strip("'")
            body = parts[2]
    m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)", p.stem)
    meta.setdefault("date", m.group(1) if m else KST.strftime("%Y-%m-%d"))
    meta["slug"] = m.group(2) if m else p.stem
    meta.setdefault("title", meta["slug"])
    meta.setdefault("summary", "")
    return meta, body


def page(title, desc, body, path):
    p = SITE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    url = path.replace("index.html", "")
    nav = "".join(f'<a href="{u}">{t}</a>' for u, t in [
        ("/", "대시보드"), ("/accuracy/", "적중 기록"), ("/archive/", "아카이브"),
        ("/posts/", "글"), ("/methodology.html", "방법론")])
    p.write_text(f'''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="{BASE}/{url}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:type" content="article"><meta name="theme-color" content="#0B1120">
<meta name="robots" content="index,follow,max-snippet:-1">
<style>{CSS}{EXTRA}</style></head><body><div class="w">
<header><div class="brand">nightgap<span>.kr</span></div>
<div class="tag">간밤 해외 지표로 오늘 코스피 개장 갭을 환산합니다</div>
<nav>{nav}</nav></header>
{body}
<footer>데이터 · 한국거래소 KRX Open API, Yahoo Finance<br>
과거 데이터의 통계적 관계만 계산합니다. 투자 조언이 아닙니다.<br>
갱신 {KST:%Y-%m-%d %H:%M} KST</footer></div></body></html>''', encoding="utf-8")
    return url


# ═══════════ 글 변환 ═══════════
items = []
for f in sorted(POSTS.glob("*.md"), reverse=True):
    meta, body = parse(f)
    slug = meta["slug"]
    page(f"{meta['title']} | nightgap.kr",
         meta["summary"] or meta["title"],
         f'''<section><div class="eyebrow">글</div>
<h2 style="font-size:1.4rem;margin-bottom:10px;line-height:1.4">{html.escape(meta['title'])}</h2>
<div class="post-meta">{meta['date']}</div>
<div class="prose">{md(body)}</div></section>

<section><div class="eyebrow">함께 보기</div>
<div class="kv"><span><a href="/" style="color:var(--text);text-decoration:none">오늘의 개장 갭 환산</a></span><b>→</b></div>
<div class="kv"><span><a href="/accuracy/" style="color:var(--text);text-decoration:none">예측 적중 기록</a></span><b>→</b></div>
<div class="kv"><span><a href="/methodology.html" style="color:var(--text);text-decoration:none">방법론과 한계</a></span><b>→</b></div>
</section>''',
         f"posts/{slug}/index.html")
    items.append(meta)
    print(f"  발행  {meta['date']}  {meta['title']}")

# ═══════════ 목록 페이지 ═══════════
if items:
    lst = "".join(
        f'<a class="post-item" href="/posts/{i["slug"]}/">'
        f'<h3>{html.escape(i["title"])}</h3>'
        f'<p>{html.escape(i["summary"])}</p>'
        f'<time>{i["date"]}</time></a>' for i in items)
else:
    lst = '<p style="color:var(--faint);font-size:.9rem">아직 발행된 글이 없습니다.</p>'

page("글 | nightgap.kr",
     "야간선물, 개장 갭, 해외 지표에 대한 해설과 기록.",
     f'''<section class="hero"><div class="eyebrow">글</div>
<div class="num mono" style="font-size:2.2rem">{len(items)}편</div>
<div class="band">야간선물과 개장 갭에 대한 해설</div></section>
<section><div class="eyebrow">전체</div>{lst}</section>''',
     "posts/index.html")

# ═══════════ 사이트맵에 추가 ═══════════
sm = SITE / "sitemap.xml"
if sm.exists() and items:
    x = sm.read_text(encoding="utf-8")
    add = "".join(
        f'<url><loc>{BASE}/posts/{i["slug"]}/</loc>'
        f'<lastmod>{i["date"]}</lastmod><changefreq>monthly</changefreq>'
        f'<priority>0.7</priority></url>' for i in items)
    add += (f'<url><loc>{BASE}/posts/</loc>'
            f'<lastmod>{KST:%Y-%m-%d}</lastmod><priority>0.8</priority></url>')
    sm.write_text(x.replace("</urlset>", add + "</urlset>"), encoding="utf-8")

print("=" * 56)
print(f"  글 {len(items)}편 발행 완료  →  /posts/")
print("=" * 56)
