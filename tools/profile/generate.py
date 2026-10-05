#!/usr/bin/env python3
"""Render the SVG panels for the GitHub profile README.

Reads static profile data from profile.json and live numbers from cache.json
(refreshed by fetch.py), then writes every panel into ../../assets and
regenerates ../../README.md. Each SVG embeds a subset of Inter so it renders
identically everywhere, including inside GitHub's <img> sandbox.
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ASSETS = ROOT / "assets"
FONT_DIR = HERE / "fonts"
FONT_FILES = {400: "Inter-Regular", 500: "Inter-Medium", 600: "Inter-SemiBold"}
INTER_ZIP = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"


def ensure_fonts() -> dict[int, Path]:
    """Use fonts from tools/profile/fonts; download Inter (OFL) on first run if missing."""
    def find(name):
        for ext in (".otf", ".ttf"):
            f = FONT_DIR / (name + ext)
            if f.exists():
                return f
        return None

    if not all(find(n) for n in FONT_FILES.values()):
        import urllib.request
        import zipfile
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(INTER_ZIP, timeout=60) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        names = z.namelist()
        for n in FONT_FILES.values():
            for ext in (".otf", ".ttf"):
                hit = next((m for m in names if m.split("/")[-1] == n + ext), None)
                if hit:
                    (FONT_DIR / (n + ext)).write_bytes(z.read(hit))
                    break
            else:
                raise RuntimeError(f"{n} not found in {INTER_ZIP}")
    return {w: find(n) for w, n in FONT_FILES.items()}


FONTS = ensure_fonts()

W = 880
PAD = 32

# palette: one accent, neutral slate greys
BG = "#0d1420"
BORDER = "#223047"
RULE = "#1b2638"
TEXT = "#e6ebf2"
SUB = "#a3b0c2"
MUTED = "#6f7d91"
ACCENT = "#6ea8fe"
GREEN = "#3fb950"


# ---------------------------------------------------------------- text metrics

class Metrics:
    def __init__(self, path: Path):
        f = TTFont(path)
        self.upm = f["head"].unitsPerEm
        self.cmap = f.getBestCmap()
        self.hmtx = f["hmtx"].metrics

    def width(self, s: str, size: float, tracking: float = 0) -> float:
        total = 0
        for ch in s:
            g = self.cmap.get(ord(ch))
            total += self.hmtx[g][0] if g in self.hmtx else self.upm * 0.6
        return total * size / self.upm + tracking * max(0, len(s) - 1)


METRICS = {w: Metrics(p) for w, p in FONTS.items()}


def tw(s: str, size: float, weight: int = 400, tracking: float = 0) -> float:
    return METRICS[weight].width(s, size, tracking)


def wrap(s: str, size: float, width: float, weight: int = 400) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        cand = f"{cur} {word}".strip()
        if tw(cand, size, weight) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fmt(n: int) -> str:
    return f"{n:,}"


def compact(n: int) -> str:
    return (f"{n/1000:.1f}K").replace(".0K", "K") if n >= 1000 else str(n)


# ---------------------------------------------------------------- svg builder

class Svg:
    def __init__(self, w: int, h: int, title: str, desc: str):
        self.w, self.h, self.title, self.desc = w, h, title, desc
        self.parts: list[str] = []
        self.chars: dict[int, set[str]] = {400: set(), 500: set(), 600: set()}

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, size=14, fill=TEXT, weight=400, anchor="start", tracking=0.0) -> None:
        self.chars[weight].update(s)
        attrs = f' font-weight="{weight}"' if weight != 400 else ""
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if tracking:
            attrs += f' letter-spacing="{tracking}"'
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}"{attrs}>{escape(s)}</text>')

    def spans(self, x, y, segs, size=14, anchor="start") -> None:
        """segs: list of (text, fill[, weight])."""
        out = []
        for seg in segs:
            s, fill = seg[0], seg[1]
            weight = seg[2] if len(seg) > 2 else 400
            self.chars[weight].update(s)
            wa = f' font-weight="{weight}"' if weight != 400 else ""
            out.append(f'<tspan fill="{fill}"{wa}>{escape(s)}</tspan>')
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" xml:space="preserve"{a}>{"".join(out)}</text>')

    def render(self) -> str:
        faces = ""
        for weight, chars in self.chars.items():
            if chars:
                b64 = subset_b64(FONTS[weight], "".join(sorted(chars | {" "})))
                faces += (f"@font-face{{font-family:'GMSans';font-weight:{weight};"
                          f"src:url(data:font/woff;base64,{b64}) format('woff')}}")
        css = faces + "text{font-family:'GMSans',Inter,'Segoe UI',Helvetica,Arial,sans-serif}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="t d">\n'
            f'<title id="t">{escape(self.title)}</title>\n<desc id="d">{escape(self.desc)}</desc>\n'
            f"<style>{css}</style>\n" + "\n".join(self.parts) + "\n</svg>\n"
        )


_subset_cache: dict[tuple[str, str], str] = {}


def subset_b64(path: Path, chars: str) -> str:
    key = (str(path), chars)
    if key not in _subset_cache:
        font = TTFont(path)
        opts = subset.Options()
        opts.flavor = "woff"
        opts.layout_features = ["kern"]
        opts.hinting = False
        opts.name_IDs = []
        opts.notdef_outline = True
        opts.drop_tables += ["FFTM"]
        sub = subset.Subsetter(opts)
        sub.populate(text=chars)
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff"
        font.save(buf)
        _subset_cache[key] = base64.b64encode(buf.getvalue()).decode()
    return _subset_cache[key]


# ---------------------------------------------------------------- building blocks

def panel(svg: Svg) -> None:
    svg.add(f'<rect x="0.5" y="0.5" width="{svg.w-1}" height="{svg.h-1}" rx="12" fill="{BG}" stroke="{BORDER}"/>')


def section_title(svg: Svg, label: str, y: float = 44, right: str = "") -> None:
    up = label.upper()
    svg.text(PAD, y, up, size=12, fill=ACCENT, weight=600, tracking=1.6)
    start = PAD + tw(up, 12, 600, 1.6) + 14
    end = W - PAD - (tw(right, 12) + 16 if right else 0)
    svg.add(f'<line x1="{start:.1f}" y1="{y-4}" x2="{end:.1f}" y2="{y-4}" stroke="{RULE}"/>')
    if right:
        svg.text(W - PAD, y, right, size=12, fill=MUTED, anchor="end")


def arrow(svg: Svg, x, y, color, s=5) -> None:
    svg.add(f'<path d="M{x-s} {y+s}l{2*s}-{2*s}M{x-s/2} {y-s}h{1.5*s}v{1.5*s}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')


# ---------------------------------------------------------------- panels

def header(p, c) -> Svg:
    x = PAD + 8
    summary = wrap(p["summary"], 15, W - x - PAD - 40)
    H = 172 + len(summary) * 23 + 50
    desc = f"{p['name']} — {p['title']}. {p['focus']}. {p['summary']} {p['location']}. {p['availability']}."
    svg = Svg(W, H, p["name"], desc)
    panel(svg)
    svg.add(f'<rect x="0.5" y="24" width="3.5" height="{H-48}" rx="1.75" fill="{ACCENT}"/>')
    svg.text(x, 70, p["name"], size=36, fill=TEXT, weight=600, tracking=-0.4)
    svg.text(x, 104, p["title"], size=18, fill=ACCENT, weight=500)
    svg.text(x, 130, p["focus"], size=14, fill=SUB)
    y = 174
    for ln in summary:
        svg.text(x, y, ln, size=15, fill=TEXT)
        y += 23
    svg.add(f'<line x1="{x}" y1="{y+2}" x2="{W-PAD}" y2="{y+2}" stroke="{RULE}"/>')
    y += 34
    svg.add(f'<path d="M{x+5} {y+1}c-3.6-4.2-5.4-7.3-5.4-9.4a5.4 5.4 0 0 1 10.8 0c0 2.1-1.8 5.2-5.4 9.4z" '
            f'fill="none" stroke="{SUB}" stroke-width="1.4"/><circle cx="{x+5}" cy="{y-8.4}" r="1.8" fill="{SUB}"/>')
    svg.text(x + 18, y, p["location"], size=13.5, fill=SUB)
    ax = x + 18 + tw(p["location"], 13.5) + 28
    svg.add(f'<circle cx="{ax:.1f}" cy="{y-4.5}" r="4" fill="{GREEN}"/>')
    svg.text(ax + 12, y, p["availability"], size=13.5, fill=SUB)
    return svg


ICONS = {
    "github": '<path fill="{c}" d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.8 1.19 1.83 1.19 3.09 0 4.42-2.7 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5z"/>',
    "nuget": '<rect x="1" y="1" width="22" height="22" rx="5" fill="none" stroke="{c}" stroke-width="2"/>'
             '<circle cx="7.6" cy="7.6" r="2.6" fill="{c}"/><circle cx="15" cy="15" r="4.6" fill="{c}"/>',
}


def link_button(link, side: str) -> Svg:
    w, h = 440, 76
    svg = Svg(w, h, link["label"], f"{link['label']}: {link['url']}")
    x0 = 0.5 if side == "left" else 6.5
    bw = w - 7
    svg.add(f'<rect x="{x0}" y="6.5" width="{bw}" height="{h-13}" rx="10" fill="{BG}" stroke="{BORDER}"/>')
    svg.add(f'<g transform="translate({x0+22} 26)">{ICONS[link["id"]].replace("{c}", TEXT)}</g>')
    svg.text(x0 + 62, 35, link["label"], size=15, fill=TEXT, weight=600)
    svg.text(x0 + 62, 54, link["url"].replace("https://", "").replace("www.", ""), size=12.5, fill=SUB)
    arrow(svg, x0 + bw - 28, 38, SUB)
    return svg


def highlights(p, c) -> Svg:
    ng, gh = c["nuget"], c["github"]
    items = [
        (p["years_experience"], "Years of experience", "Engineering & leadership"),
        (str(ng["package_count"]), "NuGet packages", "Open-source for .NET"),
        (compact(ng["total_downloads"]), "Package downloads", "All-time on NuGet"),
        (fmt(gh["public_repos"]), "Public repositories", "On GitHub"),
        (fmt(gh["contributions_last_year"]), "Contributions", "GitHub, last 12 months"),
    ]
    H = 186
    desc = "At a glance: " + "; ".join(f"{v} {l.lower()}" for v, l, _ in items) + "."
    svg = Svg(W, H, "At a glance", desc)
    panel(svg)
    section_title(svg, "At a glance")
    cols = len(items)
    cw = (W - 2 * PAD) / cols
    top, rh = 70, 102
    for i, (v, l, s) in enumerate(items):
        r, col = divmod(i, cols)
        x = PAD + col * cw
        y = top + r * rh
        if col:
            svg.add(f'<line x1="{x:.1f}" y1="{y+14}" x2="{x:.1f}" y2="{y+rh-14}" stroke="{RULE}"/>')
        ix = x + (24 if col else 0)
        svg.text(ix, y + 46, v, size=32, fill=TEXT, weight=600, tracking=-0.5)
        svg.text(ix, y + 69, l, size=13.5, fill=SUB, weight=500)
        svg.text(ix, y + 87, s, size=12, fill=MUTED)
    return svg


def experience(p, c) -> Svg:
    date_w = 150
    lx = PAD + date_w + 8
    x = lx + 22
    width = W - x - PAD
    rows = [(e, wrap(e["note"], 13, width)) for e in p["experience"]]
    H = 80 + sum(43 + 19 * len(n) + 23 for _, n in rows)
    desc = "Experience: " + "; ".join(f"{e['role']}, {e['org']} ({e['when']})" for e in p["experience"]) + "."
    svg = Svg(W, H, "Experience", desc)
    panel(svg)
    section_title(svg, "Experience")
    y = 90
    svg.add(f'<line x1="{lx}" y1="{y-4}" x2="{lx}" y2="{H-48}" stroke="{RULE}" stroke-width="1.5"/>')
    for e, notes in rows:
        current = "now" in e["when"].lower()
        when = e["when"].replace("now", "Present")
        svg.text(PAD, y, when, size=12.5, fill=ACCENT if current else MUTED, weight=500 if current else 400)
        svg.add(f'<circle cx="{lx}" cy="{y-4.5}" r="4.5" fill="{ACCENT if current else BG}" '
                f'stroke="{ACCENT if current else "#3a4a63"}" stroke-width="1.5"/>')
        svg.text(x, y, e["role"], size=15, fill=TEXT, weight=600)
        svg.spans(x, y + 21, [(e["org"], ACCENT, 500), ("  ·  " + e["where"], MUTED)], size=13)
        ny = y + 43
        for ln in notes:
            svg.text(x, ny, ln, size=13, fill=SUB)
            ny += 19
        y = ny + 23
    return svg


def education(p, c) -> Svg:
    items = p["education"]
    H = 70 + 56 * len(items) + 4
    desc = "Education: " + "; ".join(f"{e['degree']}, {e['school']} ({e['when']})" for e in items) + "."
    svg = Svg(W, H, "Education", desc)
    panel(svg)
    section_title(svg, "Education")
    y = 88
    for e in items:
        current = "now" in e["when"].lower()
        svg.text(PAD, y, e["when"].replace("now", "Present"), size=12.5, fill=ACCENT if current else MUTED, weight=500 if current else 400)
        x = PAD + 180
        svg.text(x, y, e["degree"], size=15, fill=TEXT, weight=600)
        svg.text(x, y + 21, e["school"], size=13, fill=ACCENT, weight=500)
        y += 56
    return svg


def oss_head(p, c) -> Svg:
    ng = c["nuget"]
    desc = (f"Open source: {ng['package_count']} NuGet packages for .NET with {fmt(ng['total_downloads'])} downloads, "
            "each with a runnable sample repository.")
    lines = wrap("The GM.* family: production-ready building blocks for ASP.NET Core services on .NET 10, "
                 "each published with a runnable sample repository.", 14, W - 2 * PAD)
    H = 62 + 21 * len(lines) + 16
    svg = Svg(W, H, "Open source", desc)
    panel(svg)
    section_title(svg, "Open source", right=f"{ng['package_count']} packages  ·  {fmt(ng['total_downloads'])} downloads")
    y = 76
    for ln in lines:
        svg.text(PAD, y, ln, size=14, fill=SUB)
        y += 21
    return svg


def family_stats(pkg_id: str, packages: list[dict]) -> tuple[int, str]:
    total, version = 0, ""
    for x in packages:
        if x["id"] == pkg_id or x["id"].startswith(pkg_id + "."):
            total += x["downloads"]
            if x["id"] == pkg_id:
                version = x["version"]
    return total, version


def card(fp, c, side: str) -> Svg:
    w, h = 440, 192
    total, version = family_stats(fp["id"], c["nuget"]["packages"])
    desc = f"{fp['id']}: {fp['blurb']} {fp['tech']}." + (f" {fmt(total)} downloads." if total else "")
    svg = Svg(w, h, fp["id"], desc)
    x0 = 0.5 if side == "left" else 6.5
    cw = w - 7
    svg.add(f'<rect x="{x0}" y="6.5" width="{cw}" height="{h-13}" rx="10" fill="{BG}" stroke="{BORDER}"/>')
    ix = x0 + 22
    svg.text(ix, 40, fp["tag"].upper(), size=10.5, fill=MUTED, weight=600, tracking=1.2)
    svg.text(ix, 66, fp["id"], size=19, fill=TEXT, weight=600)
    y = 92
    for ln in wrap(fp["blurb"], 13, cw - 44)[:3]:
        svg.text(ix, y, ln, size=13, fill=SUB)
        y += 19
    by = h - 24
    svg.add(f'<line x1="{ix}" y1="{by-20}" x2="{x0+cw-22}" y2="{by-20}" stroke="{RULE}"/>')
    svg.text(ix, by, fp["tech"], size=12, fill=MUTED)
    right = []
    if version:
        right.append((f"v{version}", MUTED))
    if total:
        right += [("    ", MUTED), (fmt(total), TEXT, 600), (" downloads", MUTED)]
    if right:
        svg.spans(x0 + cw - 22, by, right, size=12, anchor="end")
    return svg


def all_packages(p, c) -> Svg:
    ng = c["nuget"]
    svg = Svg(W, 56, "All packages", f"View all {ng['package_count']} packages on NuGet.")
    svg.add(f'<rect x="0.5" y="6.5" width="{W-1}" height="43" rx="10" fill="{BG}" stroke="{BORDER}"/>')
    label = f"View all {ng['package_count']} packages on NuGet"
    lw = tw(label, 13.5, 500)
    x = W / 2 - (lw + 22) / 2
    svg.text(x, 33, label, size=13.5, fill=ACCENT, weight=500)
    arrow(svg, x + lw + 15, 28.5, ACCENT, s=4)
    return svg


def expertise(p, c) -> Svg:
    groups = p["stack"]
    gap = 40
    col_w = (W - 2 * PAD - gap) / 2
    def wrap_items(items):
        lines, cur = [], ""
        for it in items:
            cand = f"{cur}  ·  {it}" if cur else it
            if cur and tw(cand, 14) > col_w:
                lines.append(cur)
                cur = it
            else:
                cur = cand
        return lines + [cur]
    blocks = [(g, wrap_items(g["items"])) for g in groups]
    rows = [blocks[i:i + 2] for i in range(0, len(blocks), 2)]
    row_h = [24 + 22 * max(len(b[1]) for b in r) + 20 for r in rows]
    H = 70 + sum(row_h) + 8
    desc = "Technical expertise. " + " ".join(f"{g['group']}: {', '.join(g['items'])}." for g in groups)
    svg = Svg(W, H, "Technical expertise", desc)
    panel(svg)
    section_title(svg, "Technical expertise")
    y = 84
    for r, rh in zip(rows, row_h):
        for j, (g, lines) in enumerate(r):
            x = PAD + j * (col_w + gap)
            svg.text(x, y, g["group"], size=12.5, fill=MUTED, weight=600)
            ly = y + 24
            for ln in lines:
                svg.text(x, ly, ln, size=14, fill=TEXT)
                ly += 22
        y += rh
    return svg


def footer(p, c) -> Svg:
    d = dt.date.fromisoformat(c["fetched_at"]).strftime("%d %b %Y").lstrip("0")
    msg = f"Figures refreshed daily from NuGet and GitHub  ·  Last updated {d}"
    svg = Svg(W, 40, "Last updated", msg)
    svg.text(W / 2, 25, msg, size=11.5, fill=MUTED, anchor="middle")
    return svg


# ---------------------------------------------------------------- output

def main() -> None:
    p = json.loads((HERE / "profile.json").read_text(encoding="utf-8"))
    c = json.loads((HERE / "cache.json").read_text(encoding="utf-8"))
    for d in (ASSETS, ASSETS / "links", ASSETS / "packages"):
        d.mkdir(parents=True, exist_ok=True)
    out = {
        "header.svg": header(p, c),
        "highlights.svg": highlights(p, c),
        "experience.svg": experience(p, c),
        "education.svg": education(p, c),
        "open-source.svg": oss_head(p, c),
        "all-packages.svg": all_packages(p, c),
        "expertise.svg": expertise(p, c),
        "footer.svg": footer(p, c),
    }
    for i, l in enumerate(p["links"]):
        out[f"links/{l['id']}.svg"] = link_button(l, "left" if i % 2 == 0 else "right")
    for i, fp in enumerate(p["featured_packages"]):
        out[f"packages/{fp['id']}.svg"] = card(fp, c, "left" if i % 2 == 0 else "right")
    keep = set(out)
    for f in list(ASSETS.rglob("*.svg")):  # drop panels from older layouts
        if f.relative_to(ASSETS).as_posix() not in keep:
            f.unlink()
    for name, svg in out.items():
        (ASSETS / name).write_text(svg.render(), encoding="utf-8")
    write_readme(p, c)
    print(f"wrote {len(out)} panels + README.md")


def write_readme(p, c) -> None:
    ng = c["nuget"]

    def img(src, alt, width="100%"):
        return f'<img src="./assets/{src}" width="{width}" align="top" alt="{escape(alt, quote=True)}">'

    L = ['<p align="center">']
    L.append(img("header.svg", f"{p['name']} — {p['title']}. {p['summary']}"))
    L.append("".join(f'<a href="{l["url"]}">{img("links/" + l["id"] + ".svg", l["label"], "50%")}</a>' for l in p["links"]))
    L.append(img("highlights.svg", f"At a glance: {ng['package_count']} NuGet packages, {fmt(ng['total_downloads'])} downloads, "
                                   f"{p['years_experience']} years of experience, {c['github']['public_repos']} public repositories, {c['github']['contributions_last_year']} contributions in the last year"))
    L.append(img("experience.svg", "Experience: " + "; ".join(f"{e['role']}, {e['org']}" for e in p["experience"][:5])))
    L.append(img("education.svg", "Education: " + "; ".join(f"{e['degree']}, {e['school']}" for e in p["education"])))
    L.append(img("open-source.svg", "Open source: the GM.* package family"))
    fps = p["featured_packages"]
    for i in range(0, len(fps), 2):
        L.append("".join(
            f'<a href="https://www.nuget.org/packages/{fp["id"]}">'
            f'{img("packages/" + fp["id"] + ".svg", fp["id"] + " — " + fp["blurb"], "50%")}</a>'
            for fp in fps[i:i + 2]))
    L.append(f'<a href="https://www.nuget.org/profiles/{p["login"]}">{img("all-packages.svg", "View all packages on NuGet")}</a>')
    L.append(img("expertise.svg", "Technical expertise"))
    L.append(img("footer.svg", "Last updated"))
    L.append("</p>")
    (ROOT / "README.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
