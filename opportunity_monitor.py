#!/usr/bin/env python3
"""Monitor European opportunities and alert through GitHub Issues/email.

By Sameer Ali <sameer43786@gmail.com>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import smtplib
import ssl
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.yaml"
DEFAULT_STATE = ROOT / "data" / "seen.json"
USER_AGENT = "EuropeOpportunityAlerts/1.0 (+https://github.com/sameer43786)"


@dataclass
class Opportunity:
    title: str
    url: str
    source: str
    summary: str
    published: str = ""
    score: int = 0
    matches: dict[str, list[str]] = field(default_factory=dict)
    age_status: str = "not stated"

    @property
    def identity(self) -> str:
        normalized = self.url.split("#", 1)[0].rstrip("/").lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:20]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("seen", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": datetime.now(UTC).isoformat(), "seen": sorted(seen)}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def bing_rss_url(query: str) -> str:
    return f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"


def clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html.unescape(value), "html.parser").get_text(" ")).strip()


def search_source(source: dict[str, Any], session: requests.Session) -> list[Opportunity]:
    query = " ".join(source["queries"])
    response = session.get(bing_rss_url(query), timeout=30)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    results: list[Opportunity] = []
    allowed = tuple(source.get("allowed_domains", []))
    for entry in feed.entries[: int(source.get("max_results", 15))]:
        url = entry.get("link", "")
        host = urlparse(url).netloc.lower()
        if allowed and not any(host == domain or host.endswith("." + domain) for domain in allowed):
            continue
        results.append(
            Opportunity(
                title=clean_html(entry.get("title", "Untitled opportunity")),
                url=url,
                source=source["name"],
                summary=clean_html(entry.get("summary", entry.get("description", ""))),
                published=entry.get("published", ""),
            )
        )
    return results


def page_text(url: str, session: requests.Session, limit: int = 80_000) -> str:
    try:
        response = session.get(url, timeout=25, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return ""
        soup = BeautifulSoup(response.text[:1_500_000], "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            tag.decompose()
        return re.sub(r"\s+", " ", soup.get_text(" "))[:limit]
    except requests.RequestException as exc:
        print(f"warning: could not retrieve {url}: {exc}", file=sys.stderr)
        return ""


def term_matches(text: str, terms: list[str]) -> list[str]:
    lowered = text.casefold()
    return sorted({term for term in terms if term.casefold() in lowered}, key=str.casefold)


def evaluate(item: Opportunity, config: dict[str, Any], body: str) -> Opportunity | None:
    criteria = config["criteria"]
    text = " ".join((item.title, item.summary, body))
    exclusion_hits = term_matches(text, criteria.get("exclude_terms", []))
    if exclusion_hits:
        return None

    explicit_no_limit = term_matches(text, criteria["age"]["no_limit_terms"])
    age_caps = []
    for pattern in criteria["age"]["exclude_patterns"]:
        age_caps.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    if age_caps and not explicit_no_limit and criteria["age"].get("reject_explicit_limits", True):
        return None
    item.age_status = "explicitly no limit" if explicit_no_limit else ("explicit limit detected" if age_caps else "not stated")

    score = 0
    matches: dict[str, list[str]] = {}
    for group_name, group in criteria["groups"].items():
        hits = term_matches(text, group["terms"])
        if hits:
            matches[group_name] = hits
            score += int(group["weight"]) + min(len(hits) - 1, 3)

    required_any = criteria.get("require_any_groups", [])
    if required_any and not any(group in matches for group in required_any):
        return None
    topical_any = criteria.get("require_topic_groups", [])
    if topical_any and not any(group in matches for group in topical_any):
        return None
    if score < int(criteria.get("minimum_score", 8)):
        return None
    item.score, item.matches = score, matches
    return item


def collect(config: dict[str, Any]) -> list[Opportunity]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})
    candidates: dict[str, Opportunity] = {}
    for source in config["sources"]:
        try:
            for item in search_source(source, session):
                candidates.setdefault(item.identity, item)
        except Exception as exc:  # keep other sources running
            print(f"warning: source {source['name']} failed: {exc}", file=sys.stderr)
        time.sleep(float(config.get("request_delay_seconds", 1)))

    selected: list[Opportunity] = []
    for item in candidates.values():
        body = page_text(item.url, session)
        evaluated = evaluate(item, config, body)
        if evaluated:
            selected.append(evaluated)
        time.sleep(float(config.get("request_delay_seconds", 1)))
    return sorted(selected, key=lambda item: (-item.score, item.title.casefold()))


def render_markdown(items: list[Opportunity]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"## New European opportunity matches ({now})", ""]
    for item in items:
        lines += [f"### [{item.title}]({item.url})", "", f"- **Source:** {item.source}", f"- **Match score:** {item.score}", f"- **Age-limit evidence:** {item.age_status}"]
        if item.published:
            lines.append(f"- **Published:** {item.published}")
        for group, hits in item.matches.items():
            lines.append(f"- **{group.replace('_', ' ').title()}:** {', '.join(hits[:8])}")
        if item.summary:
            lines += ["", item.summary[:700]]
        lines += ["", "> Verify the official eligibility conditions and deadline before applying.", ""]
    lines += ["---", "Generated by **Europe Opportunity Alerts** — by Sameer Ali (sameer43786@gmail.com)."]
    return "\n".join(lines)


def create_github_issue(title: str, body: str) -> None:
    token, repository = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not token or not repository:
        print("GitHub environment unavailable; printing alert only.")
        print(body)
        return
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    # Label creation is idempotent: 422 means it already exists.
    label_response = requests.post(
        f"https://api.github.com/repos/{repository}/labels",
        headers=headers,
        json={"name": "opportunity-alert", "color": "1d76db", "description": "Automated European opportunity match"},
        timeout=30,
    )
    if label_response.status_code not in (201, 422):
        print(f"warning: could not create alert label: HTTP {label_response.status_code}", file=sys.stderr)
    response = requests.post(
        f"https://api.github.com/repos/{repository}/issues",
        headers=headers,
        json={"title": title, "body": body, "labels": ["opportunity-alert"]},
        timeout=30,
    )
    response.raise_for_status()
    print(f"Created GitHub issue: {response.json().get('html_url')}")


def send_email(subject: str, body: str) -> None:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "ALERT_EMAIL_TO"]
    if not all(os.getenv(name) for name in required):
        return
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, os.environ["SMTP_USERNAME"], os.environ["ALERT_EMAIL_TO"]
    message.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), context=context, timeout=30) as smtp:
        smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def run(config_path: Path, state_path: Path, dry_run: bool = False) -> int:
    config, seen = load_yaml(config_path), load_state(state_path)
    matches = collect(config)
    new_items = [item for item in matches if item.identity not in seen]
    max_alerts = int(config.get("max_alerts_per_run", 10))
    new_items = new_items[:max_alerts]
    print(f"Matched {len(matches)}; new {len(new_items)}.")
    if not new_items:
        return 0
    body = render_markdown(new_items)
    if dry_run:
        print(body)
        return 0
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    subject = f"{len(new_items)} new European opportunity match(es) - {date}"
    create_github_issue(subject, body)
    try:
        send_email(subject, body)
    except (OSError, smtplib.SMTPException) as exc:
        print(f"warning: email alert failed: {exc}", file=sys.stderr)
    seen.update(item.identity for item in new_items)
    save_state(state_path, seen)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Find relevant European training, project, youth and research opportunities.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--dry-run", action="store_true", help="print matches without alerting or changing state")
    args = parser.parse_args()
    return run(args.config, args.state, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
