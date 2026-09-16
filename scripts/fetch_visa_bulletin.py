"""Get the current DOS Visa Bulletin.

travel.state.gov sits behind a whole-domain Cloudflare bot-block that rejects
plain HTTP clients (even robots.txt returns the challenge page). Rather than
fight that with a scraper-vs-WAF arms race, this leans on `pd-tracker`
(github.com/yuchenlin/pd-tracker), an existing open-source project that
already scrapes DOS's employment-based tables monthly and publishes the
result as JSON on GitHub raw -- which isn't behind the same wall.

Hierarchy: pd-tracker's latest entry is the primary source. If pd-tracker
already has the current calendar month, that's the answer -- no need to touch
travel.state.gov at all. If pd-tracker is lagging (their monthly scrape hasn't
run yet), we try one direct fetch against travel.state.gov for the newest
month (this also picks up family-sponsored categories, which pd-tracker
doesn't cover). If that's blocked too, we fall back to pd-tracker's latest
available month -- stale by a few weeks, but real data beats a placeholder.
If even pd-tracker is unreachable, `fetch_visa_bulletin` returns None and the
caller keeps whatever was last committed rather than overwriting it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

import requests
from bs4 import BeautifulSoup

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

PD_TRACKER_URL = "https://raw.githubusercontent.com/yuchenlin/pd-tracker/main/src/data/visa-bulletins.json"
COUNTRY_ORDER = ["ROW", "CHINA", "INDIA", "MEXICO", "PHILIPPINES"]
# Family-sponsored rows are F1/F2A/F2B/F3/F4; employment-based rows are the
# ordinals 1st-5th in the actual DOS table markup -- normalized to EB-1..EB-5
# below so category keys are the same human-readable form regardless of
# whether the data came from our own scrape or from pd-tracker.
CATEGORY_RE = re.compile(r"^(F[1-4][AB]?|1st|2nd|3rd|4th|5th)$", re.IGNORECASE)
ORDINAL_TO_EB = {"1ST": "EB-1", "2ND": "EB-2", "3RD": "EB-3", "4TH": "EB-4", "5TH": "EB-5"}


def _normalize_category(raw: str) -> str:
    upper = raw.upper()
    return ORDINAL_TO_EB.get(upper, upper)


def _looks_like_cloudflare_block(html: str) -> bool:
    return "attention required" in html[:3000].lower() or "cf-error-details" in html[:3000].lower()


def _fetch_pdtracker() -> tuple[dict, str] | None:
    """Return (raw_bulletin_entry, bulletin_id) for pd-tracker's latest month, or None."""
    try:
        resp = requests.get(PD_TRACKER_URL, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        bulletins = payload.get("bulletins") or []
        if not bulletins:
            return None
        latest = max(bulletins, key=lambda b: b["id"])
        return latest, latest["id"]
    except (requests.RequestException, ValueError, KeyError):
        return None


def _pdtracker_value(raw_value) -> str:
    """pd-tracker encodes Current as null and Unavailable as 'U' -- normalize
    to the same 'C'/'U'/ISO-date strings our own scraper would produce."""
    if raw_value is None:
        return "C"
    return raw_value


def _bulletin_from_pdtracker(entry: dict) -> dict:
    bulletin: dict = {"final_action": {}, "dates_for_filing": {}}
    for table_key, bulletin_type in (("A", "final_action"), ("B", "dates_for_filing")):
        categories = entry.get("tables", {}).get(table_key, {})
        section: dict[str, dict[str, str]] = {}
        for category, countries in categories.items():
            section[category] = {c: _pdtracker_value(countries.get(c)) for c in COUNTRY_ORDER}
        if section:
            bulletin[bulletin_type]["employment_based"] = section

    bulletin["source_url"] = entry.get("sourceUrl")
    bulletin["month"] = datetime(entry["year"], entry["month"], 1).strftime("%B %Y")
    bulletin["data_source"] = "pd-tracker (GitHub, family-sponsored not covered, may lag ~1 month)"
    return bulletin


def _fetch_direct(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=20)
        if resp.status_code == 200 and not _looks_like_cloudflare_block(resp.text):
            return resp.text
    except requests.RequestException:
        pass
    return None


def _classify_table(preceding_text: str) -> tuple[str, str] | None:
    """Return (bulletin_type, section) for a table based on nearby heading text."""
    text = preceding_text.lower()
    if "final action date" in text:
        bulletin_type = "final_action"
    elif "dates for filing" in text:
        bulletin_type = "dates_for_filing"
    else:
        return None
    section = "employment_based" if "employment" in text else "family_sponsored"
    return bulletin_type, section


def _parse_table(table) -> dict[str, dict[str, str]]:
    rows = table.find_all("tr")
    result: dict[str, dict[str, str]] = {}
    for row in rows[1:]:  # skip header row
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if not cells or not CATEGORY_RE.match(cells[0]):
            continue
        category = _normalize_category(cells[0])
        values = cells[1:]
        result[category] = {
            country: values[i] if i < len(values) else "U"
            for i, country in enumerate(COUNTRY_ORDER)
        }
    return result


def _parse_bulletin_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    bulletin: dict = {"final_action": {}, "dates_for_filing": {}}

    for table in soup.find_all("table"):
        # Walk backwards through preceding siblings/headings to find context text.
        context_chunks = []
        node = table
        steps = 0
        while node is not None and steps < 8:
            node = node.find_previous(["h1", "h2", "h3", "h4", "strong", "caption"])
            if node is None:
                break
            context_chunks.append(node.get_text(" ", strip=True))
            steps += 1
        classification = _classify_table(" ".join(context_chunks))
        if classification is None:
            continue
        bulletin_type, section = classification
        parsed = _parse_table(table)
        if not parsed:
            continue
        bulletin[bulletin_type].setdefault(section, {}).update(parsed)

    return bulletin


def _fetch_live(url_template: str, now: datetime) -> dict | None:
    month_name = now.strftime("%B").lower()
    url = url_template.format(year=now.year, month=month_name)

    html = _fetch_direct(url)
    if html is None:
        return None
    try:
        bulletin = _parse_bulletin_html(html)
    except Exception:
        return None
    if not bulletin["final_action"] and not bulletin["dates_for_filing"]:
        return None

    bulletin["source_url"] = url
    bulletin["month"] = now.strftime("%B %Y")
    bulletin["data_source"] = "travel.state.gov (live)"
    return bulletin


def fetch_visa_bulletin(url_template: str) -> dict | None:
    now = datetime.now(timezone.utc)
    target_id = f"{now.year}-{now.month:02d}"

    pdtracker_result = _fetch_pdtracker()
    if pdtracker_result and pdtracker_result[1] == target_id:
        bulletin = _bulletin_from_pdtracker(pdtracker_result[0])
        bulletin["fetched_at"] = now.isoformat()
        return bulletin

    live = _fetch_live(url_template, now)
    if live:
        live["fetched_at"] = now.isoformat()
        return live

    if pdtracker_result:
        bulletin = _bulletin_from_pdtracker(pdtracker_result[0])
        bulletin["fetched_at"] = now.isoformat()
        return bulletin

    return None
