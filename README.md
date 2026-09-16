# VisaSignal

Immigration/visa policy news for international students, aggregated from official U.S. government sources, tagged by visa category (F-1, OPT, STEM OPT, H-1B, green card / EB, travel & entry), and flagged for whether it's actually actionable — not just noise.

*Not legal advice. Informational only.*

## What it does

- Pulls rulemaking/notices from the **Federal Register API** (USCIS, DHS, ICE, State Dept — filtered to immigration-relevant content), **USCIS's RSS feeds**, and a couple of immigration law firm blogs (kept in a separate "Analysis" view, clearly badged apart from official sources).
- Dedups, tags by visa category, flags actionable items — all with plain keyword rules, no API keys or paid services required.
- Renders a filterable news feed, a condensed Visa Bulletin movement tracker, and the current **DOS Visa Bulletin** (when reachable — see note below) as a static site.
- Includes a "check your case status" widget that deep-links to USCIS's own case status page — receipt numbers never touch VisaSignal's pipeline, repo, or any server.
- Tracks USCIS processing times (OPT EAD, H-1B change-of-status/extension, I-140 EB-2/EB-3, I-485) via [jzebedee/uscis](https://github.com/jzebedee/uscis)'s daily-scraped data, since `egov.uscis.gov` is behind the same Cloudflare wall as `travel.state.gov`.
- Runs on a GitHub Actions cron schedule and commits the refreshed data back to the repo; the frontend is just static files reading that JSON.

## Run it locally

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/ingest.py
python3 -m http.server 8000
# open http://localhost:8000/web/index.html
```

## How the Visa Bulletin is sourced

`travel.state.gov` blocks automated requests with a whole-domain Cloudflare challenge (yes, even `robots.txt`). Rather than fight that, `scripts/fetch_visa_bulletin.py` treats [pd-tracker](https://github.com/yuchenlin/pd-tracker)'s GitHub-hosted JSON (already scraped monthly, served from `raw.githubusercontent.com`, not behind the same wall) as the primary source. If pd-tracker already has the current month, that's used directly — no need to touch travel.state.gov. If pd-tracker is lagging, one direct fetch is attempted (this also picks up family-sponsored categories, which pd-tracker doesn't cover); if that's blocked too, pd-tracker's latest available month is used as a stale-but-real fallback. If even pd-tracker is unreachable, the pipeline keeps whatever was last committed rather than overwriting it with nothing — check `data/visa_bulletin.json`'s `data_source` field to see which path produced the current data.

## Contributing

Adding a new source is usually a `sources.yaml` edit, not a code change. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

- **Now**: Federal Register + USCIS RSS + two law firm blogs + Visa Bulletin (with movement tracking), keyword tagging, case-status deep link, static dashboard.
- **Next**: Regulations.gov open comment periods, USCIS Policy Manual + SEVP broadcast message scraping, LLM-based summarization/classification (Groq free tier), more Analysis sources as blogs' RSS availability changes.
- **Later**: email/RSS-out digest, saved filters, Reddit signal (needs OAuth2 app registration — anonymous `.json` access is no longer available), Discord/Telegram bot.

## License

MIT — see [LICENSE](LICENSE).
