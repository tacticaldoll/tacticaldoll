#!/usr/bin/env python3
"""Generate the profile dashboard from public GitHub data."""

from __future__ import annotations

import argparse
import html
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "profile.json")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "assets/dashboard.svg")
    return parser.parse_args()


def api_get(path: str, token: str | None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "tacticaldoll-profile-dashboard",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{API}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned {error.code}: {detail}") from error


def fetch_github(username: str, token: str | None) -> dict[str, object]:
    return {
        "user": api_get(f"/users/{username}", token),
        "repos": api_get(
            f"/users/{username}/repos?per_page=100&sort=updated&type=owner", token
        ),
    }


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def truncate(value: str | None, length: int) -> str:
    text = " ".join((value or "No description yet.").split())
    return text if len(text) <= length else f"{text[: length - 1].rstrip()}…"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def select_repos(repos: list[dict], config: dict) -> list[dict]:
    candidates = [
        repo
        for repo in repos
        if not repo.get("fork")
        and not repo.get("archived")
        and repo.get("name") != config["username"]
    ]
    by_name = {repo["name"]: repo for repo in candidates}
    selected = [by_name[name] for name in config["featured"] if name in by_name]
    selected_names = {repo["name"] for repo in selected}
    recent = sorted(
        (repo for repo in candidates if repo["name"] not in selected_names),
        key=lambda repo: repo.get("pushed_at") or "",
        reverse=True,
    )
    return (selected + recent)[:6]


def status_for(repo: dict, now: datetime) -> tuple[str, str]:
    pushed = parse_time(repo["pushed_at"])
    age = (now - pushed).days
    if age <= 30:
        return "LIVE", "#54e38e"
    if age <= 90:
        return "WARM", "#f6c85f"
    return "IDLE", "#7892a6"


def metric_card(x: int, label: str, value: object, note: str) -> str:
    return f"""
    <g transform="translate({x} 205)">
      <rect width="214" height="94" rx="8" class="panel"/>
      <text x="18" y="25" class="label">{esc(label)}</text>
      <text x="18" y="61" class="metric">{esc(value)}</text>
      <text x="108" y="61" class="note">{esc(note)}</text>
    </g>"""


def build_dashboard(config: dict, payload: dict, generated_at: datetime) -> str:
    user = payload["user"]
    repos = payload["repos"]
    now = generated_at.astimezone(timezone.utc)
    active_cutoff = int(config["active_days"])

    owned = [
        repo
        for repo in repos
        if not repo.get("fork") and repo.get("name") != config["username"]
    ]
    active = sum(
        (now - parse_time(repo["pushed_at"])).days <= active_cutoff
        for repo in owned
        if repo.get("pushed_at")
    )
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in owned)
    languages = Counter(repo.get("language") for repo in owned if repo.get("language"))
    top_language = languages.most_common(1)[0][0] if languages else "—"
    selected = select_repos(repos, config)

    cards = "".join(
        [
            metric_card(52, "PUBLIC REPOS", user.get("public_repos", len(owned)), "reachable"),
            metric_card(278, f"ACTIVE / {active_cutoff}D", active, "signals"),
            metric_card(504, "TOTAL STARS", stars, "received"),
            metric_card(730, "PRIMARY STACK", top_language, "by repo"),
        ]
    )

    rows = []
    for index, repo in enumerate(selected):
        y = 365 + index * 50
        status, color = status_for(repo, now)
        language = repo.get("language") or "—"
        rows.append(
            f"""
      <g transform="translate(52 {y})">
        <circle cx="7" cy="-5" r="5" fill="{color}"/>
        <text x="22" y="0" class="repo">{esc(repo["name"])}</text>
        <text x="212" y="0" class="lang">{esc(language)}</text>
        <text x="302" y="0" class="description">{esc(truncate(repo.get("description"), 62))}</text>
        <text x="842" y="0" text-anchor="end" class="status" fill="{color}">{status}</text>
      </g>"""
        )

    doctrine = "  /  ".join(config["doctrine"])
    local_time = generated_at.astimezone(ZoneInfo(config["timezone"]))
    stamp = local_time.strftime("%Y-%m-%d %H:%M %Z")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="735" viewBox="0 0 1000 735" role="img" aria-labelledby="title desc">
  <title id="title">{esc(config["title"])} operations dashboard</title>
  <desc id="desc">An automated overview of public repositories and engineering principles.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#09131d"/>
      <stop offset="1" stop-color="#0d1b26"/>
    </linearGradient>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0H0V32" fill="none" stroke="#183246" stroke-width="1" opacity=".35"/>
    </pattern>
    <style>
      text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .panel {{ fill: #102330; stroke: #234358; stroke-width: 1; }}
      .eyebrow, .label, .status {{ font-size: 12px; font-weight: 700; letter-spacing: 1.5px; }}
      .eyebrow, .accent {{ fill: #55d6be; }}
      .title {{ fill: #e7f6f2; font-size: 38px; font-weight: 750; }}
      .subtitle {{ fill: #8ca6b5; font-size: 13px; letter-spacing: 2px; }}
      .label, .lang {{ fill: #7892a6; }}
      .metric {{ fill: #e7f6f2; font-size: 28px; font-weight: 750; }}
      .note {{ fill: #7892a6; font-size: 12px; }}
      .section {{ fill: #55d6be; font-size: 13px; font-weight: 700; letter-spacing: 1.5px; }}
      .repo {{ fill: #e7f6f2; font-size: 15px; font-weight: 700; }}
      .lang, .description {{ font-size: 12px; }}
      .description {{ fill: #a9bdc8; }}
      .doctrine {{ fill: #c5d7dd; font-size: 11px; letter-spacing: .2px; }}
      .footer {{ fill: #617b8b; font-size: 11px; }}
    </style>
  </defs>
  <rect width="1000" height="735" rx="14" fill="url(#bg)"/>
  <rect width="1000" height="735" rx="14" fill="url(#grid)"/>
  <rect x="1" y="1" width="998" height="733" rx="13" fill="none" stroke="#29495d"/>

  <g transform="translate(52 48)">
    <text class="eyebrow">{esc(config["eyebrow"])} // {esc(user["login"])}</text>
    <text y="54" class="title">{esc(config["title"])}</text>
    <text y="84" class="subtitle">{esc(config["subtitle"])}</text>
    <g transform="translate(824 24)">
      <circle r="23" fill="#102f31" stroke="#55d6be"/>
      <circle r="7" fill="#54e38e"/>
      <text x="-44" y="51" class="status" fill="#54e38e">TELEMETRY ONLINE</text>
    </g>
  </g>

  <line x1="52" y1="170" x2="948" y2="170" stroke="#234358"/>
{cards}

  <text x="52" y="338" class="section">SERVICE REGISTRY</text>
  <text x="948" y="338" text-anchor="end" class="label">STATE FROM LAST PUSH</text>
{''.join(rows)}

  <g transform="translate(52 672)">
    <rect width="896" height="34" rx="6" fill="#0b1822" stroke="#234358"/>
    <text x="16" y="22" class="doctrine"><tspan class="accent">OPERATOR DOCTRINE  </tspan>{esc(doctrine)}</text>
  </g>
  <text x="52" y="720" class="footer">AUTOMATED SNAPSHOT · {esc(stamp)}</text>
  <text x="948" y="720" text-anchor="end" class="footer">SOURCE: GITHUB PUBLIC API</text>
</svg>
"""


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    else:
        payload = fetch_github(config["username"], os.environ.get("GITHUB_TOKEN"))
    generated_at = datetime.now(timezone.utc)
    dashboard = build_dashboard(config, payload, generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dashboard, encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
