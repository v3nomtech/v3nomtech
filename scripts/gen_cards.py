#!/usr/bin/env python3
"""Generate self-hosted profile cards (stats, top languages, activity graph, repo pins).

Replaces github-readme-stats / github-readme-activity-graph so the profile never
depends on a third-party server. Runs in GitHub Actions with GITHUB_TOKEN.

Usage: gen_cards.py <login> <out_dir> [pinned_repo ...]
"""
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

BG, BORDER = "#0d1117", "#30363d"
ACCENT, TEXT, MUTED = "#00ff9c", "#c9d1d9", "#8b949e"
FONT = "'Segoe UI',Ubuntu,'Helvetica Neue',Sans-Serif"
MONO = "'JetBrains Mono',Consolas,'DejaVu Sans Mono',monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    name login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        name stargazerCount forkCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions
      totalIssueContributions restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

PIN_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    name description stargazerCount forkCount url
    primaryLanguage { name color }
  }
}
"""


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
            "Content-Type": "application/json",
            "User-Agent": "v3nomtech-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fmt(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
  .t {{ font: 600 17px {FONT}; fill: {ACCENT}; }}
  .l {{ font: 400 14px {FONT}; fill: {TEXT}; }}
  .v {{ font: 700 14px {MONO}; fill: {TEXT}; }}
  .m {{ font: 400 12px {FONT}; fill: {MUTED}; }}
  .fade {{ opacity: 0; animation: in .5s ease-out forwards; }}
  @keyframes in {{ to {{ opacity: 1; }} }}
</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="6" fill="{BG}" stroke="{BORDER}"/>
<text x="25" y="35" class="t">{escape(title)}</text>
{body}
</svg>
"""


# ---------- stats card ----------
def stats_card(user):
    cc = user["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    rows = [
        ("★", "Total stars", stars),
        ("⎇", "Commits (last year)",
         cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
        ("⇄", "Pull requests", user["pullRequests"]["totalCount"]),
        ("!", "Issues", user["issues"]["totalCount"]),
        ("▣", "Public repos", user["repositories"]["totalCount"]),
        ("◉", "Followers", user["followers"]["totalCount"]),
    ]
    body = []
    for i, (icon, label, val) in enumerate(rows):
        y = 70 + i * 24
        body.append(
            f'<g class="fade" style="animation-delay:{150 + i * 120}ms">'
            f'<text x="25" y="{y}" class="v" fill="{ACCENT}" style="fill:{ACCENT}">{icon}</text>'
            f'<text x="50" y="{y}" class="l">{escape(label)}:</text>'
            f'<text x="260" y="{y}" class="v">{fmt(val)}</text></g>'
        )
    # contribution total ring
    total = cc["contributionCalendar"]["totalContributions"]
    body.append(
        f'<g class="fade" style="animation-delay:900ms" transform="translate(385,112)">'
        f'<circle r="48" fill="none" stroke="{BORDER}" stroke-width="6"/>'
        f'<circle r="48" fill="none" stroke="{ACCENT}" stroke-width="6" stroke-linecap="round" '
        f'stroke-dasharray="301.6" stroke-dashoffset="0" transform="rotate(-90)"/>'
        f'<text y="6" text-anchor="middle" class="v" style="font-size:20px;fill:{ACCENT}">{fmt(total)}</text>'
        f'<text y="26" text-anchor="middle" class="m">contribs/yr</text></g>'
    )
    name = user["name"] or user["login"]
    return frame(495, 215, f"{name}'s GitHub Stats", "\n".join(body))


# ---------- top languages ----------
def langs_card(user, top=8):
    sizes, colors = {}, {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or MUTED
    langs = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:top]
    total = sum(s for _, s in langs) or 1

    body, x, bar_w = [], 25, 445
    body.append(f'<mask id="bar"><rect x="25" y="55" width="{bar_w}" height="8" rx="4" fill="#fff"/></mask>')
    body.append('<g mask="url(#bar)">')
    for n, s in langs:
        w = bar_w * s / total
        body.append(f'<rect x="{x:.2f}" y="55" width="{w + 0.5:.2f}" height="8" fill="{colors[n]}"/>')
        x += w
    body.append("</g>")
    for i, (n, s) in enumerate(langs):
        col, row = i % 2, i // 2
        cx, cy = 30 + col * 225, 92 + row * 26
        body.append(
            f'<g class="fade" style="animation-delay:{200 + i * 100}ms">'
            f'<circle cx="{cx}" cy="{cy - 4}" r="5" fill="{colors[n]}"/>'
            f'<text x="{cx + 12}" y="{cy}" class="l">{escape(n)}</text>'
            f'<text x="{cx + 190}" y="{cy}" text-anchor="end" class="m">{100 * s / total:.1f}%</text></g>'
        )
    if not langs:
        body.append('<text x="25" y="95" class="m">No language data yet.</text>')
    h = 92 + ((len(langs) + 1) // 2) * 26 + 5
    return frame(495, max(h, 215), "Most Used Languages", "\n".join(body))


# ---------- activity graph ----------
def activity_card(user, days=31):
    all_days = [
        d for w in user["contributionsCollection"]["contributionCalendar"]["weeks"]
        for d in w["contributionDays"]
    ]
    pts = all_days[-days:]
    W, H = 900, 300
    L, R, T, B = 55, 25, 60, 45
    pw, ph = W - L - R, H - T - B
    peak = max((p["contributionCount"] for p in pts), default=0)
    ymax = max(4, -(-peak // 4) * 4)  # round up to a multiple of 4
    step = pw / max(len(pts) - 1, 1)

    def xy(i, c):
        return L + i * step, T + ph - ph * c / ymax

    coords = [xy(i, p["contributionCount"]) for i, p in enumerate(pts)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = f"{L},{T + ph} {line} {L + pw},{T + ph}"

    body = [
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{ACCENT}" stop-opacity=".45"/>'
        f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>'
    ]
    for k in range(5):
        v = ymax * k / 4
        y = T + ph - ph * k / 4
        body.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="{BORDER}" stroke-dasharray="3 4"/>')
        body.append(f'<text x="{L - 10}" y="{y + 4:.1f}" text-anchor="end" class="m">{v:g}</text>')
    for i, p in enumerate(pts):
        x, _ = xy(i, 0)
        body.append(f'<text x="{x:.1f}" y="{T + ph + 20}" text-anchor="middle" class="m">{int(p["date"][-2:])}</text>')
    body.append(f'<polygon points="{area}" fill="url(#g)" class="fade" style="animation-delay:300ms"/>')
    body.append(
        f'<polyline points="{line}" fill="none" stroke="{ACCENT}" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round" class="fade"/>'
    )
    for (x, y), p in zip(coords, pts):
        body.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{BG}" stroke="#ffffff" stroke-width="1.5">'
            f'<title>{p["date"]}: {p["contributionCount"]}</title></circle>'
        )
    span = f"{pts[0]['date']} → {pts[-1]['date']}" if pts else ""
    body.append(f'<text x="{W - R}" y="35" text-anchor="end" class="m">{span}</text>')
    body.append(f'<text x="{L + pw / 2}" y="{H - 8}" text-anchor="middle" class="m">Days</text>')
    body.append(
        f'<text transform="translate(16,{T + ph / 2}) rotate(-90)" text-anchor="middle" class="m">Contributions</text>'
    )
    name = user["name"] or user["login"]
    return frame(W, H, f"{name}'s Contribution Graph (last {days} days)", "\n".join(body))


# ---------- repo pin ----------
def wrap(text, width=58, max_lines=3):
    words, lines, cur = (text or "No description provided.").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
        else:
            cur = f"{cur} {w}".strip()
    else:
        lines.append(cur)
    if len(lines) == max_lines and " ".join(lines) != " ".join(words):
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


def pin_card(repo):
    desc = wrap(repo["description"])
    body = []
    for i, ln in enumerate(desc):
        body.append(f'<text x="25" y="{65 + i * 20}" class="m" style="font-size:13px">{escape(ln)}</text>')
    y = 65 + len(desc) * 20 + 18
    lang = repo["primaryLanguage"]
    x = 25
    if lang:
        body.append(f'<circle cx="{x + 6}" cy="{y - 5}" r="6" fill="{lang["color"] or MUTED}"/>')
        body.append(f'<text x="{x + 18}" y="{y}" class="l" style="font-size:13px">{escape(lang["name"])}</text>')
        x += 30 + 8 * len(lang["name"])
    body.append(f'<text x="{x}" y="{y}" class="l" style="font-size:13px">★ {fmt(repo["stargazerCount"])}</text>')
    body.append(f'<text x="{x + 60}" y="{y}" class="l" style="font-size:13px">⑂ {fmt(repo["forkCount"])}</text>')
    return frame(420, y + 22, repo["name"], "\n".join(body))


def main():
    login, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    user = gql(QUERY, {"login": login})["user"]
    (out / "stats.svg").write_text(stats_card(user), encoding="utf-8")
    (out / "top-langs.svg").write_text(langs_card(user), encoding="utf-8")
    (out / "activity.svg").write_text(activity_card(user), encoding="utf-8")
    for name in sys.argv[3:]:
        repo = gql(PIN_QUERY, {"owner": login, "name": name})["repository"]
        if repo:
            (out / f"pin-{name}.svg").write_text(pin_card(repo), encoding="utf-8")
        else:
            print(f"warning: repo {name} not found", file=sys.stderr)
    print("cards written:", ", ".join(sorted(p.name for p in out.glob("*.svg"))))


if __name__ == "__main__":
    main()
