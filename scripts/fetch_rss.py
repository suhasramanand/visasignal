"""Generic RSS/Atom fetch used for USCIS newsroom and alert feeds."""
from __future__ import annotations

from datetime import datetime, timezone
import time

import feedparser
import requests
from bs4 import BeautifulSoup

from normalize import Item


def _to_iso(entry) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _clean_summary(raw_summary: str) -> str:
    # WordPress feeds (law firm blogs) embed full HTML in the summary/description;
    # official RSS feeds are already plain text, but stripping tags is a no-op for those.
    text = BeautifulSoup(raw_summary, "html.parser").get_text(" ", strip=True)
    return text.split(". ")[0][:300] if text else ""


def fetch_rss(source_name: str, url: str, source_trust: str = "official") -> list[Item]:
    # Fetch with requests (uses certifi's CA bundle) rather than letting
    # feedparser open the URL itself -- feedparser's urllib call fails SSL
    # verification in some Python installs that lack system CA certs.
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    items = []
    for entry in feed.entries:
        summary = entry.get("summary") or ""
        items.append(
            Item(
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                source=f"rss:{source_name}",
                source_trust=source_trust,
                published_at=_to_iso(entry),
                summary=_clean_summary(summary),
                raw=dict(entry),
            )
        )
    return items
