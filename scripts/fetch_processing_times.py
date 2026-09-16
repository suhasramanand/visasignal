"""Get current USCIS processing times.

egov.uscis.gov's processing-times site/API is behind the same Cloudflare
bot-block as everything else on USCIS's domains (verified this session:
403 on every endpoint tried, even with browser headers). Rather than fight
that, this consumes github.com/jzebedee/uscis's daily-dated GitHub release,
which already scrapes the official site (with residential-proxy support on
their end, per their own changelog) and publishes the result as a SQLite
database asset -- reachable via the normal GitHub Releases API, no
Cloudflare wall.

Only a hand-picked set of form/category combinations relevant to this
audience are surfaced (not all ~500 rows in their database): F-1 OPT EAD,
H-1B change-of-status and extension, EB-2/EB-3 I-140, and I-485 (median
across USCIS field offices, since that's reported per-office nationally).
"""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timezone
from statistics import median

import requests

RELEASES_API = "https://api.github.com/repos/jzebedee/uscis/releases/latest"
STALE_AFTER_HOURS = 72  # their scrape runs daily; a few missed days is a signal, not a crash

# (form_name, form_subtype, display label)
HIGHLIGHTS = [
    ("I-765", "147-C3", "OPT (F-1 academic student)"),
    ("I-129", "137-H1B2", "H-1B (change of status)"),
    ("I-129", "137-H1B3", "H-1B (extension of stay)"),
    ("I-140", "136A-E21", "I-140 EB-2 (advanced degree)"),
    ("I-140", "136A-E31", "I-140 EB-3 (skilled worker)"),
]

UNIT_TO_MONTHS = {"Days": 1 / 30, "Weeks": 1 / 4.345, "Months": 1, "Years": 12}


def _to_months(value: float, unit: str) -> float:
    return round(value * UNIT_TO_MONTHS.get(unit, 1), 2)


def _fetch_latest_release() -> dict | None:
    try:
        resp = requests.get(RELEASES_API, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        db_asset = next((a for a in payload["assets"] if a["name"].endswith(".db")), None)
        if db_asset is None:
            return None
        return {
            "tag": payload["tag_name"],
            "published_at": payload["published_at"],
            "download_url": db_asset["browser_download_url"],
        }
    except (requests.RequestException, KeyError, StopIteration):
        return None


def _query_highlights(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    results = []

    for form_name, subtype, label in HIGHLIGHTS:
        cur.execute(
            "SELECT range_lower, range_lower_unit, range_upper, range_upper_unit, publication_date "
            "FROM processing_time WHERE form_name=? AND form_subtype=? LIMIT 1",
            (form_name, subtype),
        )
        row = cur.fetchone()
        if row is None or row["range_lower"] is None or row["range_upper"] is None:
            continue
        results.append(
            {
                "key": f"{form_name}_{subtype}",
                "form": form_name,
                "label": label,
                "range_lower_months": _to_months(row["range_lower"], row["range_lower_unit"]),
                "range_upper_months": _to_months(row["range_upper"], row["range_upper_unit"]),
                "display": f"{row['range_lower']:g} {row['range_lower_unit']} - {row['range_upper']:g} {row['range_upper_unit']}",
                "as_of": row["publication_date"],
            }
        )

    # I-485 is reported per USCIS field office (dozens of them) rather than
    # nationally -- a median across offices is a more honest "ballpark" than
    # picking one arbitrary office.
    cur.execute(
        "SELECT range_lower, range_lower_unit, range_upper, range_upper_unit FROM processing_time "
        "WHERE form_name='I-485' AND range_lower IS NOT NULL AND range_upper IS NOT NULL"
    )
    i485_rows = cur.fetchall()
    if i485_rows:
        lowers = [_to_months(r["range_lower"], r["range_lower_unit"]) for r in i485_rows]
        uppers = [_to_months(r["range_upper"], r["range_upper_unit"]) for r in i485_rows]
        lower_med, upper_med = round(median(lowers), 1), round(median(uppers), 1)
        results.append(
            {
                "key": "I-485_median",
                "form": "I-485",
                "label": "Adjustment of Status (median across field offices)",
                "range_lower_months": lower_med,
                "range_upper_months": upper_med,
                "display": f"~{lower_med:g} - {upper_med:g} months",
                "as_of": None,
            }
        )

    conn.close()
    return results


def fetch_processing_times() -> dict | None:
    release = _fetch_latest_release()
    if release is None:
        return None

    published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
    age_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600

    try:
        db_resp = requests.get(release["download_url"], timeout=60)
        db_resp.raise_for_status()
    except requests.RequestException:
        return None

    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp.write(db_resp.content)
        tmp.flush()
        try:
            highlights = _query_highlights(tmp.name)
        except sqlite3.Error:
            return None

    if not highlights:
        return None

    return {
        "release_tag": release["tag"],
        "release_published_at": release["published_at"],
        "release_age_hours": round(age_hours, 1),
        "stale": age_hours > STALE_AFTER_HOURS,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "github.com/jzebedee/uscis (daily scrape, not official USCIS API)",
        "highlights": highlights,
    }
