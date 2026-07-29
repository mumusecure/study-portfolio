#!/usr/bin/env python3
"""study-portfolio 정적 사이트 생성기.

data/*.yml + data/notes/*.md 를 읽어 docs/ 에 사이트를 생성한다.
의존성: pyyaml, markdown
사용법: python3 scripts/build.py
"""
import datetime
import html
import re
import shutil
import unicodedata
from pathlib import Path

import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
ASSETS = ROOT / "assets"

MASCOT = r"""      \\|//
     \\|||//
      \|||/
    .-------.
    |  [] []|   < 무무
    |   __  |
    '.  \/ .'
      \   /
      |   |
       \ /
        V"""

LOGO = r""" __  __ _   _ __  __ _   _
|  \/  | | | |  \/  | | | |
| |\/| | | | | |\/| | | | |
| |  | | |_| | |  | | |_| |
|_|  |_|\___/|_|  |_|\___/  ── study log"""

NAV = [
    ("index.html", "~/"),
    ("skills.html", "skill-tree"),
    ("wiki/index.html", "wiki/"),
    ("timeline.html", "timeline"),
    ("logs.html", "weekly.log"),
    ("fails.html", "/var/log/fails"),
    ("me.html", "~/.config/me"),
    ("about.html", "whoami"),
]


def esc(s):
    return html.escape(str(s), quote=False)


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


SITE = load_yaml(DATA / "site.yml")


def page(title, active, body, rel="", extra=""):
    """공통 레이아웃. rel: 루트까지의 상대 경로 접두어 ('' 또는 '../')."""
    nav_html = ""
    for href, label in NAV:
        cls = ' class="active"' if href == active else ""
        nav_html += f'<a href="{rel}{href}"{cls}>{esc(label)}</a>\n'
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — {esc(SITE['nickname'])} study log</title>
<link rel="stylesheet" href="{rel}assets/style.css">
</head>
<body>
{extra}
<div class="wrap">
<div class="titlebar">
  <span class="dot dot-r"></span><span class="dot dot-y"></span><span class="dot dot-g"></span>
  <span class="session">mumu@study: {esc(title)}</span>
</div>
<nav class="mainnav">
{nav_html}</nav>
{body}
<footer>
  <span>© {datetime.date.today().year} {esc(SITE['nickname'])} — 기록은 YAML로, 빌드는 build.py로.</span>
  <span>uptime: 공부하는 중</span>
</footer>
</div>
<!-- 뭔가 숨겨져 있습니다. 메인 화면의 터미널에서 ls -la -->
<script src="{rel}assets/main.js"></script>
</body>
</html>"""


def write(path, content):
    out = DOCS / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"  build {path}")


# ---------------------------------------------------------------- data load
def load_weeks():
    weeks = []
    for f in sorted((DATA / "weeks").glob("*.yml")):
        w = load_yaml(f)
        if w:
            weeks.append(w)
    weeks.sort(key=lambda w: w["week"])
    return weeks


def load_notes():
    """마크다운 노트: frontmatter 파싱 + [[링크]] 수집."""
    notes = {}
    for f in sorted((DATA / "notes").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        meta, body = {}, text
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if m:
            meta = yaml.safe_load(m.group(1)) or {}
            body = m.group(2)
        nid = f.stem
        notes[nid] = {
            "id": nid,
            "title": meta.get("title", nid),
            "tags": meta.get("tags", []),
            "date": str(meta.get("date", "")),
            "body": body,
            "links": re.findall(r"\[\[([\w-]+)\]\]", body),
        }
    return notes


WEEKS = load_weeks()
NOTES = load_notes()
PAPERS = load_yaml(DATA / "papers.yml") or []
PROJECTS = [p for p in (load_yaml(DATA / "projects.yml") or []) if p.get("public", False)]
FAILS = load_yaml(DATA / "fails.yml") or []
SKILLS = load_yaml(DATA / "skills.yml") or {"branches": []}
ME = load_yaml(DATA / "me.yml") or {"sections": []}


# ---------------------------------------------------------------- heatmap
def heatmap_html(n=26):
    """최근 n주 학습 잔디. weeks 데이터의 hours 기반."""
    by_week = {w["week"]: w for w in WEEKS}
    today = datetime.date.today()
    cells = []
    for i in range(n - 1, -1, -1):
        d = today - datetime.timedelta(weeks=i)
        iso = d.isocalendar()
        wid = f"{iso[0]}-W{iso[1]:02d}"
        w = by_week.get(wid)
        hours = (w or {}).get("hours", 0)
        if w is None:
            lv = 0
        elif hours >= 8:
            lv = 3
        elif hours >= 4:
            lv = 2
        else:
            lv = 1
        tip = f"{wid}: {hours}h" if w else f"{wid}: 기록 없음"
        cells.append(f'<div class="hm-cell" data-lv="{lv}" data-tip="{tip}"></div>')
    return (
        '<div class="heatmap">' + "".join(cells) + "</div>"
        '<div class="hm-legend">최근 26주 · 어두움=기록 없음 → 밝은 초록=8시간 이상 '
        "(잔디가 휑하다면, 그것도 데이터입니다)</div>"
    )


# ---------------------------------------------------------------- skill tree
ICONS = {"done": "◆", "learning": "◈", "locked": "◇"}


def disp_width(s):
    """모노스페이스 기준 표시 폭 — 한글/전각은 2칸."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def skill_layout():
    """브랜치별로 노드를 선수 관계 깊이에 따라 행으로 묶는다.

    같은 깊이의 노드는 같은 행에 가로로 나란히 놓여 트리 모양이 된다.
    """
    layouts = []
    for branch in SKILLS["branches"]:
        nodes = branch.get("nodes", [])
        depth = {}
        for nd in nodes:  # 선수 노드는 앞에 정의되어 있다고 가정
            reqs = nd.get("requires", []) or []
            depth[nd["id"]] = 1 + max([depth.get(r, 0) for r in reqs], default=0)
        rows = {}
        for nd in nodes:
            rows.setdefault(depth[nd["id"]], []).append(nd)
        layouts.append({"name": branch["name"], "nodes": nodes, "rows": rows})
    return layouts


def branch_svg(layout, rel=""):
    rows = layout["rows"]
    node_h, row_gap, col_gap, pad = 40, 38, 26, 30
    labels = [f'{ICONS["done"]} {nd["label"]}' for nd in layout["nodes"]]
    node_w = int(max(200, max(disp_width(l) for l in labels) * 7.6 + 28))
    depths = sorted(rows)
    widest = max(len(rows[d]) for d in depths)
    width = widest * node_w + (widest - 1) * col_gap + pad * 2
    height = 56 + len(depths) * node_h + (len(depths) - 1) * row_gap + 10

    pos = {}
    for ri, d in enumerate(depths):
        row = rows[d]
        total = len(row) * node_w + (len(row) - 1) * col_gap
        start = (width - total) / 2
        y = 56 + ri * (node_h + row_gap) + node_h / 2
        for i, nd in enumerate(row):
            pos[nd["id"]] = (start + i * (node_w + col_gap) + node_w / 2, y)

    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'xmlns="http://www.w3.org/2000/svg" role="img" '
             f'aria-label="{esc(layout["name"])} 스킬 트리">']
    parts.append(f'<text x="{width/2:.0f}" y="30" text-anchor="middle" '
                 f'class="sk-branch-label">[ {esc(layout["name"])} ]</text>')

    for nd in layout["nodes"]:
        for r in nd.get("requires", []) or []:
            if r in pos:
                x1, y1 = pos[r]
                x2, y2 = pos[nd["id"]]
                parts.append(f'<line class="sk-edge" x1="{x1:.0f}" y1="{y1 + node_h/2:.0f}" '
                             f'x2="{x2:.0f}" y2="{y2 - node_h/2:.0f}"/>')

    for nd in layout["nodes"]:
        cx, cy = pos[nd["id"]]
        status = nd.get("status", "locked")
        label = f'{ICONS[status]} {nd["label"]}'
        box = (f'<rect x="{cx - node_w/2:.0f}" y="{cy - node_h/2:.0f}" '
               f'width="{node_w}" height="{node_h}" rx="6"/>'
               f'<text x="{cx:.0f}" y="{cy + 4:.0f}" text-anchor="middle">{esc(label)}</text>')
        note = nd.get("note")
        if note and note in NOTES:
            box = f'<a href="{rel}wiki/{note}.html">{box}</a>'
        parts.append(f'<g class="sk-node {status}">{box}</g>')

    parts.append("</svg>")
    return "".join(parts)


def skilltree_svg(rel=""):
    svgs = "".join(branch_svg(la, rel) for la in skill_layout())
    return f'<div class="skilltree-svg">{svgs}</div>'


def skill_topics_html():
    """각 노드에서 다루는 키워드 목록."""
    out = []
    for branch in SKILLS["branches"]:
        for nd in branch.get("nodes", []):
            topics = nd.get("topics") or []
            if not topics:
                continue
            chips = "".join(f'<span class="tagchip">{esc(t)}</span>' for t in topics)
            status = nd.get("status", "locked")
            out.append(f'<div class="sk-topics"><div class="sk-topics-head">'
                       f'{ICONS[status]} {esc(nd["label"])}</div>{chips}</div>')
    return "".join(out)


def skill_progress_html():
    out = []
    for branch in SKILLS["branches"]:
        nodes = branch.get("nodes", [])
        done = sum(1 for n in nodes if n.get("status") == "done")
        total = len(nodes)
        filled = round(done / total * 10) if total else 0
        bar = f'<span class="bar">{"█" * filled}</span><span class="bar-empty">{"░" * (10 - filled)}</span>'
        out.append(f'<div class="sk-progress">{bar} {esc(branch["name"])} — {done}/{total} 해금</div>')
    return "".join(out)


# ---------------------------------------------------------------- weekly logs
def week_entry_html(w, full=True):
    def sec(title, items):
        if not items:
            return ""
        lis = "".join(f"<li>{esc(i)}</li>" for i in items if i)
        return f"<h4>{title}</h4><ul>{lis}</ul>" if lis else ""

    body = sec("한 일", w.get("done"))
    if full:
        body += sec("배운 것", w.get("learned"))
        body += sec("삽질", w.get("fails"))
        body += sec("다음 주", w.get("next"))
    hours = w.get("hours", 0)
    return (f'<div class="week-entry"><h3>{esc(w["week"])}</h3>'
            f'<div class="week-meta">{esc(w.get("range", ""))} · {hours}h</div>{body}</div>')


# ---------------------------------------------------------------- pages
def build_index():
    stats = [
        (len(WEEKS), "주간 로그"),
        (sum(w.get("hours", 0) for w in WEEKS), "기록된 시간(h)"),
        (len(NOTES), "위키 노트"),
        (len(PAPERS), "읽은 논문"),
        (len(FAILS), "삽질 기록"),
    ]
    stats_html = "".join(f'<div class="stat"><div class="num">{n}</div><div class="lab">{lab}</div></div>'
                         for n, lab in stats)
    recent = "".join(week_entry_html(w, full=False) for w in reversed(WEEKS[-3:]))
    projects = "".join(
        f'<li><span class="date">{esc(p.get("period", ""))}</span>'
        f'{esc(p["name"])} <span class="t-tag">{esc(p.get("status", ""))}</span></li>'
        for p in PROJECTS if p.get("status") == "active")
    body = f"""
<pre class="ascii">{esc(LOGO)}</pre>
<p class="subtitle">{esc(SITE['tagline'])} — 공부한 모든 것이 여기 기록됩니다.</p>

<div class="stats">{stats_html}</div>

<div class="panel"><p class="panel-title">학습 잔디</p>{heatmap_html()}</div>

<div class="grid2">
  <div class="panel"><p class="panel-title">스킬 트리 진행률</p>{skill_progress_html()}
    <p><a href="skills.html">전체 트리 보기 →</a></p></div>
  <div class="panel"><p class="panel-title">진행 중인 프로젝트</p>
    <ul class="loglist">{projects or '<li>진행 중인 프로젝트 없음</li>'}</ul>
    <p><a href="timeline.html">타임라인 보기 →</a></p></div>
</div>

<h2>최근 로그</h2>
{recent}
<p><a href="logs.html">전체 주간 로그 →</a> · <a href="fails.html">삽질 로그 →</a></p>

<h2>terminal</h2>
<div class="term">
  <pre class="term-out" id="term-out"></pre>
  <form class="term-line" id="term-form"><span class="ps1">mumu@study:~$</span>
    <input class="term-input" id="term-in" autocomplete="off" spellcheck="false" aria-label="terminal input"></form>
</div>
"""
    write("index.html", page("~/", "index.html", body, extra='<div id="boot"></div>'))


def build_logs():
    entries = "".join(week_entry_html(w) for w in reversed(WEEKS))
    body = f"""<h1 class="prompt">tail -f weekly.log</h1>
<p class="subtitle">매주 15분, 다듬지 않고 기록합니다. 최신순.</p>
{entries or '<p>아직 기록이 없습니다. 이번 주가 첫 줄이 될 차례.</p>'}"""
    write("logs.html", page("weekly.log", "logs.html", body))


def build_skills():
    topics = skill_topics_html()
    topics_panel = (f'<div class="panel"><p class="panel-title">각 노드에서 다루는 것</p>{topics}</div>'
                    if topics else "")
    body = f"""<h1 class="prompt">./skill-tree --render</h1>
<p class="subtitle">◆ 해금 · ◈ 진행 중 · ◇ 잠김 — 위키 노트가 연결된 노드는 클릭하면 이동합니다.</p>
{skilltree_svg()}
<div class="panel"><p class="panel-title">진행률</p>{skill_progress_html()}</div>
{topics_panel}"""
    write("skills.html", page("skill-tree", "skills.html", body))


def build_wiki():
    md = markdown.Markdown(extensions=["tables", "fenced_code"])

    def resolve_links(text):
        def repl(m):
            nid = m.group(1)
            if nid in NOTES:
                return f'<a class="wikilink" href="{nid}.html">{esc(NOTES[nid]["title"])}</a>'
            return f'<span class="wikilink-missing">[[{nid}]]</span>'
        return re.sub(r"\[\[([\w-]+)\]\]", repl, text)

    backlinks = {nid: [] for nid in NOTES}
    for nid, note in NOTES.items():
        for target in note["links"]:
            if target in backlinks and nid not in backlinks[target]:
                backlinks[target].append(nid)

    # index
    items = "".join(
        f'<li><span class="date">{esc(n["date"])}</span><a href="{n["id"]}.html">{esc(n["title"])}</a> '
        + "".join(f'<span class="tagchip">{esc(t)}</span>' for t in n["tags"]) + "</li>"
        for n in sorted(NOTES.values(), key=lambda n: n["date"], reverse=True))
    body = f"""<h1 class="prompt">ls wiki/</h1>
<p class="subtitle">개념 노트 {len(NOTES)}개. [[링크]]로 서로 연결되어 있습니다.</p>
<ul class="loglist">{items}</ul>"""
    write("wiki/index.html", page("wiki/", "wiki/index.html", body, rel="../"))

    # each note
    for nid, note in NOTES.items():
        md.reset()
        content = md.convert(resolve_links(note["body"]))
        bl = backlinks.get(nid, [])
        bl_html = ""
        if bl:
            lis = "".join(f'<li><a href="{b}.html">{esc(NOTES[b]["title"])}</a></li>' for b in bl)
            bl_html = f'<div class="backlinks panel"><p class="panel-title">이 노트로 연결되는 노트</p><ul>{lis}</ul></div>'
        tags = "".join(f'<span class="tagchip">{esc(t)}</span>' for t in note["tags"])
        body = f"""<h1 class="prompt">cat wiki/{esc(nid)}.md</h1>
<h1>{esc(note["title"])}</h1>
<p class="subtitle">{esc(note["date"])} {tags}</p>
<div class="wiki-body">{content}</div>
{bl_html}
<p><a href="index.html">← 노트 목록</a></p>"""
        write(f"wiki/{nid}.html", page(note["title"], "wiki/index.html", body, rel="../"))


def norm_date(s):
    """'2026-07' → '2026-07-01' 정렬용."""
    s = str(s).split("~")[0].strip()
    parts = s.split("-")
    while len(parts) < 3:
        parts.append("01")
    return "-".join(parts)


def build_timeline():
    events = []
    for p in PROJECTS:
        events.append({"date": norm_date(p.get("period", "")), "disp": p.get("period", ""),
                       "tag": "project", "title": p["name"], "desc": p.get("summary", ""),
                       "active": p.get("status") == "active"})
    for pp in PAPERS:
        events.append({"date": norm_date(pp.get("date", "")), "disp": str(pp.get("date", "")),
                       "tag": "paper", "title": pp["title"],
                       "desc": (pp.get("summary") or [""])[0], "active": False})
    for f in FAILS:
        events.append({"date": norm_date(f.get("date", "")), "disp": str(f.get("date", "")),
                       "tag": "fail", "title": f["title"], "desc": f.get("learned", ""), "active": False})
    events.sort(key=lambda e: e["date"], reverse=True)
    lis = "".join(
        f'<li class="{"t-active" if e["active"] else ""}">'
        f'<span class="t-date">{esc(e["disp"])}</span><span class="t-tag">{e["tag"]}</span>'
        f'<div class="t-title">{esc(e["title"])}</div>'
        f'<div class="t-desc">{esc(e["desc"])}</div></li>'
        for e in events)
    body = f"""<h1 class="prompt">git log --graph --all</h1>
<p class="subtitle">프로젝트·논문·삽질을 시간순으로. ● 는 진행 중.</p>
<ul class="timeline">{lis}</ul>"""
    write("timeline.html", page("timeline", "timeline.html", body))


def build_fails():
    entries = "".join(
        f"""<details>
<summary><span class="ts">{esc(f["date"])}</span> <span class="lv">[FAIL]</span> {esc(f["title"])}</summary>
<div class="body">
<p><b>시도:</b> {esc(f.get("tried", ""))}</p>
<p><b>원인:</b> {esc(f.get("why_failed", ""))}</p>
<p><b>배운 것:</b> {esc(f.get("learned", ""))}</p>
</div>
</details>"""
        for f in reversed(FAILS))
    body = f"""<h1 class="prompt">less /var/log/fails</h1>
<p class="subtitle">실패는 숨기지 않습니다. 여기 기록된 삽질이 다음 삽질을 20분쯤 줄여줍니다. (클릭해서 펼치기)</p>
<div class="faillog">{entries or '<details><summary>아직 기록된 실패가 없습니다 — 아직 아무것도 안 해봤다는 뜻일 수도.</summary></details>'}</div>"""
    write("fails.html", page("/var/log/fails", "fails.html", body))


def build_me():
    blocks = ""
    for sec in ME.get("sections", []):
        lis = ""
        for item in sec.get("items", []):
            cls = ' class="comment"' if str(item).startswith("#") else ""
            lis += f"<li{cls}>{esc(item)}</li>"
        blocks += f'<div class="me-conf"><div class="filehead">{esc(sec["title"])}</div><ul>{lis}</ul></div>'
    body = f"""<h1 class="prompt">cat ~/.config/me/*</h1>
<p class="subtitle">공부 밖의 무무. 설정 파일은 수시로 업데이트됩니다.</p>
{blocks}"""
    write("me.html", page("~/.config/me", "me.html", body))


def build_about():
    email = SITE.get("email", "")
    github = SITE.get("github", "")
    contact = f'<li>email: <a href="mailto:{email}">{email}</a></li>' if email else ""
    if github:
        contact += f'<li>github: <a href="{github}">{github}</a></li>'
    body = f"""<h1 class="prompt">whoami</h1>
<div class="grid2">
<div>
<p>{esc(SITE["nickname"])} ({esc(SITE["handle"])}) — {esc(SITE["goal"])}</p>
<p>이 사이트는 제 학습 관제 센터입니다. 잘한 것만 골라 담은 하이라이트가 아니라,
공부한 것·읽은 것·실패한 것 전부를 기록합니다. 커밋 히스토리가 곧 꾸준함의 증거가
되도록, 매주 15분씩 YAML로 기록하면 <code>build.py</code>가 이 사이트를 다시 만듭니다.</p>
<ul>{contact}</ul>
</div>
<div class="panel"><p class="panel-title">mascot: 채소 무 해커</p>
<pre class="ascii mascot">{esc(MASCOT)}</pre>
<p class="subtitle">단단하고, 뿌리가 깊고, 흙(로우레벨)에 산다. 저와 같습니다.</p>
</div>
</div>
<h2>이 사이트의 규칙</h2>
<ul>
<li>전 과정 공개 — 삽질 포함. 단, 화이트햇스쿨 내부 자료·비공개 취약점·타인 개인정보는 올리지 않습니다.</li>
<li>주간 기록은 15분 상한. 다듬은 글보다 꾸준한 기록.</li>
<li>이 사이트 어딘가에 암호 퍼즐이 숨어 있습니다. 힌트는 소스에.</li>
</ul>"""
    write("about.html", page("whoami", "about.html", body))


def build_404():
    body = f"""<h1 class="prompt">cd {{요청한 경로}}</h1>
<pre class="ascii mascot">{esc(MASCOT)}</pre>
<p>404: 무를 뽑았는데 아무것도 없었습니다.</p>
<p>땅을 잘못 파신 것 같아요. <a href="index.html">밭으로 돌아가기 →</a></p>"""
    write("404.html", page("404", "", body))


def build_vault():
    body = f"""<h1 class="prompt">open vault --key=rot13(base64)</h1>
<pre class="ascii">{esc(LOGO)}</pre>
<pre class="ascii mascot">{esc(MASCOT)}</pre>
<p>축하합니다. base64를 벗기고 rot13을 돌려 금고를 열었네요.</p>
<p>이 페이지를 찾은 사람: 아마 당신 포함 세 명쯤. 그중 두 명은 저(무무)와 미래의 저입니다.</p>
<p>당신도 뭔가를 꾸준히 기록해보세요. 미래의 당신이 고마워합니다.</p>
<p><a href="../index.html">← 아무 일 없었다는 듯 돌아가기</a></p>"""
    write("secret/vault.html", page("???", "", body, rel="../"))


def copy_assets():
    dest = DOCS / "assets"
    dest.mkdir(parents=True, exist_ok=True)
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy2(f, dest / f.name)
            print(f"  copy  assets/{f.name}")
    # GitHub Pages: Jekyll 처리 비활성화
    (DOCS / ".nojekyll").write_text("")


def main():
    print("mumu-os build 시작")
    DOCS.mkdir(exist_ok=True)
    copy_assets()
    build_index()
    build_logs()
    build_skills()
    build_wiki()
    build_timeline()
    build_fails()
    build_me()
    build_about()
    build_404()
    build_vault()
    print(f"완료: 주간로그 {len(WEEKS)} · 노트 {len(NOTES)} · 논문 {len(PAPERS)} · "
          f"프로젝트 {len(PROJECTS)} · 삽질 {len(FAILS)}")


if __name__ == "__main__":
    main()
