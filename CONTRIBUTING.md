# Contributing

## Add a news source

Most sources need zero code:

- **Federal Register query** — add a block under `federal_register:` in `sources.yaml` with an agency slug (look it up at `https://www.federalregister.gov/api/v1/agencies.json`) and optionally a `term` (free-text search) to keep the query focused on immigration content instead of everything that agency publishes.
- **RSS feed** — add `name` + `url` under `rss:` in `sources.yaml`.

If a source has no RSS/API and needs HTML scraping (like the Visa Bulletin), add a new `scripts/fetch_<source>.py` module following the pattern in `fetch_visa_bulletin.py`: return `None` on failure instead of raising, so one broken scraper never takes down the rest of the pipeline.

## Add or refine a tag

Edit `scripts/tag.py`. `CATEGORY_KEYWORDS` maps a category to keyword/phrase strings matched (case-insensitive) against the title + summary. `ACTIONABLE_KEYWORDS` flags items that represent a concrete deadline/change vs. general informational content.

## Reduce noise

`scripts/ingest.py` has a `NOISE_TITLE_PATTERNS` list that drops high-volume, zero-signal boilerplate (OMB paperwork renewals, individual criminal case press releases) before tagging. If a new source introduces its own boilerplate pattern, add it there rather than trying to categorize it away.

## Run locally

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/ingest.py
python3 -m http.server 8000   # serve repo root
# open http://localhost:8000/web/index.html
```

No API keys are required for the current source set.

## Good first issues

- Add one of the Phase 2 RSS blogs (Murthy Law Firm, Cyrus Mehta's Insightful Immigration Blog, etc. — see project roadmap) to `sources.yaml`.
- Improve a `CATEGORY_KEYWORDS` list where you've spotted a miscategorized item.
- Add a new `NOISE_TITLE_PATTERNS` entry for boilerplate you've noticed slipping through.
