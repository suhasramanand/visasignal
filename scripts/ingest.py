"""Orchestrates the whole ingestion pipeline: fetch every source in
sources.yaml, normalize, dedup, tag, and write the static JSON files the
frontend reads. Run with no arguments and no API keys required."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from dedup import dedup
from fetch_federal_register import fetch_federal_register
from fetch_processing_times import fetch_processing_times
from fetch_rss import fetch_rss
from fetch_visa_bulletin import fetch_visa_bulletin
from tag import tag

# High-volume, zero-signal boilerplate that shows up under every USCIS/DHS
# agency query -- routine paperwork renewals and unrelated crime prosecutions,
# neither of which is a visa/immigration *policy* change a reader cares about.
NOISE_TITLE_PATTERNS = [
    "agency information collection activities",
    "submission for omb review",
    "indicted for",
    "sentenced for",
    "pleads guilty",
    "deported for",
    "indicted in",
    "arrested in",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
HISTORY_DIR = DATA_DIR / "visa_bulletin_history"
PROCESSING_TIMES_HISTORY_DIR = DATA_DIR / "processing_times_history"
SOURCES_FILE = REPO_ROOT / "sources.yaml"


def load_sources() -> dict:
    with open(SOURCES_FILE) as f:
        return yaml.safe_load(f)


def collect_items(sources: dict) -> list:
    items = []

    for block in sources.get("federal_register", []):
        try:
            fetched = fetch_federal_register(
                block["name"], block["agencies"], block["types"], block.get("term")
            )
            print(f"  federal_register:{block['name']}: {len(fetched)} items", file=sys.stderr)
            items.extend(fetched)
        except Exception as exc:
            print(f"  federal_register:{block['name']} FAILED: {exc}", file=sys.stderr)

    for feed in sources.get("rss", []):
        try:
            fetched = fetch_rss(feed["name"], feed["url"], feed.get("trust", "official"))
            print(f"  rss:{feed['name']}: {len(fetched)} items", file=sys.stderr)
            items.extend(fetched)
        except Exception as exc:
            print(f"  rss:{feed['name']} FAILED: {exc}", file=sys.stderr)

    return items


def _is_noise(item) -> bool:
    title = item.title.lower()
    return any(pattern in title for pattern in NOISE_TITLE_PATTERNS)


def write_news(items: list) -> None:
    items = [item for item in items if not _is_noise(item)]
    deduped = dedup(items)
    tagged = [tag(item) for item in deduped]
    tagged.sort(key=lambda i: i.published_at, reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(tagged),
        "source_count": len({item.source for item in tagged}),
        "items": [item.to_dict() for item in tagged],
    }
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "data.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {len(tagged)} deduped/tagged items to data/data.json", file=sys.stderr)


def _parse_bulletin_date(value):
    if not value or value in ("C", "U"):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def compute_movement(previous: dict, new: dict) -> dict:
    """Per-cell month delta vs. the previous bulletin: positive = cutoff date
    advanced (good news, more people current), negative = retrogression,
    None = not comparable (missing history, or either side is C/U)."""
    movement: dict = {}
    for bulletin_type in ("final_action", "dates_for_filing"):
        movement[bulletin_type] = {}
        for section, categories in new.get(bulletin_type, {}).items():
            prev_categories = previous.get(bulletin_type, {}).get(section, {})
            movement[bulletin_type][section] = {}
            for category, countries in categories.items():
                prev_countries = prev_categories.get(category, {})
                movement[bulletin_type][section][category] = {}
                for country, value in countries.items():
                    new_date = _parse_bulletin_date(value)
                    old_date = _parse_bulletin_date(prev_countries.get(country))
                    if new_date is None or old_date is None:
                        delta = None
                    else:
                        delta = (new_date.year - old_date.year) * 12 + (new_date.month - old_date.month)
                    movement[bulletin_type][section][category][country] = delta
    return movement


def write_visa_bulletin(sources: dict) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    bulletin = fetch_visa_bulletin(sources["visa_bulletin"]["url_template"])

    if bulletin is None:
        print("  visa_bulletin: fetch failed (blocked + archive fallback unavailable) -- "
              "keeping previously committed data/visa_bulletin.json", file=sys.stderr)
        return

    current_path = DATA_DIR / "visa_bulletin.json"
    previous = None
    if current_path.exists():
        with open(current_path) as f:
            previous = json.load(f)
        archive_name = (previous.get("month") or "unknown").replace(" ", "-").lower() + ".json"
        shutil.copy(current_path, HISTORY_DIR / archive_name)

    bulletin["movement"] = compute_movement(previous, bulletin) if previous else {}

    with open(current_path, "w") as f:
        json.dump(bulletin, f, indent=2)
    print(f"  visa_bulletin: wrote {bulletin['month']}", file=sys.stderr)


def compute_processing_movement(previous: dict | None, new: dict) -> dict:
    """Per-highlight month delta vs. the previous snapshot: negative = faster
    (good news), positive = slower, None = not comparable (no history yet,
    or USCIS changed/removed this form+subtype combination)."""
    if previous is None:
        return {}
    prev_by_key = {h["key"]: h for h in previous.get("highlights", [])}
    movement = {}
    for h in new.get("highlights", []):
        prev = prev_by_key.get(h["key"])
        if prev is None:
            movement[h["key"]] = None
            continue
        movement[h["key"]] = {
            "delta_lower_months": round(h["range_lower_months"] - prev["range_lower_months"], 2),
            "delta_upper_months": round(h["range_upper_months"] - prev["range_upper_months"], 2),
        }
    return movement


def write_processing_times() -> None:
    PROCESSING_TIMES_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    result = fetch_processing_times()

    if result is None:
        print("  processing_times: fetch failed (jzebedee/uscis unreachable) -- "
              "keeping previously committed data/processing_times.json", file=sys.stderr)
        return

    current_path = DATA_DIR / "processing_times.json"
    previous = None
    if current_path.exists():
        with open(current_path) as f:
            previous = json.load(f)
        if previous.get("release_tag") != result["release_tag"]:
            archive_name = f"{previous.get('release_tag', 'unknown')}.json"
            shutil.copy(current_path, PROCESSING_TIMES_HISTORY_DIR / archive_name)

    result["movement"] = compute_processing_movement(previous, result)

    with open(current_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  processing_times: wrote release {result['release_tag']}"
          f"{' (stale)' if result['stale'] else ''}", file=sys.stderr)


def main() -> None:
    sources = load_sources()
    print("Fetching sources...", file=sys.stderr)
    items = collect_items(sources)
    write_news(items)
    write_visa_bulletin(sources)
    write_processing_times()


if __name__ == "__main__":
    main()
