#!/usr/bin/env python3
"""Render the profile as a styled, text-based web page (HTML + CSS).

Uses the same data as the README (profile.json + cache.json) and the same
visual language as the README cards, but everything is real text, so it can
be selected, copied and indexed. Writes the page to the path given as the
first argument (default: site/index.html next to the repo root).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def e(s) -> str:
    return escape(str(s or ""), quote=True)


def fmt(n: int) -> str:
    return f"{n:,}"


def compact(n: int) -> str:
    return (f"{n/1000:.1f}K").replace(".0K", "K") if n >= 1000 else str(n)


def first_sentence(s: str) -> str:
    parts = re.split(r"(?<=[.!?])\s", (s or "").strip(), maxsplit=1)
    return parts[0] if parts else ""


def when(s: str) -> str:
    return s.replace("now", "Present")


def sample_repos(c) -> list[dict]:
    repos = [r for r in c["github"].get("repos", []) if re.match(r"^GM\..+\.Samples$", r["name"], re.I)]
    pk = c["nuget"]["packages"]
    out = []
    for r in repos:
        base = r["name"][: -len(".Samples")].lower()
        total = sum(x["downloads"] for x in pk if x["id"].lower() == base or x["id"].lower().startswith(base + "."))
        main = next((x for x in pk if x["id"].lower() == base), None)
        summary = r.get("description") or first_sentence((main or {}).get("description", ""))
        out.append({**r, "family_downloads": total, "summary": summary})
    out.sort(key=lambda r: (-r["family_downloads"], r["name"].lower()))
    return out


ICONS = {
    "linkedin": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1" y="1" width="22" height="22" rx="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="7.3" cy="7.4" r="1.7" fill="currentColor"/><rect x="5.8" y="10.2" width="3" height="8" rx=".6" fill="currentColor"/><path d="M11.2 18.2v-8h2.9v1.2c.6-.9 1.6-1.4 2.8-1.4 2 0 3.2 1.3 3.2 3.7v4.5h-3v-4.1c0-1.1-.5-1.7-1.4-1.7s-1.5.6-1.5 1.7v4.1z" fill="currentColor"/></svg>',
    "nuget": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1" y="1" width="22" height="22" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="7.6" cy="7.6" r="2.6" fill="currentColor"/><circle cx="15" cy="15" r="4.6" fill="currentColor"/></svg>',
    "github": '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.8 1.19 1.83 1.19 3.09 0 4.42-2.7 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5z"/></svg>',
    "web": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M1.5 12h21M12 1.5c3 3.2 4.5 6.7 4.5 10.5S15 19.3 12 22.5C9 19.3 7.5 15.8 7.5 12S9 4.7 12 1.5z" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
}

ARROW = '<svg class="arrow" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 12l8-8M6 4h6v6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'

CSS = """
:root{--bg:#070b12;--card:#0d1420;--border:#223047;--rule:#1b2638;--text:#e6ebf2;--sub:#a3b0c2;--muted:#6f7d91;--accent:#6ea8fe;--green:#3fb950}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 Inter,"Segoe UI",Helvetica,Arial,sans-serif;font-feature-settings:"cv11","ss01"}
a{color:inherit;text-decoration:none}
::selection{background:#6ea8fe55}
.wrap{max-width:960px;margin:0 auto;padding:32px 16px 48px;display:flex;flex-direction:column;gap:8px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:28px 32px}
.header{position:relative;padding:36px 40px 26px}
.header::before{content:"";position:absolute;left:-1px;top:24px;bottom:24px;width:4px;border-radius:2px;background:var(--accent)}
h1{margin:0;font-size:36px;line-height:1.15;font-weight:600;letter-spacing:-.4px}
.title{margin:8px 0 0;color:var(--accent);font-size:18px;font-weight:500}
.focus{margin:4px 0 0;color:var(--sub);font-size:14px}
.summary{margin:22px 0 0;font-size:15px;max-width:780px}
.meta{margin-top:22px;padding-top:16px;border-top:1px solid var(--rule);display:flex;flex-wrap:wrap;gap:8px 28px;color:var(--sub);font-size:13.5px}
.meta span{display:inline-flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block}
.links{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}
.link{display:flex;align-items:center;gap:14px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 18px;transition:border-color .15s,transform .15s}
.link:hover{border-color:var(--accent);transform:translateY(-1px)}
.link svg{width:24px;height:24px;flex:none}
.link b{display:block;font-size:15px;font-weight:600}
.link small{display:block;color:var(--sub);font-size:12.5px;overflow-wrap:anywhere}
.link .arrow{width:16px;height:16px;margin-left:auto;color:var(--sub)}
.section{display:flex;align-items:center;gap:14px;margin:0 0 22px;color:var(--accent);font-size:12px;font-weight:600;letter-spacing:1.6px;text-transform:uppercase}
.section::after{content:"";flex:1;height:1px;background:var(--rule)}
.section em{order:2;font-style:normal;color:var(--muted);letter-spacing:0;text-transform:none;font-weight:400}
.stats{display:grid;grid-template-columns:repeat(5,1fr)}
.stat{padding:2px 20px;border-left:1px solid var(--rule)}
.stat:first-child{padding-left:0;border-left:0}
.stat b{display:block;font-size:32px;font-weight:600;letter-spacing:-.5px;line-height:1.2}
.stat span{display:block;color:var(--sub);font-size:13.5px;font-weight:500}
.stat small{display:block;color:var(--muted);font-size:12px}
.skills{display:grid;grid-template-columns:1fr 1fr;gap:20px 40px}
.skills h3{margin:0 0 4px;color:var(--muted);font-size:12.5px;font-weight:600}
.skills p{margin:0;font-size:14px}
.skills span{white-space:nowrap}
.timeline{list-style:none;margin:0;padding:0}
.timeline li{display:grid;grid-template-columns:150px 1fr;gap:0 30px;position:relative;padding-bottom:22px}
.timeline li:last-child{padding-bottom:0}
.timeline li::before{content:"";position:absolute;left:158px;top:7px;width:7px;height:7px;border-radius:50%;border:1.5px solid #3a4a63;background:var(--card);z-index:1}
.timeline li::after{content:"";position:absolute;left:162.5px;top:16px;bottom:-6px;width:1.5px;background:var(--rule)}
.timeline li:last-child::after{display:none}
.timeline li.now::before{background:var(--accent);border-color:var(--accent)}
.when{color:var(--muted);font-size:12.5px;padding-top:1px}
.now .when{color:var(--accent);font-weight:500}
.role{margin:0;font-size:15px;font-weight:600}
.org{margin:2px 0 0;font-size:13px;color:var(--muted)}
.org b{color:var(--accent);font-weight:500}
.note{margin:4px 0 0;color:var(--sub);font-size:13px}
.grid2,.grid3{display:grid;gap:8px}
.grid2{grid-template-columns:1fr 1fr}
.grid3{grid-template-columns:1fr 1fr 1fr}
.pkg,.repo{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 22px;transition:border-color .15s,transform .15s}
.pkg:hover,.repo:hover{border-color:var(--accent);transform:translateY(-1px)}
.rank{color:var(--muted);font-size:10.5px;font-weight:600;letter-spacing:1.2px}
.pkg:first-child .rank{color:var(--accent)}
.pkg h3{margin:4px 0 8px;font-size:19px;font-weight:600}
.pkg p,.repo p{margin:0;color:var(--sub);font-size:13px;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.foot{margin-top:auto;padding-top:14px;display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--muted)}
.pkg .foot{border-top:1px solid var(--rule);margin-top:auto;padding-top:12px}
.pkg .body{margin-bottom:14px}
.foot b{color:var(--text);font-weight:600}
.repo h3{margin:0 0 6px;font-size:14px;font-weight:600;overflow-wrap:anywhere}
.repo p{-webkit-line-clamp:2;font-size:12px}
.lang{display:inline-flex;align-items:center;gap:6px}
.lang::before{content:"";width:8px;height:8px;border-radius:50%;background:#178600}
.more{display:flex;justify-content:center;align-items:center;gap:8px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;color:var(--accent);font-size:13.5px;font-weight:500}
.more:hover{border-color:var(--accent)}
.more svg{width:14px;height:14px}
.intro{margin:-6px 0 0;color:var(--sub);font-size:14px}
footer{margin-top:12px;text-align:center;color:var(--muted);font-size:11.5px}
@media (max-width:760px){
 .card{padding:22px 20px}.header{padding:28px 24px 20px}h1{font-size:28px}
 .stats{grid-template-columns:1fr 1fr;gap:16px 0}.stat{border-left:0;padding-left:0}
 .skills,.grid2,.grid3{grid-template-columns:1fr}
 .timeline li{grid-template-columns:1fr;padding-left:22px}
 .timeline li::before{left:0;top:6px}.timeline li::after{left:4.5px;top:15px}
 .when{padding-top:0}
}
@media print{body{background:#fff;color:#000}.card,.pkg,.repo,.link,.more{border-color:#ccc;background:#fff}}
"""


def build(p, c) -> str:
    ng, gh = c["nuget"], c["github"]
    tops = sorted(ng["packages"], key=lambda x: -x["downloads"])[: p.get("top_packages", 8)]
    samples = sample_repos(c)
    updated = dt.date.fromisoformat(c["fetched_at"]).strftime("%d %b %Y").lstrip("0")

    links = "".join(
        f'<a class="link" href="{e(l["url"])}">{ICONS.get(l["id"], ICONS["web"])}'
        f'<span><b>{e(l["label"])}</b><small>{e(l.get("handle") or l["url"])}</small></span>{ARROW}</a>'
        for l in p["links"] if l["id"] != "web")

    stats = [
        (p["years_experience"], "Years of experience", "Engineering & leadership"),
        (str(ng["package_count"]), "NuGet packages", "Free to use · .NET"),
        (compact(ng["total_downloads"]), "Package downloads", "All-time on NuGet"),
        (fmt(gh["public_repos"]), "Public repositories", "On GitHub"),
        (fmt(gh["contributions_last_year"]), "Contributions", "GitHub, last 12 months"),
    ]
    stats_html = "".join(f'<div class="stat"><b>{e(v)}</b><span>{e(l)}</span><small>{e(s)}</small></div>' for v, l, s in stats)

    skills = "".join(f'<div><h3>{e(g["group"])}</h3><p>' + " · ".join(f"<span>{e(i)}</span>" for i in g["items"]) + "</p></div>"
                     for g in p["stack"])

    def tl(items, note=True):
        rows = []
        for x in items:
            now = "now" in x["when"].lower()
            role = x.get("role") or x.get("degree")
            org = x.get("org") or x.get("school")
            extra = f' · {e(x["where"])}' if x.get("where") else ""
            body = f'<p class="note">{e(x["note"])}</p>' if note and x.get("note") else ""
            rows.append(f'<li class="{"now" if now else ""}"><div class="when">{e(when(x["when"]))}</div>'
                        f'<div><p class="role">{e(role)}</p><p class="org"><b>{e(org)}</b>{extra}</p>{body}</div></li>')
        return '<ol class="timeline">' + "".join(rows) + "</ol>"

    pkgs = "".join(
        f'<a class="pkg" href="https://www.nuget.org/packages/{e(x["id"])}">'
        f'<div class="body"><span class="rank">#{i} BY DOWNLOADS</span><h3>{e(x["id"])}</h3><p>{e(x.get("description", ""))}</p></div>'
        f'<div class="foot"><span>{e(" · ".join([t for t in x.get("tags", []) if t.lower() not in ("dotnet", ".net")][:3]))}</span>'
        f'<span>v{e(x["version"])} &nbsp; <b>{fmt(x["downloads"])}</b> downloads</span></div></a>'
        for i, x in enumerate(tops, 1))

    repos = "".join(
        f'<a class="repo" href="{e(r["url"])}"><h3>{e(r["name"])}</h3><p>{e(r["summary"])}</p>'
        f'<div class="foot"><span class="lang">{e(r.get("language") or "C#")}</span>'
        f'<span>{"★ " + str(r["stars"]) if r.get("stars") else "Sample app"}</span></div></a>'
        for r in samples)

    desc = f'{p["name"]}: {p["title"]}. {p["summary"]}'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(p["name"])} · {e(p["title"])}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(p["name"])} · {e(p["title"])}">
<meta property="og:description" content="{e(p["summary"])}">
<meta property="og:type" content="profile">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main class="wrap">
<header class="card header">
<h1>{e(p["name"])}</h1>
<p class="title">{e(p["title"])}</p>
<p class="focus">{e(p["focus"])}</p>
<p class="summary">{e(p["summary"])}</p>
<div class="meta"><span>{e(p["location"])}</span><span><i class="dot"></i>{e(p["availability"])}</span></div>
</header>
<nav class="links">{links}</nav>
<section class="card"><h2 class="section">At a glance</h2><div class="stats">{stats_html}</div></section>
<section class="card"><h2 class="section">Technical expertise</h2><div class="skills">{skills}</div></section>
<section class="card"><h2 class="section">Experience</h2>{tl(p["experience"])}</section>
<section class="card"><h2 class="section">Education</h2>{tl(p["education"], note=False)}</section>
<section class="card"><h2 class="section">NuGet packages<em>{ng["package_count"]} packages · {fmt(ng["total_downloads"])} downloads</em></h2>
<p class="intro">My most downloaded packages from the GM.* family: production-ready building blocks for ASP.NET Core services on .NET 10.</p></section>
<div class="grid2">{pkgs}</div>
<a class="more" href="https://www.nuget.org/profiles/{e(p["login"])}">View all {ng["package_count"]} packages on NuGet {ARROW}</a>
<section class="card"><h2 class="section">Sample projects<em>{len(samples)} repositories</em></h2>
<p class="intro">Runnable ASP.NET Core applications showing each GM.* package in a realistic setting, with CI, tests and documentation.</p></section>
<div class="grid3">{repos}</div>
<a class="more" href="https://github.com/{e(p["login"])}?tab=repositories&amp;q=Samples">View all {len(samples)} sample repositories on GitHub {ARROW}</a>
<footer>Figures refreshed daily from NuGet and GitHub · Last updated {e(updated)}</footer>
</main>
</body>
</html>
"""


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site" / "index.html"
    p = json.loads((HERE / "profile.json").read_text(encoding="utf-8"))
    c = json.loads((HERE / "cache.json").read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(p, c), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
