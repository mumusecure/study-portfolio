#!/usr/bin/env python3
"""study-portfolio 정적 사이트 생성기.

data/*.yml + data/notes/*.md 를 읽어 docs/ 에 사이트를 생성한다.
의존성: pyyaml, markdown
사용법: python3 scripts/build.py
"""
import datetime
import hashlib
import html
import re
import shutil
import subprocess
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


def asset_ver():
    """CSS/JS 내용으로 만든 짧은 해시.

    자산 주소 뒤에 붙여 브라우저가 옛 스타일시트를 계속 쓰는 걸 막는다.
    """
    h = hashlib.sha1()
    for f in sorted(ASSETS.glob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


ASSET_VER = asset_ver()


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
<link rel="stylesheet" href="{rel}assets/style.css?v={ASSET_VER}">
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
<script src="{rel}assets/main.js?v={ASSET_VER}"></script>
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


# 옵시디언 문법: [[노트]] · [[노트|별칭]] · [[노트#소제목]] · ![[이미지.png]]
WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]#|]+)(?:#([^\[\]|]+))?(?:\|([^\[\]]+))?\]\]")
CALLOUT_RE = re.compile(r"^>\s*\[!(\w+)\][+-]?\s*(.*)$", re.M)
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


def slugify(name):
    """파일명/제목 → 슬러그. 한글은 그대로 두고 공백만 하이픈으로 바꾼다."""
    s = re.sub(r"[\s_]+", "-", str(name).strip().lower())
    s = re.sub(r"[^\w\-]", "", s)
    return re.sub(r"-{2,}", "-", s).strip("-") or "note"


def git_date(path):
    """그 파일을 마지막으로 건드린 커밋 날짜.

    CI(actions/checkout)는 파일 수정시각을 내려받은 시각으로 덮어쓴다.
    그래서 mtime 만 믿으면 모든 노트 날짜가 빌드한 날로 뭉개진다.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        d = out.stdout.strip()
        return d if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else ""
    except Exception:
        return ""


def first_h1(body):
    """본문 맨 위의 `# 제목`만 제목 후보로 본다.

    `##` 이하는 문단 소제목이므로 제목으로 쓰면 안 된다.
    (템플릿의 첫 항목이 통째로 노트 제목이 되어버린다)
    """
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return m.group(1).strip() if m else ""


def convert_callouts(text):
    """옵시디언 콜아웃 `> [!note] 제목` → 제목이 붙은 인용구."""
    def repl(m):
        title = m.group(2).strip()
        return f"> **{m.group(1).upper()}**" + (f" — {title}" if title else "")
    return CALLOUT_RE.sub(repl, text)


def load_notes():
    """옵시디언 볼트(data/notes)를 읽는다.

    - 하위 폴더까지 훑되 `.`/`_` 로 시작하는 폴더는 건너뛴다 (설정·첨부 보관용)
    - frontmatter 에 draft: true 인 노트는 사이트로 내보내지 않는다
    - 옵시디언은 파일명이나 제목으로 링크하므로, 파일명·제목·슬러그를
      같은 노트로 이어주는 별칭 색인을 함께 만든다
    """
    notes, alias, attach = {}, {}, {}
    root = DATA / "notes"
    if not root.exists():
        return notes, alias, attach

    for f in root.rglob("*"):
        if f.is_file() and f.suffix.lower() in IMG_EXT:
            attach.setdefault(f.name, f)

    for f in sorted(root.rglob("*.md")):
        parts = f.relative_to(root).parts
        if any(p.startswith((".", "_")) for p in parts[:-1]):
            continue
        text = f.read_text(encoding="utf-8")
        meta, body = {}, text
        m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.S)
        if m:
            meta = yaml.safe_load(m.group(1))
            body = m.group(2)
        if not isinstance(meta, dict):
            meta = {}
        if meta.get("draft"):
            continue

        slug = slugify(meta.get("slug") or f.stem)
        title = str(meta.get("title") or first_h1(body) or f.stem)
        # 옵시디언에선 본문 맨 위에 `# 제목`을 쓰는 습관이 흔하다.
        # 사이트가 제목을 따로 찍으므로 중복되는 첫 H1 은 본문에서 걷어낸다.
        body = re.sub(r"^\s*#\s+" + re.escape(title) + r"\s*$", "", body, count=1, flags=re.M).lstrip("\n")
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        # 날짜를 안 적었으면 파일을 마지막으로 저장한 날로 채운다.
        # (옵시디언 템플릿 플레이스홀더가 그대로 남은 경우도 같이 처리)
        date = str(meta.get("date") or "").strip()
        if not date or "{{" in date:
            date = git_date(f) or datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()
        notes[slug] = {
            "id": slug,
            "title": title,
            "tags": tags,
            "date": date,
            "body": body,
            "links": [],
        }
        for key in (f.stem, title, slug):
            alias.setdefault(str(key).strip().lower(), slug)
            alias.setdefault(slugify(key), slug)

    for slug, note in notes.items():
        seen = []
        for embed, target, _heading, _label in WIKILINK_RE.findall(note["body"]):
            if embed:
                continue
            t = alias.get(target.strip().lower()) or alias.get(slugify(target))
            if t and t != slug and t not in seen:
                seen.append(t)
        note["links"] = seen

    return notes, alias, attach


WEEKS = load_weeks()
NOTES, NOTE_ALIAS, ATTACHMENTS = load_notes()
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
    node_h, row_gap, col_gap, pad = 40, 38, 20, 24
    labels = [f'{ICONS["done"]} {nd["label"]}' for nd in layout["nodes"]]
    node_w = int(max(200, max(disp_width(l) for l in labels) * 7.6 + 28))
    step = node_w + col_gap
    depths = sorted(rows)

    # 각 노드를 부모들의 평균 x 아래에 놓고, 겹치면 오른쪽으로 밀어낸다.
    # 행을 무조건 가운데 정렬하면 여러 행을 건너뛰는 간선이 중간 노드를 관통한다.
    xs = {}
    for d in depths:
        row = rows[d]
        pref = []
        for nd in row:
            parents = [xs[r] for r in (nd.get("requires") or []) if r in xs]
            pref.append(sum(parents) / len(parents) if parents else 0.0)
        placed, cursor = {}, None
        for i in sorted(range(len(row)), key=lambda i: pref[i]):
            x = pref[i] if cursor is None else max(pref[i], cursor + step)
            placed[i] = cursor = x
        # 밀어낸 만큼 행 전체를 되돌려 부모 중심과 다시 맞춘다
        shift = sum(pref) / len(pref) - sum(placed.values()) / len(placed)
        for i, nd in enumerate(row):
            xs[nd["id"]] = placed[i] + shift

    left, right = min(xs.values()), max(xs.values())
    width = int(right - left + node_w + pad * 2)
    height = 56 + len(depths) * node_h + (len(depths) - 1) * row_gap + 10
    offset = pad + node_w / 2 - left

    pos = {}
    for ri, d in enumerate(depths):
        y = 56 + ri * (node_h + row_gap) + node_h / 2
        for nd in rows[d]:
            pos[nd["id"]] = (xs[nd["id"]] + offset, y)

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
    # toc: 소제목에 id 를 달아 [[노트#소제목]] 앵커가 동작하게 한다
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc"],
        extension_configs={"toc": {"slugify": lambda value, sep: slugify(value)}})
    used_images = {}

    def resolve_links(text):
        """옵시디언 링크/임베드를 사이트용 HTML로 바꾼다."""
        def repl(m):
            embed, target = m.group(1), m.group(2).strip()
            heading, label = m.group(3), m.group(4)

            if embed and Path(target).suffix.lower() in IMG_EXT:
                src = ATTACHMENTS.get(Path(target).name)
                if not src:
                    return f'<span class="wikilink-missing">![[{esc(target)}]]</span>'
                safe = slugify(src.stem) + src.suffix.lower()
                used_images[safe] = src
                return f'<img src="../assets/notes/{safe}" alt="{esc(label or src.stem)}">'

            slug = NOTE_ALIAS.get(target.lower()) or NOTE_ALIAS.get(slugify(target))
            if slug and slug in NOTES:
                anchor = f"#{slugify(heading)}" if heading else ""
                return (f'<a class="wikilink" href="{slug}.html{anchor}">'
                        f'{esc(label or NOTES[slug]["title"])}</a>')
            return f'<span class="wikilink-missing">[[{esc(label or target)}]]</span>'
        return WIKILINK_RE.sub(repl, text)

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
        content = md.convert(convert_callouts(resolve_links(note["body"])))
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

    if used_images:
        dest = DOCS / "assets" / "notes"
        dest.mkdir(parents=True, exist_ok=True)
        for name, src_path in sorted(used_images.items()):
            shutil.copy2(src_path, dest / name)
            print(f"  copy  assets/notes/{name}")


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


def build_write():
    """브라우저에서 글을 써서 바로 커밋하는 콘솔.

    GitHub Pages 는 서버가 없으므로 브라우저가 GitHub API 를 직접 호출한다.
    내비게이션에는 넣지 않는다 — 방문자용 콘텐츠가 아니라 나만 쓰는 도구다.
    """
    gh = str(SITE.get("github", "")).rstrip("/")
    owner = gh.rsplit("/", 1)[-1] if gh else ""
    repo = "study-portfolio"
    site_url = f"https://{owner}.github.io/{repo}/" if owner else "/"
    cfg = (f'<script>window.WRITE_CFG={{owner:"{owner}",repo:"{repo}",'
           f'branch:"main",dir:"data/notes",site:"{site_url}"}};</script>'
           f'<script src="assets/write.js?v={ASSET_VER}"></script>')
    body = f"""<h1 class="prompt">write --new</h1>
<p class="subtitle">여기서 쓴 글은 GitHub 에 커밋되고, 1분쯤 뒤 사이트에 나타납니다.</p>

<div class="panel">
  <p class="panel-title">인증 <span id="w-token-state" class="w-badge warn">토큰 없음</span></p>
  <div id="w-token-panel">
    <p class="w-help">이 사이트는 서버가 없어서, 브라우저가 GitHub 에 직접 글을 올립니다.
    그래서 <b>이 저장소에만 쓸 수 있는 토큰</b>이 필요합니다.</p>
    <ol class="w-help">
      <li><a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">
        Fine-grained token 만들기</a> 를 엽니다</li>
      <li>Repository access → <b>Only select repositories</b> → <code>{esc(repo)}</code> 하나만 선택</li>
      <li>Permissions → Repository permissions → <b>Contents</b> 를 <b>Read and write</b> 로</li>
      <li>만료일은 짧게(90일 등) 두고 생성한 뒤, 나온 토큰을 아래에 붙여넣기</li>
    </ol>
    <div class="w-row">
      <input id="w-token" type="password" class="w-input" placeholder="github_pat_..." autocomplete="off">
      <button id="w-save-token" class="w-btn">저장</button>
    </div>
    <p class="w-help dim">토큰은 이 브라우저에만 저장되고 GitHub 외에는 아무 데도 전송되지 않습니다.
    공용 컴퓨터에서는 쓰지 마세요.</p>
  </div>
  <button id="w-forget" class="w-btn ghost" hidden>토큰 지우기</button>
</div>

<div id="w-editor" hidden>
  <div class="w-row">
    <select id="w-list" class="w-input"><option value="">— 새 글 쓰기 —</option></select>
    <button id="w-template" class="w-btn ghost">템플릿 넣기</button>
  </div>
  <div class="w-row">
    <span class="w-label">파일 이름</span>
    <input id="w-name" class="w-input" placeholder="격자 기반 암호" autocomplete="off">
    <span class="w-label dim">.md</span>
  </div>
  <textarea id="w-body" class="w-body" spellcheck="false"
    placeholder="여기에 본문을 씁니다. 형식은 없어도 됩니다.&#10;&#10;제목은 파일 이름에서, 날짜는 자동으로 채워집니다."></textarea>
  <div class="w-row">
    <button id="w-publish" class="w-btn primary">발행 (⌘+Enter)</button>
    <button id="w-delete" class="w-btn danger">삭제</button>
  </div>
</div>

<p id="w-status" class="w-status">토큰을 등록하면 시작합니다.</p>"""
    write("write.html", page("write", "", body, extra=cfg))


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
    # 글쓰기 콘솔은 나만 쓰는 도구라 검색에 노출시키지 않는다
    (DOCS / "robots.txt").write_text("User-agent: *\nDisallow: /write.html\n", encoding="utf-8")


def main():
    print("mumu-os build 시작")
    DOCS.mkdir(exist_ok=True)
    # 노트를 지우거나 이름을 바꿨을 때 옛 결과물이 사이트에 남지 않도록 먼저 비운다
    shutil.rmtree(DOCS / "wiki", ignore_errors=True)
    shutil.rmtree(DOCS / "assets" / "notes", ignore_errors=True)
    copy_assets()
    build_index()
    build_logs()
    build_skills()
    build_wiki()
    build_timeline()
    build_fails()
    build_me()
    build_about()
    build_write()
    build_404()
    build_vault()
    print(f"완료: 주간로그 {len(WEEKS)} · 노트 {len(NOTES)} · 논문 {len(PAPERS)} · "
          f"프로젝트 {len(PROJECTS)} · 삽질 {len(FAILS)}")


if __name__ == "__main__":
    main()
