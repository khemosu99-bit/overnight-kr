"""
글 발행 시스템
- posts/*.md → HTML (목차·요약·박스·표·FAQ·JSON-LD 자동)
"""
import re
import json
import html
import pathlib
import datetime
from theme import BASE, shell as _shell

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
POSTS = ROOT / "posts"
POSTS.mkdir(exist_ok=True)
KST = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

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
.tldr{background:var(--surf2);border:1px solid #2E3D5C;border-radius:9px;
padding:17px 18px;margin:0 0 24px}
.tldr .lb{font-size:.7rem;letter-spacing:.14em;color:var(--faint);
font-weight:700;margin-bottom:9px}
.tldr p{color:var(--text);font-size:.96rem;margin:0 0 10px;line-height:1.75}
.tldr ul{margin:0 0 0 18px;color:var(--dim);font-size:.9rem}
.tldr li{margin:5px 0}
.toc{border:1px dashed var(--line);border-radius:9px;padding:15px 18px;margin:0 0 26px}
.toc .lb{font-size:.7rem;letter-spacing:.14em;color:var(--faint);
font-weight:700;margin-bottom:9px}
.toc ol{margin:0 0 0 18px;font-size:.9rem}
.toc li{margin:5px 0}
.toc a{color:var(--dim);text-decoration:none;border:0}
.toc a:hover{color:var(--text)}
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


def shell(title, desc, body, path, schema=""):
    _shell(title, desc, body, path, SITE, schema=schema, extra_css=EXTRA)


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


def slugify(t):
    return re.sub(r"[^\w가-힣]+", "-", t).strip("-").lower()


def md(text):
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
            out.append("</tbody></table></div>"); in_tb = False

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

        m = re.match(r"^:::(info|warn|check)\s*(.*)$", s)
        if m:
            close_box()
            kind, ttl = m.group(1), m.group(2).strip()
            df = {"info": "💡 알아두세요", "warn": "⚠️ 주의", "check": "✅ 자가진단"}[kind]
            box = kind
            out.append('<div class="box box-' + kind + '">'
                       '<div class="bt">' + inline(ttl or df) + "</div>")
            continue
        if s.strip() == ":::":
            close_box()
            continue

        m = re.match(r"^\?\s*(.+)$", s)
        if m:
            close_lists(); close_box()
            q = m.group(1).strip()
            ans = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("?"):
                ans.append(lines[i].strip()); i += 1
            a = " ".join(ans)
            faq.append((q, a))
            out.append("<details><summary>" + inline(q) + "</summary><p>"
                       + inline(a) + "</p></details>")
            continue

        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not in_tb:
                close_lists()
                out.append('<div class="qa-table-wrap"><table><thead><tr>'
                           + "".join("<th>" + inline(c) + "</th>" for c in cells)
                           + "</tr></thead><tbody>")
                in_tb = True
                continue
            out.append("<tr>" + "".join("<td>" + inline(c) + "</td>" for c in cells) + "</tr>")
            continue
        if in_tb:
            out.append("</tbody></table></div>"); in_tb = False

        if s.startswith("### "):
            close_lists()
            out.append("<h3>" + inline(s[4:]) + "</h3>")
            continue
        if s.startswith("## "):
            close_lists(); close_box()
            t = s[3:]
            sid = slugify(t)
            toc.append((sid, t))
            out.append('<h2 id="' + sid + '">' + inline(t) + "</h2>")
            continue
        if s.startswith("> "):
            close_lists()
            out.append("<blockquote>" + inline(s[2:]) + "</blockquote>")
            continue
        if s.strip() in ("---", "***"):
            close_lists()
            out.append("<hr>")
            continue
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


# ═══════════ 발행 ═══════════
items = []
for f in sorted(POSTS.glob("*.md"), reverse=True):
    meta, raw = parse(f)
    body, toc, faq = md(raw)

    tldr = ""
    if meta["summary"] or meta["points"]:
        pts = "".join("<li>" + inline(x) + "</li>" for x in meta["points"])
        tldr = ('<div class="tldr"><div class="lb">핵심 요약</div><p>'
                + inline(meta["summary"]) + "</p>"
                + ("<ul>" + pts + "</ul>" if pts else "") + "</div>")

    toc_html = ""
    if len(toc) >= 2:
        li = "".join('<li><a href="#' + i + '">' + html.escape(t) + "</a></li>"
                     for i, t in toc)
        toc_html = ('<div class="toc"><div class="lb">목차</div><ol>' + li + "</ol></div>")

    schema = ""
    if faq:
        schema = ('<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}}
                           for q, a in faq]}, ensure_ascii=False) + "</script>")

    shell(meta["title"] + " | nightgap.co.kr",
          meta["summary"] or meta["title"],
          f'''<section><div class="eyebrow">글</div>
<h2 style="font-size:1.42rem;margin-bottom:10px;line-height:1.45;border:0;padding:0">
{html.escape(meta['title'])}</h2>
<div class="post-meta">{meta['date']}</div>
{tldr}{toc_html}
<div class="prose">{body}</div></section>

<section><div class="eyebrow">함께 보기</div>
<div class="kv"><span><a href="/" style="color:var(--text);text-decoration:none">오늘의 개장 갭 환산</a></span><b>→</b></div>
<div class="kv"><span><a href="/accuracy/" style="color:var(--text);text-decoration:none">예측 적중 기록</a></span><b>→</b></div>
<div class="kv"><span><a href="/archive/" style="color:var(--text);text-decoration:none">월별 갭 아카이브</a></span><b>→</b></div>
<div class="kv"><span><a href="/methodology.html" style="color:var(--text);text-decoration:none">방법론과 한계</a></span><b>→</b></div>
</section>''',
          "posts/" + meta["slug"] + "/index.html", schema)
    items.append(meta)
    print(f"  발행  {meta['date']}  {meta['title']}  (목차 {len(toc)} · FAQ {len(faq)})")

lst = "".join(
    '<a class="post-item" href="/posts/' + i["slug"] + '/"><h3>'
    + html.escape(i["title"]) + "</h3><p>" + html.escape(i["summary"])
    + "</p><time>" + i["date"] + "</time></a>" for i in items)
if not lst:
    lst = '<p style="color:var(--faint);font-size:.9rem">아직 발행된 글이 없습니다.</p>'

# ── 근거 데이터 요약 (글의 신뢰 배경) ──
try:
    _m = json.loads((ROOT / "data" / "model2.json").read_text(encoding="utf-8"))
    _n, _r2, _end = _m["n"], _m["gap"]["r2"], _m["end"]
except Exception:
    _n, _r2, _end = 0, 0, "-"

shell("글 | nightgap.co.kr",
      "야간선물과 개장 갭에 대한 해설. 전부 KRX 공식 데이터와 검증된 회귀 결과에 근거합니다.",
      f'''<section class="hero"><div class="eyebrow">글</div>
<div class="lead" style="border:0;margin:0;padding:0">
이 사이트의 글은 전부 <b>KRX 공식 데이터</b>와 검증된 회귀 결과에 근거합니다.<br>
경험담이나 시황 전망은 쓰지 않습니다. 확인 가능한 사실만 씁니다.</div>
<div class="pts" style="margin-top:18px">
<div>근거 데이터<b>{_n}일</b><em>KRX 공식</em></div>
<div>검증 모델<b>R² {_r2:.2f}</b><em>개장 갭</em></div>
<div>구간 적중률<b class="yes">80.2%</b><em>목표 80%</em></div>
<div>데이터 갱신<b>{_end[5:]}</b><em>{_end[:4]}년</em></div>
</div></section>

<section><div class="eyebrow">전체 {len(items)}편</div>{lst}</section>

<section class="limit"><div class="eyebrow">글에 적용하는 원칙</div>
<ul>
<li><b>해보지 않은 것을 해본 척하지 않습니다.</b> 저희가 가진 것은 경험담이 아니라 데이터입니다.</li>
<li><b>시황을 전망하지 않습니다.</b> 과거에 무슨 일이 있었는지만 셉니다.</li>
<li><b>수치에는 표본 수를 함께 적습니다.</b> 표본을 숨긴 확률은 정보가 아닙니다.</li>
<li><b>틀린 것은 정정하고 남깁니다.</b> 지우지 않습니다.</li>
</ul></section>''',
      "posts/index.html")

sm = SITE / "sitemap.xml"
if sm.exists() and items:
    x = sm.read_text(encoding="utf-8")
    add = "".join(
        "<url><loc>" + BASE + "/posts/" + i["slug"] + "/</loc><lastmod>" + i["date"]
        + "</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>"
        for i in items)
    add += ("<url><loc>" + BASE + "/posts/</loc><lastmod>"
            + KST.strftime("%Y-%m-%d") + "</lastmod><priority>0.8</priority></url>")
    sm.write_text(x.replace("</urlset>", add + "</urlset>"), encoding="utf-8")

print("=" * 56)
print(f"  글 {len(items)}편 발행  →  /posts/")
print("=" * 56)
