"""
글 발행 시스템 v2
- 마크다운 → HTML (목차·요약·박스·FAQ·JSON-LD 자동)
- 특수 문법으로 정보박스/경고박스/체크리스트/FAQ를 쉽게 작성
"""
import re
import json
import html
import pathlib
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
POSTS = ROOT / "posts"
POSTS.mkdir(exist_ok=True)
BASE = "https://nightgap.co.kr"
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

CSS = (SITE / "index.html").read_text(encoding="utf-8").split("<style>")[1].split("</style>")[0]

EXTRA = """
.prose h2{font-size:1.18rem;margin:34px 0 12px;padding:0;border:0;
  letter-spacing:-.01em;color:var(--text);scroll-margin-top:20px}
.prose h2:first-child{margin-top:0}
.prose h3{font-size:1.02rem;font-weight:600;margin:24px 0 8px;color:var(--text)}
.prose p{color:var(--dim);margin:12px 0;line-height:1.85;font-size:.95rem}
.prose strong{color:var(--text);font-weight:600}
.prose ul,.prose ol{margin:12px 0 12px 20px;color:var(--dim);font-size:.95rem}
.prose li{margin:7px 0;line-height:1.8}
.prose a{color:var(--down);text-decoration:none;border-bottom:1px solid rgba(70,162,255,.32)}
.prose code{font-family:var(--mono);background:var(--surf2);padding:2px 6px;
  border-radius:4px;font-size:.86em;color:var(--text)}
.prose blockquote{border-left:3px solid var(--line);padding:4px 0 4px 16px;
  margin:18px 0;color:var(--faint);font-size:.93rem}
.prose hr{border:0;border-top:1px solid var(--line);margin:28px 0}
.prose table{margin:18px 0;width:100%}
.prose thead th{font-size:.72rem}

/* 핵심 요약 */
.tldr{background:var(--surf2);border:1px solid #2E3D5C;border-radius:9px;
  padding:17px 18px;margin:0 0 24px}
.tldr .lb{font-size:.7rem;letter-spacing:.14em;color:var(--faint);
  font-weight:700;margin-bottom:9px}
.tldr p{color:var(--text);font-size:.96rem;margin:0 0 10px;line-height:1.75}
.tldr ul{margin:0 0 0 18px;color:var(--dim);font-size:.9rem}
.tldr li{margin:5px 0}

/* 목차 */
.toc{border:1px dashed var(--line);border-radius:9px;padding:15px 18px;margin:0 0 26px}
.toc .lb{font-size:.7rem;letter-spacing:.14em;color:var(--faint);
  font-weight:700;margin-bottom:9px}
.toc ol{margin:0 0 0 18px;font-size:.9rem}
.toc li{margin:5px 0}
.toc a{color:var(--dim);text-decoration:none;border:0}
.toc a:hover{color:var(--text)}

/* 박스 */
.box{border-radius:9px;padding:15px 17px;margin:20px 0;font-size:.92rem;line-height:1.75}
.box .bt{font-weight:700;margin-bottom:7px;font-size:.92rem}
.box p{margin:0;color:inherit;font-size:.92rem}
.box ul{margin:8px 0 0 18px;font-size:.9rem}
.box-info{background:rgba(70,162,255,.07);border:1px solid rgba(70,162,255,.28);color:var(--dim)}
.box-info .bt{color:var(--down)}
.box-warn{background:rgba(255,184,77,.07);border:1px solid rgba(255,184,77,.3);color:var(--dim)}
.box-warn .bt{color:var(--warn)}
.box-check{background:var(--surf2);border:1px solid var(--line);color:var(--dim)}
.box-check .bt{color:var(--text)}
.box-check ul{list-style:none;margin-left:0}
.box-check li{padding:5px 0 5px 24px;position:relative}
.box-check li:before{content:'☐';position:absolute;left:0;color:var(--faint);
  font-family:var(--mono)}

/* FAQ */
.faq h2{margin-bottom:4px}
.post-meta{color:var(--faint);font-size:.8rem;font-family:var(--mono);
  padding-bottom:16px;margin-bottom:22px;border-bottom:1px solid var(--line)}
.post-item{display:block;padding:16px 0;border-bottom:1px solid var(--line);
  text-decoration:none;color:inherit}
.post-item:last-child{border:0}
.post-item h3{font-size:1rem;font-weight:600;color:var(--text);margin-bottom:5px}
.post-item p{color:var(--dim);font-size:.87rem;line-height:1.6}
.post-item time{font-family:var(--mono);font-size:.74rem;color:var(--faint);
  display:block;margin-top:7px}
.post-item:hover h3{color:var(--down)}
"""


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


def slugify(t):
    return re.sub(r"[^\w가-힣]+", "-", t).strip("-").lower()


def md(text):
    """마크다운 → HTML. 목차·FAQ 데이터도 함께 반환."""
    out, toc, faq = [], [], []
    in_ul = in_ol = in_tb = False
    box = None

    def close_lists():
        nonlocal in_ul, in_ol, in_tb
        if in_ul:
            out.append("</ul>"); in_ul = False
        if in_ol:
            out.append("</ol>"); in_ol = False
        if in_tb:
            out.append("</tbody></table>"); in_tb = False

    def close_box():
        nonlocal box
        if box:
            close_lists()
            out.append("</div>"); box = None

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        s = lines[i].rstrip()
        i += 1

        if not s.strip():
            close_lists()
            continue

        # ── 박스 시작/끝 ──
        m = re.match(r"^:::(info|warn|check)\s*(.*)$", s)
        if m:
            close_box()
            kind, ttl = m.group(1), m.group(2).strip()
            df = {"info": "💡 알아두세요", "warn": "⚠️ 주의",
                  "check": "✅ 자가진단"}[kind]
            box = kind
            out.append(f'<div class="box box-{kind}">'
                       f'<div class="bt">{inline(ttl or df)}</div>')
            continue
        if s.strip() == ":::":
            close_box()
            continue

        # ── FAQ ──
        m = re.match(r"^\?\s*(.+)$", s)
        if m:
            close_lists(); close_box()
            q = m.group(1).strip()
            ans = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("?"):
                ans.append(lines[i].strip()); i += 1
            a = " ".join(ans)
            faq.append((q, a))
            out.append(f"<details><summary>{inline(q)}</summary>"
                       f"<p>{inline(a)}</p></details>")
            continue

        # ── 표 ──
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not in_tb:
                close_lists()
                out.append('<div class="qa-table-wrap"><table><thead><tr>'
                           + "".join(f"<th>{inline(c)}</th>" for c in cells)
                           + "</tr></thead><tbody>")
                in_tb = True
                continue
            out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_tb:
            out.append("</tbody></table></div>"); in_tb = False

        # ── 제목 ──
        if s.startswith("### "):
            close_lists()
            out.append(f"<h3>{inline(s[4:])}</h3>")
            continue
        if s.startswith("## "):
            close_lists(); close_box()
            t = s[3:]
            sid = slugify(t)
            toc.append((sid, t))
            out.append(f'<h2 id="{sid}">{inline(t)}</h2>')
            continue

        # ── 인용 / 구분선 ──
        if s.startswith("> "):
            close_lists()
            out.append(f"<blockquote>{inline(s[2:])}</blockquote>")
            continue
        if s.strip() in ("---", "***"):
            close_lists()
            out.append("<hr>")
            continue

        # ── 목록 ──
        if re.match(r"^[-*] ", s):
            if not in_ul:
                close_lists(); out.append("<ul>"); in_ul = True
            out.append("<li>" + inline(s[2:]) + "</li>")
            continue
        if re.match(r"^\d+\. ", s):
            if not in_ol:
                close_lists(); out.append("<ol>"); in_ol = True
            txt = re.sub(r"^\d+\. ", "", s)
            out.append("<li>" + inline(txt) + "</li>")
            continue

        close_lists()
        out.append("<p>" + inline(s) + "</p>")

    close_lists(); close_box()
    return "\n".join(out), toc, faq


def parse(p):
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
    meta["points"] = [x.strip() for x in meta.get("points", "").split("|") if x.strip()]
    return meta, body


def shell(title, desc, body, path, schema=""):
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
{schema}
<style>{CSS}{EXTRA}</style></head><body><div class="w">
<header><div class="brand">nightgap<span>co.kr</span></div>
<div class="tag">간밤 해외 지표로 오늘 코스피 개장 갭을 환산합니다</div>
<nav>{nav}</nav></header>
{body}
<footer>데이터 · 한국거래소 KRX Open API, Yahoo Finance<br>
과거 데이터의 통계적 관계만 계산합니다. 투자 조언이 아닙니다.<br>
갱신 {KST:%Y-%m-%d %H:%M} KST</footer></div></body></html>''', encoding="utf-8")


# ═══════════ 발행 ═══════════
items = []
for f in sorted(POSTS.glob("*.md"), reverse=True):
    meta, raw = parse(f)
    body, toc, faq = md(raw)

    tldr = ""
    if meta["summary"] or meta["points"]:
        pts = "".join(f"<li>{inline(x)}</li>" for x in meta["points"])
        tldr = (f'<div class="tldr"><div class="lb">핵심 요약</div>'
                f'<p>{inline(meta["summary"])}</p>'
                + (f"<ul>{pts}</ul>" if pts else "") + "</div>")

    toc_html = ""
    if len(toc) >= 2:
        li = "".join(f'<li><a href="#{i}">{html.escape(t)}</a></li>' for i, t in toc)
        toc_html = f'<div class="toc"><div class="lb">목차</div><ol>{li}</ol></div>'

    schema = ""
    if faq:
        schema = ('<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}}
                           for q, a in faq]}, ensure_ascii=False) + "</script>")

    shell(f"{meta['title']} | nightgap.kr", meta["summary"] or meta["title"],
          f'''<section><div class="eyebrow">글</div>
<h2 style="font-size:1.42rem;margin-bottom:10px;line-height:1.45;border:0;padding:0">
{html.escape(meta['title'])}</h2>
<div class="post-meta">{meta['date']}</div>
{tldr}{toc_html}
<div class="prose faq">{body}</div></section>

<section><div class="eyebrow">함께 보기</div>
<div class="kv"><span><a href="/" style="color:var(--text);text-decoration:none">오늘의 개장 갭 환산</a></span><b>→</b></div>
<div class="kv"><span><a href="/accuracy/" style="color:var(--text);text-decoration:none">예측 적중 기록 80.2%</a></span><b>→</b></div>
<div class="kv"><span><a href="/archive/" style="color:var(--text);text-decoration:none">월별 갭 아카이브</a></span><b>→</b></div>
<div class="kv"><span><a href="/methodology.html" style="color:var(--text);text-decoration:none">방법론과 한계</a></span><b>→</b></div>
</section>''',
          f"posts/{meta['slug']}/index.html", schema)
    items.append(meta)
    print(f"  발행  {meta['date']}  {meta['title']}  (목차 {len(toc)} · FAQ {len(faq)})")

lst = "".join(
    f'<a class="post-item" href="/posts/{i["slug"]}/"><h3>{html.escape(i["title"])}</h3>'
    f'<p>{html.escape(i["summary"])}</p><time>{i["date"]}</time></a>'
    for i in items) or '<p style="color:var(--faint)">아직 글이 없습니다.</p>'

shell("글 | nightgap.kr", "야간선물과 개장 갭에 대한 해설과 기록.",
      f'''<section class="hero"><div class="eyebrow">글</div>
<div class="num mono" style="font-size:2.2rem">{len(items)}편</div>
<div class="band">야간선물과 개장 갭에 대한 해설</div></section>
<section><div class="eyebrow">전체</div>{lst}</section>''',
      "posts/index.html")

sm = SITE / "sitemap.xml"
if sm.exists() and items:
    x = sm.read_text(encoding="utf-8")
    add = "".join(f'<url><loc>{BASE}/posts/{i["slug"]}/</loc><lastmod>{i["date"]}</lastmod>'
                  f'<changefreq>monthly</changefreq><priority>0.7</priority></url>' for i in items)
    add += f'<url><loc>{BASE}/posts/</loc><lastmod>{KST:%Y-%m-%d}</lastmod></url>'
    sm.write_text(x.replace("</urlset>", add + "</urlset>"), encoding="utf-8")

print("=" * 56)
print(f"  글 {len(items)}편 발행  →  /posts/")
print("=" * 56)
