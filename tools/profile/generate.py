#!/usr/bin/env python3
"""Write the GitHub profile README as plain text (Markdown).

Reads static profile data from profile.json and live numbers from cache.json
(refreshed daily by fetch.py) and regenerates ../../README.md. No images:
everything is text, so it is searchable, selectable and always current.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def fmt(n: int) -> str:
    return f"{n:,}"


def compact(n: int) -> str:
    return (f"{n/1000:.1f}K").replace(".0K", "K") if n >= 1000 else str(n)


def first_sentence(s: str) -> str:
    parts = re.split(r"(?<=[.!?])\s", (s or "").strip(), maxsplit=1)
    return parts[0] if parts else ""


def cell(s: str) -> str:
    """Make text safe for a Markdown table cell."""
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def when(s: str) -> str:
    return s.replace("now", "present")


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


def build(p, c) -> str:
    ng, gh = c["nuget"], c["github"]
    tops = sorted(ng["packages"], key=lambda x: -x["downloads"])[: p.get("top_packages", 8)]
    samples = sample_repos(c)
    updated = dt.date.fromisoformat(c["fetched_at"]).strftime("%d %b %Y").lstrip("0")
    links = " &nbsp;·&nbsp; ".join(f'<a href="{l["url"]}">{l["label"]}</a>' for l in p["links"])

    L = [
        f'<h1 align="center">{p["name"]}</h1>',
        "",
        f'<p align="center"><b>{p["title"]}</b><br>{p["focus"]}</p>',
        "",
        f'<p align="center">{links}</p>',
        "",
        f'<p align="center">{p["location"]} &nbsp;·&nbsp; {p["availability"]}</p>',
        "",
        p["summary"],
        "",
        "## At a glance",
        "",
        "| Experience | NuGet packages | Package downloads | Public repositories | Contributions |",
        "|:---:|:---:|:---:|:---:|:---:|",
        f"| **{p['years_experience']} years** | **{ng['package_count']}** | **{fmt(ng['total_downloads'])}** "
        f"| **{gh['public_repos']}** | **{fmt(gh['contributions_last_year'])}** |",
        "| engineering & leadership | free to use · .NET | all-time on NuGet | on GitHub | last 12 months |",
        "",
        "## Technical expertise",
        "",
        "| Area | Technologies |",
        "|---|---|",
    ]
    L += [f"| **{cell(g['group'])}** | {cell(', '.join(g['items']))} |" for g in p["stack"]]

    L += ["", "## Experience", ""]
    for e in p["experience"]:
        L.append(f"**{e['role']}** · {e['org']} · {e['where']}  ")
        L.append(f"<sub>{when(e['when'])}</sub>  ")
        L.append(e["note"])
        L.append("")

    L += ["## Education", ""]
    for e in p["education"]:
        L.append(f"**{e['degree']}** · {e['school']}  ")
        L.append(f"<sub>{when(e['when'])}</sub>")
        L.append("")

    L += [
        "## NuGet packages",
        "",
        f"{ng['package_count']} free-to-use packages for ASP.NET Core services on .NET 10, "
        f"with {fmt(ng['total_downloads'])} downloads in total. The most downloaded:",
        "",
        "| # | Package | Description | Version | Downloads |",
        "|---:|---|---|---|---:|",
    ]
    for i, x in enumerate(tops, 1):
        L.append(f"| {i} | [{x['id']}](https://www.nuget.org/packages/{x['id']}) | "
                 f"{cell(first_sentence(x.get('description', '')))} | {x['version']} | {fmt(x['downloads'])} |")
    L += ["", f"[View all {ng['package_count']} packages on NuGet →](https://www.nuget.org/profiles/{p['login']})", ""]

    if samples:
        L += [
            "## Sample projects",
            "",
            "Runnable ASP.NET Core applications showing each GM.* package in a realistic setting, "
            "with CI, tests and documentation.",
            "",
            "| Repository | What it shows |",
            "|---|---|",
        ]
        L += [f"| [{r['name']}]({r['url']}) | {cell(r['summary'])} |" for r in samples]
        L += ["", f"[View all {len(samples)} sample repositories →]"
                  f"(https://github.com/{p['login']}?tab=repositories&q=Samples)", ""]

    L += ["---", "", f"<sub>Figures refreshed daily from NuGet and GitHub · Last updated {updated}</sub>", ""]
    return "\n".join(L)


def main() -> None:
    p = json.loads((HERE / "profile.json").read_text(encoding="utf-8"))
    c = json.loads((HERE / "cache.json").read_text(encoding="utf-8"))
    (ROOT / "README.md").write_text(build(p, c), encoding="utf-8")
    # remove leftovers from the image-based layout
    for old in (ROOT / "assets", HERE / "fonts"):
        if old.exists():
            shutil.rmtree(old)
    print("wrote README.md")


if __name__ == "__main__":
    main()
