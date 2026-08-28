#!/usr/bin/env python3
"""
Dynamic SVG Generator & Profile Stats Updater
Fetches real-time GitHub stats via GitHub CLI (gh) or GitHub GraphQL API,
and updates SVG assets in the assets/ directory.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
GH_STATS_SVG = ASSETS_DIR / "gh-stats.svg"
HEADER_SVG = ASSETS_DIR / "header.svg"
ABOUT_SVG = ASSETS_DIR / "about.svg"
FOOTER_SVG = ASSETS_DIR / "footer.svg"
SKILLS_SVG = ASSETS_DIR / "skills.svg"

# Default fallback language colors if not returned by GitHub API
DEFAULT_LANG_COLORS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "C++": "#f34b7d",
    "C": "#555555",
    "Java": "#b07219",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Shell": "#89e051",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Dart": "#00B4AB",
}

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    bio
    location
    publicRepositories: repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      totalCount
      nodes {
        name
        stargazerCount
        forkCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
      }
    }
  }
}
"""

VIEWER_GRAPHQL_QUERY = """
query {
  viewer {
    login
    name
    bio
    location
    publicRepositories: repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      totalCount
      nodes {
        name
        stargazerCount
        forkCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
      }
    }
  }
}
"""


def fetch_data_via_gh_cli():
    """Fetch GitHub stats using the local gh cli tool."""
    try:
        res = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={VIEWER_GRAPHQL_QUERY}"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        if "data" in data and "viewer" in data["data"] and data["data"]["viewer"]:
            return data["data"]["viewer"]
    except Exception as e:
        print(f"[Warning] Failed to fetch via 'gh api viewer': {e}", file=sys.stderr)

    return None


def fetch_data_via_api(token: str, username: str = "shreyansdev"):
    """Fetch GitHub stats using GitHub GraphQL API over HTTPS."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Profile-SVG-Updater",
    }
    req_body = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": username}}).encode("utf-8")
    req = urllib.request.Request("https://api.github.com/graphql", data=req_body, headers=headers)
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        if "errors" in body:
            raise RuntimeError(f"GraphQL Errors: {body['errors']}")
        return body["data"]["user"]


def get_github_stats():
    """Fetch stats trying token first, then gh CLI, then fallback to public API."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT")
    
    if token:
        try:
            print("[Info] Attempting to fetch stats via GitHub API with token...")
            data = fetch_data_via_api(token, username="shreyansdev")
            if data:
                return data
        except Exception as e:
            print(f"[Warning] Token-based fetch failed: {e}", file=sys.stderr)

    print("[Info] Attempting to fetch stats via GitHub CLI (gh)...")
    data = fetch_data_via_gh_cli()
    if data:
        return data

    raise RuntimeError("Could not fetch GitHub data via either GitHub CLI or GITHUB_TOKEN.")


def generate_bar(percentage: float, total_blocks: int = 10) -> str:
    """Generate terminal block bar for a given percentage (0-100%)."""
    filled_count = round((percentage / 100.0) * total_blocks)
    if percentage > 0 and filled_count == 0:
        filled_count = 1
    filled_count = min(filled_count, total_blocks)
    empty_count = total_blocks - filled_count
    return ("▮" * filled_count) + ("░" * empty_count)


def update_gh_stats_svg(user_data: dict):
    """Generate and update gh-stats.svg with live GitHub analytics."""
    login = user_data.get("login", "shreyansdev")
    repos_count = user_data["publicRepositories"]["totalCount"]
    contribs_coll = user_data.get("contributionsCollection", {})
    commits_count = contribs_coll.get("totalCommitContributions", 0)
    prs_count = contribs_coll.get("totalPullRequestContributions", 0)
    reviews_count = contribs_coll.get("totalPullRequestReviewContributions", 0)
    calendar_contribs = contribs_coll.get("contributionCalendar", {}).get("totalContributions", commits_count)

    # Language aggregation
    lang_bytes = {}
    lang_colors = {}
    for repo in user_data["publicRepositories"]["nodes"]:
        for edge in repo.get("languages", {}).get("edges", []):
            name = edge["node"]["name"]
            color = edge["node"]["color"] or DEFAULT_LANG_COLORS.get(name, "#58a6ff")
            size = edge["size"]
            lang_bytes[name] = lang_bytes.get(name, 0) + size
            lang_colors[name] = color

    total_bytes = sum(lang_bytes.values()) or 1
    sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)
    top_langs = sorted_langs[:3]  # Top 3 languages

    # Format top languages SVG lines
    top_lang_elements = []
    line_classes = ["ln9", "ln10", "ln11"]
    y_positions = [262, 284, 306]

    for idx, (lang_name, size) in enumerate(top_langs):
        pct = (size / total_bytes) * 100
        bar = generate_bar(pct, 10)
        color = lang_colors.get(lang_name, "#58a6ff")
        ln_class = line_classes[idx]
        y_pos = y_positions[idx]
        top_lang_elements.append(
            f'  <g class="{ln_class}" transform="translate(60 {y_pos})">'
            f'<text fill="{color}">{bar}</text>'
            f'<text x="120" fill="#e7e7ea">{lang_name}</text>'
            f'<text x="200" fill="#5a5a64" fill-opacity="0.7">{pct:.1f}%</text>'
            f'</g>'
        )

    langs_svg_markup = "\n".join(top_lang_elements)

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="390" viewBox="0 0 800 390">
  <style>
    text {{ font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 13px; dominant-baseline: middle; }}
    @keyframes ln0 {{ 0%,0% {{ opacity: 0 }} 2%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln2 {{ 0%,6% {{ opacity: 0 }} 8%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln3 {{ 0%,9% {{ opacity: 0 }} 11%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln4 {{ 0%,12% {{ opacity: 0 }} 14%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln5 {{ 0%,15% {{ opacity: 0 }} 17%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln6 {{ 0%,18% {{ opacity: 0 }} 20%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln8 {{ 0%,24% {{ opacity: 0 }} 26%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln9 {{ 0%,27% {{ opacity: 0 }} 29%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln10 {{ 0%,30% {{ opacity: 0 }} 32%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln11 {{ 0%,33% {{ opacity: 0 }} 35%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes ln13 {{ 0%,39% {{ opacity: 0 }} 41%,88% {{ opacity: 1 }} 95%,100% {{ opacity: 0 }} }}
    @keyframes blink {{ 0%,49% {{ opacity: 1 }} 50%,100% {{ opacity: 0 }} }}
    .ln0 {{ animation: ln0 12s ease-in-out infinite }}
    .ln2 {{ animation: ln2 12s ease-in-out infinite }}
    .ln3 {{ animation: ln3 12s ease-in-out infinite }}
    .ln4 {{ animation: ln4 12s ease-in-out infinite }}
    .ln5 {{ animation: ln5 12s ease-in-out infinite }}
    .ln6 {{ animation: ln6 12s ease-in-out infinite }}
    .ln8 {{ animation: ln8 12s ease-in-out infinite }}
    .ln9 {{ animation: ln9 12s ease-in-out infinite }}
    .ln10 {{ animation: ln10 12s ease-in-out infinite }}
    .ln11 {{ animation: ln11 12s ease-in-out infinite }}
    .ln13 {{ animation: ln13 12s ease-in-out infinite }}
  </style>
  <rect width="100%" height="100%" fill="#0a0a0b" rx="14" ry="14"/>
  <g opacity="0.5">
    <circle cx="24" cy="24" r="6" fill="#ff5f57"/>
    <circle cx="44" cy="24" r="6" fill="#febc2e"/>
    <circle cx="64" cy="24" r="6" fill="#28c840"/>
  </g>
  <text x="400" y="28" fill="#5a5a64" font-family="ui-monospace, monospace" font-size="11" text-anchor="middle">~ / github.sh</text>
  <g class="ln0" transform="translate(40 64)"><text fill="#4ade80">$</text><text x="20" fill="#e7e7ea">gh stat --user {login}</text></g>
  <g class="ln2" transform="translate(60 108)"><text fill="#5a5a64">[</text><text x="6" fill="#4ade80">→</text><text x="20" fill="#5a5a64">]</text><text x="40" fill="#5a5a64">repos</text><text x="120" fill="#e7e7ea">{repos_count}</text><text x="200" fill="#5a5a64" fill-opacity="0.7">{repos_count} indexed</text></g>
  <g class="ln3" transform="translate(60 130)"><text fill="#5a5a64">[</text><text x="6" fill="#4ade80">→</text><text x="20" fill="#5a5a64">]</text><text x="40" fill="#5a5a64">commits</text><text x="120" fill="#e7e7ea">{commits_count}</text><text x="200" fill="#5a5a64" fill-opacity="0.7">ytd</text></g>
  <g class="ln4" transform="translate(60 152)"><text fill="#5a5a64">[</text><text x="6" fill="#4ade80">→</text><text x="20" fill="#5a5a64">]</text><text x="40" fill="#5a5a64">prs</text><text x="120" fill="#e7e7ea">{prs_count}</text><text x="200" fill="#5a5a64" fill-opacity="0.7">{prs_count} ytd</text></g>
  <g class="ln5" transform="translate(60 174)"><text fill="#5a5a64">[</text><text x="6" fill="#4ade80">→</text><text x="20" fill="#5a5a64">]</text><text x="40" fill="#5a5a64">reviews</text><text x="120" fill="#e7e7ea">{reviews_count}</text><text x="200" fill="#5a5a64" fill-opacity="0.7">ytd</text></g>
  <g class="ln6" transform="translate(60 196)"><text fill="#5a5a64">[</text><text x="6" fill="#4ade80">→</text><text x="20" fill="#5a5a64">]</text><text x="40" fill="#5a5a64">contribs</text><text x="120" fill="#e7e7ea">{calendar_contribs}</text><text x="200" fill="#5a5a64" fill-opacity="0.7">graphql</text></g>
  <g class="ln8" transform="translate(40 240)"><text fill="#5a5a64"># </text><text x="22" fill="#e7e7ea">top languages</text></g>
{langs_svg_markup}
  <g class="ln13" transform="translate(40 350)"><text fill="#4ade80">$</text><text x="20" fill="#e7e7ea">ready</text><rect x="78" y="-7" width="9" height="14" fill="#e7e7ea" style="animation: blink 1s steps(1) infinite"/></g>
  <text x="782" y="376" fill="#5a5a64" fill-opacity="0.5" font-family="ui-monospace, monospace" font-size="10" text-anchor="end">{calendar_contribs} contributions · @{login}</text>
</svg>
"""
    with open(GH_STATS_SVG, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"[Success] Updated {GH_STATS_SVG.name} with live stats: {repos_count} repos, {commits_count} commits, {calendar_contribs} contribs.")


def update_header_and_footer(user_data: dict):
    """Keep profile name and location in sync if header or footer exist."""
    name = user_data.get("name") or "Shreyans Jain"
    location = user_data.get("location") or "Bengaluru"
    login = user_data.get("login") or "shreyansdev"

    if HEADER_SVG.exists():
        content = HEADER_SVG.read_text(encoding="utf-8")
        # Update name and location
        content = re.sub(
            r'(<g class="ln2" transform="translate\(60 140\)">.*?<text x="160" fill="#e7e7ea">)[^<]*(</text></g>)',
            rf"\g<1>{name}\g<2>",
            content,
        )
        content = re.sub(
            r'(<g class="ln4" transform="translate\(60 184\)">.*?<text x="160" fill="#e7e7ea">)[^<]*(</text></g>)',
            rf"\g<1>{location}\g<2>",
            content,
        )
        HEADER_SVG.write_text(content, encoding="utf-8")
        print(f"[Success] Verified/Updated {HEADER_SVG.name}")

    if FOOTER_SVG.exists():
        content = FOOTER_SVG.read_text(encoding="utf-8")
        # Update name in session.end
        content = re.sub(
            r'(<text x="128" font-size="13" fill="#e7e7ea">thanks for visiting - )[^<]*(</text>)',
            rf"\g<1>{name}\g<2>",
            content,
        )
        FOOTER_SVG.write_text(content, encoding="utf-8")
        print(f"[Success] Verified/Updated {FOOTER_SVG.name}")


def main():
    print("========================================")
    print("  Fetching Latest GitHub Profile Stats  ")
    print("========================================")
    data = get_github_stats()
    print(f"Logged in as: {data.get('login')} ({data.get('name')})")
    print(f"Public Repos: {data['publicRepositories']['totalCount']}")

    update_gh_stats_svg(data)
    update_header_and_footer(data)
    print("========================================")
    print("  Profile SVGs Successfully Updated!   ")
    print("========================================")


if __name__ == "__main__":
    main()
