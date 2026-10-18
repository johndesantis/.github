#!/usr/bin/env python3
"""Generate a live, animated SVG dashboard of GitHub-organization metrics and a
dynamic technology-stack badge set, then inject them into the README files.

The dashboard and tech-stack are driven entirely by the GitHub REST API. A
dedicated ``DASHBOARD_API`` secret is preferred over the default
``GITHUB_TOKEN`` so the organisation read quota is not exhausted.

Run directly (as the GitHub Actions workflow does) or import the pure functions
in tests.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode
from xml.sax.saxutils import escape as _xml_escape

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

ORG = "LoBot-LLC"
API_BASE = "https://api.github.com"
USER_AGENT = "LoBot-LLC-live-dashboard"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))

SVG_OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "code-stats.svg")
README_PATHS = [
    os.path.join(REPO_ROOT, "README.md"),
    os.path.join(REPO_ROOT, ".github", "profile", "README.md"),
]

TECH_START = "<!-- TECH-STACK-START -->"
TECH_END = "<!-- TECH-STACK-END -->"
STATS_START = "<!-- CODE-STATS-START -->"
STATS_END = "<!-- CODE-STATS-END -->"

TECH_REGEX = re.compile(re.escape(TECH_START) + r".*?" + re.escape(TECH_END), re.DOTALL)
STATS_REGEX = re.compile(re.escape(STATS_START) + r".*?" + re.escape(STATS_END), re.DOTALL)

# Simple-icons slug (logo) used by shields.io for each language.
LOGO_MAP = {
    "TypeScript": "typescript",
    "JavaScript": "javascript",
    "Python": "python",
    "Python 2": "python",
    "Python 3": "python",
    "Java": "java",
    "C#": "csharp",
    "C++": "cplusplus",
    "C": "c",
    "Go": "go",
    "Rust": "rust",
    "Ruby": "ruby",
    "PHP": "php",
    "Swift": "swift",
    "Kotlin": "kotlin",
    "HTML": "html5",
    "CSS": "css3",
    "SCSS": "sass",
    "JSON": "json",
    "Markdown": "markdown",
    "Shell": "gnubash",
    "Dockerfile": "docker",
    "Makefile": None,
    "YAML": "yaml",
    "Vue": "vuejs",
    "Svelte": "svelte",
    "Dart": "dart",
    "Lua": "lua",
    "R": "r",
    "Scala": "scala",
    "Elixir": "elixir",
    "Haskell": "haskell",
    "Perl": "perl",
}

# Hex colour (without #) for each language badge.
COLORS = {
    "TypeScript": "3178C6",
    "JavaScript": "F7DF1E",
    "Python": "3776AB",
    "Java": "007396",
    "C#": "239",
    "C++": "F34B7D",
    "C": "A12D3F",
    "Go": "00ADD8",
    "Rust": "F74C00",
    "Ruby": "CC342D",
    "PHP": "8892BF",
    "Swift": "F05323",
    "Kotlin": "7D64F7",
    "HTML": "E34D26",
    "CSS": "1572B6",
    "SCSS": "C6538C",
    "JSON": "85C1E9",
    "Markdown": "000000",
    "Shell": "89E051",
    "Dockerfile": "396DEB",
    "Makefile": "858585",
    "YAML": "027490",
    "Vue": "4FC08D",
    "Svelte": "FF3E00",
    "Dart": "0175C2",
    "Lua": "000080",
    "R": "276DC3",
    "Scala": "DC322F",
    "Elixir": "4E2A8E",
    "Haskell": "5E5086",
    "Perl": "39457E",
}

# Animated dashboard palette (GitHub dark dimmed).
DARK = "#0D1117"
CARD_BG = "#161B22"
CARD_BORDER = "#30363D"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
ACCENT = "#58A6FF"
ACCENTS = ["#4578F7", "#58A6FF", "#7D64FF", "#F2CC60", "#F08839", "#F77D50"]

SVG_W, SVG_H = 920, 640
CARD_W, CARD_H = 274, 200
COLS, GAP = 3, 22
START_X, START_Y = 40, 100
FONT_STACK = "ui-monospace,SFMonoRegular,Consolas,Monaco,monospace"
MAX_LANG_BADGES = 16


def _esc(value) -> str:
    """XML-escape a value for safe embedding in SVG text."""
    return _xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


# --------------------------------------------------------------------------- #
# GitHub API helpers
# --------------------------------------------------------------------------- #

def _headers(token: str | None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _api_get_raw(url, token):
    """GET *url*, returning (parsed_json, link_header)."""
    req = urllib.request.Request(url, headers=_headers(token))
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
        return json.loads(body), resp.headers.get("Link")


def _api_get(url, token):
    data, _ = _api_get_raw(url, token)
    return data


def _link_part(link_header: str | None, rel: str):
    """Return the URL registered for a given rel in a Link header, else None."""
    if not link_header:
        return None
    for part in link_header.split(","):
        m = re.match(r'\s*<([^>]+)>\s*;\s*rel="([^"]+)"', part)
        if m and m.group(2) == rel:
            return m.group(1)
    return None


def _link_page(link_header: str | None, rel: str):
    """Return the ``page`` number of the URL stored under *rel*, else None."""
    url = _link_part(link_header, rel)
    if not url:
        return None
    m = re.search(r"[?&]page=(\d+)", url)
    return int(m.group(1)) if m else None


def _get_paginated(url, token):
    """Yield every item from a paginated GitHub collection."""
    while url:
        data, link = _api_get_raw(url, token)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "items" in data:
            items = data["items"]
        else:
            items = [data] if data else []
        for item in items:
            yield item
        url = _link_part(link, "next")


def _paged_count(list_url: str, token) -> int:
    """Approximate the size of a GitHub list endpoint using ``per_page=1``.

    GitHub replies with a ``Link`` header whose ``rel="last"`` page number is
    the total count when ``per_page=1``.  When no ``last`` link is present
    the list fits on a single page, so the response length itself is the total.
    """
    sep = "&" if "?" in list_url else "?"
    full = f"{list_url}{sep}per_page=1"
    try:
        data, link = _api_get_raw(full, token)
    except urllib.error.HTTPError:
        return 0
    if not link:
        return len(data) if isinstance(data, list) else 0
    return _link_page(link, "last") or 0


def _commit_count(repo_full: str, token) -> int:
    """Return the commit count for the repo's default branch."""
    url = f"{API_BASE}/repos/{repo_full}/commits?per_page=1"
    try:
        data, link = _api_get_raw(url, token)
    except urllib.error.HTTPError:
        return 0
    if not link:
        return len(data) if isinstance(data, list) else 0
    return _link_page(link, "last") or 0


def _repo_languages(repo_full: str, token) -> dict:
    try:
        data = _api_get(f"{API_BASE}/repos/{repo_full}/languages", token)
        return data if isinstance(data, dict) else {}
    except urllib.error.HTTPError:
        return {}


def _token():
    return (
        os.environ.get("DASHBOARD_API")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )


# --------------------------------------------------------------------------- #
# Data collection
# --------------------------------------------------------------------------- #

def collect_metrics(token=None):
    """Fetch the six organisation-wide metrics used by the dashboard."""
    token = token or _token()

    org_info = _api_get(f"{API_BASE}/orgs/{ORG}", token)
    total_followers = int(org_info.get("followers", 0))

    repos = [
        r
        for r in _get_paginated(
            f"{API_BASE}/orgs/{ORG}/repos?per_page=100&sort=pushed", token
        )
        if not r.get("fork")
    ]

    total_commits = 0
    total_prs = 0
    total_issues = 0
    most_active_repo = None
    most_active_commits = 0
    lang_bytes: dict = {}

    for repo in repos:
        name = repo["name"]
        commit_count = _commit_count(f"{ORG}/{name}", token)
        total_commits += commit_count
        if commit_count > most_active_commits:
            most_active_commits = commit_count
            most_active_repo = name

        total_prs += _paged_count(
            f"{API_BASE}/repos/{ORG}/{name}/pulls", {"state": "all"}, token
        )
        open_prs = _paged_count(
            f"{API_BASE}/repos/{ORG}/{name}/pulls", {"state": "open"}, token
        )
        # open_issues_count = open issues + open PRs
        total_issues += max(
            0, int(repo.get("open_issues_count", 0)) - open_prs
        )

        for lang, count in _repo_languages(f"{ORG}/{name}", token).items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + count

    most_used_language = (
        max(lang_bytes, key=lang_bytes.get) if lang_bytes else "N/A"
    )

    return {
        "total_followers": total_followers,
        "total_commits": total_commits,
        "most_active_repo": most_active_repo or "N/A",
        "most_used_language": most_used_language,
        "total_prs": total_prs,
        "total_issues": total_issues,
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def collect_languages(token=None):
    """Return ``{language: bytes}`` summed across every non-fork org repo."""
    token = token or _token()
    repos = [
        r
        for r in _get_paginated(
            f"{API_BASE}/orgs/{ORG}/repos?per_page=100&sort=pushed", token
        )
        if not r.get("fork")
    ]
    lang_bytes: dict = {}
    for repo in repos:
        for lang, count in _repo_languages(f"{ORG}/{repo['name']}", token).items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + count
    return lang_bytes


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _fmt_number(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def render_tech_stack(lang_bytes) -> str:
    """Render the technology stack as a block of shields.io badges (markdown)."""
    if not lang_bytes:
        return "_(no languages detected)_"

    ordered = sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:MAX_LANG_BADGES]
    badges = []
    for lang, _count in ordered:
        color = COLORS.get(lang, "858585")
        logo = LOGO_MAP.get(lang)
        if logo:
            badges.append(
                f'<img src="https://img.shields.io/badge/-{_esc_url(lang)}-{color}'
                f'?style=flat&logo={logo}&logoColor=white&label=" alt="{lang}" height="22" />'
            )
        else:
            badges.append(
                f'<img src="https://img.shields.io/badge/-{_esc_url(lang)}-{color}'
                f'?style=flat&label=" alt="{lang}" height="22" />'
            )
    return "<div align=\"left\">\n  " + "\n  ".join(badges) + "\n</div>"


def _esc_url(value) -> str:
    """URL-encode a language name for shields.io, keeping readable form."""
    from urllib.parse import quote

    return quote(str(value))


def _card_markup(i: int, x: int, y: int, title: str, value: str,
                 subtitle: str, accent: str) -> str:
    """Return the SVG group for a single animated stat card."""
    value_size = "26" if _looks_numeric(value) else "20"
    return (
        f'<g>'
        f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="12" '
        f'fill="{CARD_BG}" stroke="{CARD_BORDER}" stroke-width="1">'
        f'<animate attributeName="opacity" from="0" to="1" '
        f'dur="0.6s" begin="{i * 0.15}s" fill="freeze"/></rect>'
        f'<rect x="{x}" y="{y}" width="{CARD_W}" height="8" fill="{accent}">'
        f'<animate attributeName="width" from="0" to="{CARD_W}" '
        f'dur="0.9s" begin="{0.25 + i * 0.15}s" fill="freeze"/></rect>'
        f'<text x="{x + 18}" y="{y + 24}" font-family="{FONT_STACK}" '
        f'font-size="13" fill="{MUTED}">{_esc(title)}</text>'
        f'<text x="{x + 18}" y="{y + 54}" font-family="{FONT_STACK}" '
        f'font-size="{value_size}" font-weight="700" fill="{TEXT}">{_esc(value)}</text>'
        f'<text x="{x + 18}" y="{y + 80}" font-family="{FONT_STACK}" '
        f'font-size="12" fill="{MUTED}">{_esc(subtitle)}</text>'
        f'<circle cx="{x + CARD_W - 14}" cy="{y + 18}" r="5.5" fill="{accent}">'
        f'<animate attributeName="opacity" values="1;0.25;1" dur="1.6s" '
        f'begin="{0.6 + i * 0.2}s" repeatCount="indefinite"/></circle>'
        f'</g>'
    )


def _looks_numeric(value) -> bool:
    s = str(value).strip()
    if not s:
        return False
    s = s.replace(",", "")
    try:
        float(s)
        return True
    except ValueError:
        return False


def render_code_stats_svg(metrics) -> str:
    """Render the full animated SVG dashboard for the supplied metrics dict."""
    cards = [
        ("Followers", _fmt_number(metrics["total_followers"]),
         "organisation members", ACCENTS[0]),
        ("Total Commits", _fmt_number(metrics["total_commits"]),
         "across all repos", ACCENTS[1]),
        ("Most Active Repo", str(metrics["most_active_repo"]),
         "by commit count", ACCENTS[2]),
        ("Most Used Language", str(metrics["most_used_language"]),
         "by bytes across repos", ACCENTS[3]),
        ("Total PRs", _fmt_number(metrics["total_prs"]),
         "open + closed", ACCENTS[4]),
        ("Open Issues", _fmt_number(metrics["total_issues"]),
         "active, not closed", ACCENTS[5]),
    ]

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {SVG_W} {SVG_H}" width="{SVG_W}" height="{SVG_H}" '
        f'role="img" aria-label="LoBot-LLC live code statistics">'
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="{DARK}"/>',
        # Header
        f'<text x="460" y="38" text-anchor="middle" font-family="{FONT_STACK}" '
        f'font-size="22" font-weight="700" fill="{TEXT}">'
        f'LoBot-LLC &#8209; Live Code Statistics</text>',
        f'<text x="460" y="58" text-anchor="middle" font-family="{FONT_STACK}" '
        f'font-size="12" fill="{MUTED}">'
        f'real-time organisation metrics &#8209; updated {_esc(metrics["updated"])}</text>',
        # Live indicator
        f'<circle cx="858" cy="30" r="5.5" fill="{ACCENT}">'
        f'<animate attributeName="opacity" values="1;0.2;1" dur="1.4s" '
        f'repeatCount="indefinite"/></circle>',
        f'<text x="838" y="34" text-anchor="end" font-family="{FONT_STACK}" '
        f'font-size="11" fill="{ACCENT}" font-weight="700">LIVE</text>',
    ]

    for i, (title, value, subtitle, accent) in enumerate(cards):
        col, row = divmod(i, COLS)
        x = START_X + col * (CARD_W + GAP)
        y = START_Y + row * (CARD_H + GAP)
        parts.append(
            _card_markup(i, x, y, title, value, subtitle, accent)
        )

    parts.append(
        f'<text x="460" y="{SVG_H - 14}" text-anchor="middle" '
        f'font-family="{FONT_STACK}" font-size="11" fill="{MUTED}">'
        f'dashboard auto-refreshed by .github/workflows/update-tech-stack.yml '
        f'&#8209; data &amp; icons from GitHub REST API + simple-icons</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def code_stats_html(metrics=None) -> str:
    """Return the markdown fragment injected between the CODE-STATS markers."""
    if metrics is not None:
        render_code_stats_svg(metrics)  # noqa: F841  (side-effect kept for CLI parity)
    return (
        '<p align="center">\n'
        f'  <img src="docs/code-stats.svg" '
        f'alt="Live Code Statistics dashboard for {ORG}" '
        f'width="{SVG_W}" height="{SVG_H}" />\n'
        "</p>\n\n"
        f"<div align=\"center\">\n\n"
        f"Real-time metrics fetched live from <a href=\"https://github.com/{ORG}\">"
        f"github.com/{ORG}</a> via the <code>DASHBOARD_API</code> secret. "
        f"Values are refreshed automatically by the scheduled GitHub Actions "
        f"workflow.\n\n</div>"
    )


# --------------------------------------------------------------------------- #
# README mutation
# --------------------------------------------------------------------------- #

def update_readme(content: str, stats_html: str, tech_html: str) -> str:
    """Inject the rendered HTML into both marker-bounded sections."""
    content = STATS_REGEX.sub(
        f"{STATS_START}\n{stats_html}\n{STATS_END}", content
    )
    content = TECH_REGEX.sub(
        f"{TECH_START}\n{tech_html}\n{TECH_END}", content
    )
    return content


PROFILE_README_TEMPLATE = f"""# LoBot LLC

> Home of AI-native logistics tooling — open source, always live.

## Technology Stack

Our products are built using programming languages and technologies harvested dynamically from every repository in the [{ORG}](https://github.com/{ORG}) organisation:

{TECH_START}
{TECH_END}

## Code Statistics

<!-- An animated, continuously-updating dashboard of organisation-wide metrics. -->

{STATS_START}
{STATS_END}

## Get Involved

Contributions are welcome. Open an issue or drop a pull request on any
[`{ORG}`](https://github.com/{ORG}) repository.

---

*Built with ♥ by the [LoBot-LLC](https://github.com/{ORG}) team.*
"""


def _ensure_readme(path: str) -> str:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(PROFILE_README_TEMPLATE)
    return path


def main() -> None:
    token = _token()
    metrics = collect_metrics(token)
    lang_bytes = collect_languages(token)

    svg = render_code_stats_svg(metrics)
    os.makedirs(os.path.dirname(SVG_OUTPUT_PATH) or ".", exist_ok=True)
    with open(SVG_OUTPUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(svg)

    stats_html = code_stats_html(metrics)
    tech_html = render_tech_stack(lang_bytes)

    for path in README_PATHS:
        _ensure_readme(path)
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        content = update_readme(content, stats_html, tech_html)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    print(
        f"Updated {len(README_PATHS)} README file(s); "
        f"wrote animated dashboard to {SVG_OUTPUT_PATH}."
    )


if __name__ == "__main__":
    main()
