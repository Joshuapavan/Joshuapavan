"""Render the profile README's badges and project cards into .github/assets.

Badges copy shields.io's for-the-badge style (Verdana 10px, uppercase, 1.25px
letter spacing, widths from shields' own Verdana metrics) so they line up with
the shields-rendered tool badges. Keep the top row under ~840px in total, the
width of a profile README. Project cards match the YouTube cards: 250px wide on
#0d1117, with live stars, latest release and download counts.

Runs once a day from .github/workflows/profile.yml. Tokens come only from env
vars and travel in request headers, never in URLs, logs or files. Only public
counts are written to this public repo.
"""

import base64
import json
import math
import os
import re
import sys
import urllib.request
from html import escape
from pathlib import Path

GITHUB_USER = "Joshuapavan"
YOUTUBE_HANDLE = "joshuapavan"
YOUTUBE_CHANNEL_ID = "UCU-zE3krzE5DR_VxIrk-YnQ"
ASSETS = Path(__file__).resolve().parents[2] / ".github" / "assets"
ICONS = ASSETS / "icons"

# Featured projects, in README order. `repo` is where the live numbers come from;
# without one the card shows `meta` and no star count.
# `icon` is a PNG or SVG in .github/assets/icons; without one the card draws `glyph`.
PROJECTS = [
    {
        "file": "card-scripture-pod.svg",
        "repo": "Scripture-Pod",
        "name": "Scripture Pod",
        "icon": "scripture-pod.png",
        "stack": "Tauri · Rust",
        "dot": "#DEA584",
        "blurb": "Bible verses, song lyrics and lower thirds for church services, sent to a projector or OBS.",
    },
    {
        "file": "card-trimly.svg",
        "repo": "Trimly",
        "name": "Trimly",
        "icon": "trimly.png",
        "stack": "Tauri · Rust",
        "dot": "#DEA584",
        "blurb": "Clip just the part of a video link you need, crop it vertical for Shorts or Reels, and save only that.",
    },
    {
        "file": "card-streak-stats.svg",
        "repo": "Github-stats",
        "name": "GitHub Streak Stats",
        "glyph": "flame",
        "color": "#2DA44E",
        "stack": "Angular · TypeScript",
        "dot": "#DD0031",
        "no_release": "Live web app",
        "blurb": "An animated streak card for your profile README, with an activity chart and your top languages.",
    },
    {
        "file": "card-pressd.svg",
        "name": "Pressd",
        "icon": "pressd.svg",
        "stack": "Angular · .NET · Firebase",
        "dot": "#DD0031",
        "meta": "Online store",
        "blurb": "Christ-centred T-shirts, hoodies, mugs and your own designs, made to order and shipped across India.",
    },
]

# Release download counts below this stay off the cards.
MIN_DOWNLOADS = 50

# Verdana 10px advance widths for ASCII 32..126 (anafanafo 2.0.0, as used by shields.io).
VERDANA_NORMAL = [float(w) for w in (
    "3.52 3.94 4.59 8.18 6.36 10.76 7.27 2.69 4.54 4.54 6.36 8.18 3.64 4.54 3.64 4.54 "
    "6.36 6.36 6.36 6.36 6.36 6.36 6.36 6.36 6.36 6.36 4.54 4.54 8.18 8.18 8.18 5.45 10 "
    "6.84 6.86 6.98 7.71 6.32 5.75 7.75 7.51 4.21 4.55 6.93 5.57 8.43 7.48 7.87 6.03 7.87 "
    "6.95 6.84 6.16 7.32 6.84 9.89 6.85 6.15 6.85 4.54 4.54 4.54 8.18 6.36 6.36 6.01 6.23 "
    "5.21 6.23 5.96 3.52 6.23 6.33 2.74 3.44 5.92 2.74 9.73 6.33 6.07 6.23 6.23 4.27 5.21 "
    "3.94 6.33 5.92 8.18 5.92 5.92 5.25 6.35 4.54 6.35 8.18"
).split()]
VERDANA_BOLD = [float(w) for w in (
    "3.42 4.02 5.87 8.67 7.11 12.72 8.62 3.32 5.43 5.43 7.11 8.67 3.61 4.8 3.61 6.89 7.11 "
    "7.11 7.11 7.11 7.11 7.11 7.11 7.11 7.11 7.11 4.02 4.02 8.67 8.67 8.67 6.17 9.64 7.76 "
    "7.62 7.24 8.3 6.83 6.5 8.11 8.37 5.46 5.55 7.71 6.37 9.48 8.47 8.5 7.33 8.5 7.82 7.1 "
    "6.82 8.12 7.64 11.28 7.64 7.37 6.92 5.43 6.89 5.43 8.67 7.11 7.11 6.68 6.99 5.88 "
    "6.99 6.64 4.22 6.99 7.12 3.42 4.03 6.71 3.42 10.58 7.12 6.87 6.99 6.99 4.97 5.93 "
    "4.56 7.12 6.5 9.79 6.69 6.51 5.97 7.11 5.43 7.11 8.67"
).split()]


def verdana(s, size=10, bold=False):
    """Width of `s` in Verdana at `size` px. Wider than most UI fonts, so text sized by it fits."""
    table = VERDANA_BOLD if bold else VERDANA_NORMAL
    return sum(table[ord(c) - 32] if 32 <= ord(c) <= 126 else 10.0 for c in s) * size / 10


# ---------------------------------------------------------------- badges

# 14x14 white glyphs, drawn at (9, 7).
ICON_PLAY = (
    '<rect x="0.9" y="1.9" width="12.2" height="10.2" rx="1.6" fill="none" stroke="#fff" stroke-width="1.6"/>'
    '<path d="M5.4 4.4v5.2L9.8 7z" fill="#fff"/>'
)
ICON_DOWNLOAD = (
    '<path d="M7 1.2v7.4M3.9 5.6 7 8.7l3.1-3.1M1.4 9.4v2.3c0 .6.4 1 1 1h9.2c.6 0 1-.4 1-1V9.4" '
    'fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
)
ICON_LINKEDIN = (
    '<path transform="scale(.5833)" fill="#fff" d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 '
    '0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 '
    '5.455v6.286zM5.337 7.433a2.064 2.064 0 1 1 0-4.128 2.064 2.064 0 0 1 0 4.128zm1.782 13.019H3.555V9h3.564v11.452z'
    'M22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729'
    'C24 .774 23.2 0 22.222 0h.003z"/>'
)
ICON_GLOBE = (
    '<g fill="none" stroke="#fff" stroke-width="1.3"><circle cx="7" cy="7" r="6"/>'
    '<ellipse cx="7" cy="7" rx="2.6" ry="6"/><path d="M1 7h12"/></g>'
)


def badge(label, value, icon, label_bg, value_bg, title=None):
    label, value = label.upper(), value.upper()
    title = escape(title or f"{label}: {value}")
    lt = math.floor(verdana(label)) + 1.25 * len(label)
    vt = math.floor(verdana(value, bold=True)) + 1.25 * len(value)
    lx = 9 + 14 + 9
    lw = lx + lt + 12
    vw = 12 + vt + 12
    w = lw + vw
    label, value = escape(label), escape(value)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="28" role="img" aria-label="{title}">'
        f"<title>{title}</title>"
        f'<g shape-rendering="crispEdges"><rect width="{lw:g}" height="28" fill="{label_bg}"/>'
        f'<rect x="{lw:g}" width="{vw:g}" height="28" fill="{value_bg}"/></g>'
        f'<g transform="translate(9 7)">{icon}</g>'
        '<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        'text-rendering="geometricPrecision" font-size="100">'
        f'<text transform="scale(.1)" x="{(lx + lt / 2) * 10:g}" y="175" textLength="{lt * 10:g}">{label}</text>'
        f'<text transform="scale(.1)" x="{(lw + 12 + vt / 2) * 10:g}" y="175" textLength="{vt * 10:g}" '
        f'font-weight="bold">{value}</text></g></svg>\n'
    )


# ---------------------------------------------------------------- project cards

CARD_W, CARD_H, PAD = 250, 150, 16
FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Noto Sans,Helvetica,Arial,sans-serif"
GLYPHS = {
    # 20x20 white flame, centred in the 32px icon tile.
    "flame": '<path transform="translate(6 6)" fill="#fff" d="M10.6 1c.5 3.1 4.9 5.3 4.9 10.2A5.5 5.5 0 0 1 4.5 '
             '11.6c0-2.4 1.2-4.1 2.5-5.2-.1 1.9.7 3.2 1.9 3.6-.4-3.3.3-6.6 1.7-9zM10 18a2.4 2.4 0 0 0 2.4-2.4c0-1.6'
             '-1.3-2.4-1.9-4-.9 1-2.9 2.3-2.9 4A2.4 2.4 0 0 0 10 18z"/>',
}
STAR_SMALL = (
    'M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 '
    '1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611'
    'L7.327.668A.75.75 0 0 1 8 .25Z'
)


def wrap(text, width, size, max_lines):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if verdana(trial, size) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while verdana(lines[-1] + "…", size) > width:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "…"
    return lines


def card(p, stars, meta):
    name, stack = escape(p["name"]), escape(p["stack"])
    if p.get("icon"):
        data = base64.b64encode((ICONS / p["icon"]).read_bytes()).decode()
        mime = "image/svg+xml" if p["icon"].endswith(".svg") else "image/png"
        tile = (
            '<clipPath id="tile"><rect x="16" y="16" width="32" height="32" rx="8"/></clipPath>'
            f'<image x="16" y="16" width="32" height="32" clip-path="url(#tile)" href="data:{mime};base64,{data}"/>'
        )
    else:
        tile = (
            f'<rect x="16" y="16" width="32" height="32" rx="8" fill="{p["color"]}"/>'
            f'<g transform="translate(16 16)">{GLYPHS[p["glyph"]]}</g>'
        )
    lines = wrap(p["blurb"], CARD_W - 2 * PAD, 12, 3)
    blurb = "".join(f'<tspan x="{PAD}" y="{74 + 17 * i}">{escape(t)}</tspan>' for i, t in enumerate(lines))
    star = ""
    if stars is not None:
        star_x = 31 + verdana(p["stack"], 11) + 14
        star = (
            f'<path transform="translate({star_x:g} 122) scale(.75)" fill="#9198a1" d="{STAR_SMALL}"/>'
            f'<text x="{star_x + 16:g}" y="134" font-size="11" fill="#9198a1">{stars}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{CARD_H}" '
        f'viewBox="0 0 {CARD_W} {CARD_H}" role="img" aria-label="{name}: {escape(p["blurb"])}">'
        f"<title>{name}</title>"
        f'<rect x=".5" y=".5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="5" fill="#0d1117" stroke="#30363d"/>'
        f"{tile}"
        f'<g font-family="{FONT}">'
        f'<text x="58" y="30" font-size="14" font-weight="700" fill="#ffffff">{name}</text>'
        f'<text x="58" y="45" font-size="11" fill="#9198a1">{escape(meta)}</text>'
        f'<text font-size="12" fill="#dedede">{blurb}</text>'
        f'<circle cx="21" cy="130" r="5" fill="{p["dot"]}"/>'
        f'<text x="31" y="134" font-size="11" fill="#9198a1">{stack}</text>'
        f"{star}"
        "</g></svg>\n"
    )


# ---------------------------------------------------------------- data

def get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def github(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-assets"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return get_json(f"https://api.github.com/{path}", headers)


def paged(path):
    page, out = 1, []
    while True:
        batch = github(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def youtube_subscribers():
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return None
    data = get_json(
        f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={YOUTUBE_CHANNEL_ID}",
        {"X-Goog-Api-Key": key},
    )
    return int(data["items"][0]["statistics"]["subscriberCount"])


def releases(repo):
    """(latest version, total downloads) across every published release."""
    rels = [r for r in paged(f"repos/{GITHUB_USER}/{repo}/releases") if not r.get("draft")]
    if not rels:
        return None, 0
    version = re.sub(r"-build\.\d+$", "", rels[0]["tag_name"])
    downloads = sum(a["download_count"] for r in rels for a in r["assets"])
    return version, downloads


def short(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k") if n < 10_000 else f"{n // 1_000}k"
    return str(n)


def write(name, svg):
    (ASSETS / name).write_text(svg)


# ---------------------------------------------------------------- main

def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    failed = False

    write("linkedin.svg", badge("Connect", "LinkedIn", ICON_LINKEDIN, "#004182", "#0A66C2"))
    write("portfolio.svg", badge("Portfolio", "Pavan G", ICON_GLOBE, "#18181B", "#3F3F46"))

    # Each source is independent: a failure keeps that file's last good version.
    try:
        subs = youtube_subscribers()
        value = short(subs) if subs is not None else f"@{YOUTUBE_HANDLE}"
        write("youtube.svg", badge("Subscribe", value, ICON_PLAY, "#CE4630", "#E05D44"))
        print(f"youtube={value}")
    except Exception as e:  # type name only, so nothing request-related reaches the logs
        print(f"YouTube stats failed: {type(e).__name__}")
        failed = True

    for p in PROJECTS:
        try:
            if not p.get("repo"):
                write(p["file"], card(p, None, p["meta"]))
                continue
            stars = github(f"repos/{GITHUB_USER}/{p['repo']}")["stargazers_count"]
            version, downloads = releases(p["repo"])
            meta = [version] if version else [p.get("no_release", "Open source")]
            if downloads >= MIN_DOWNLOADS:
                meta.append(f"{downloads:,} downloads")
            write(p["file"], card(p, short(stars), " · ".join(meta)))
            if p["repo"] == "Scripture-Pod":
                write("scripture-pod-downloads.svg", badge(
                    "Downloads", short(downloads), ICON_DOWNLOAD, "#3730A3", "#4F46E5",
                    title=f"Scripture Pod: {downloads:,} downloads",
                ))
            print(f"{p['repo']}: stars={stars} version={version} downloads={downloads}")
        except Exception as e:
            print(f"{p['name']} failed: {type(e).__name__}")
            failed = True

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
