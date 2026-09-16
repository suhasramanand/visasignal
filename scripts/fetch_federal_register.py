"""Pull rulemaking documents from the free, unauthenticated Federal Register API."""
from __future__ import annotations

import requests

from normalize import Item

API_URL = "https://www.federalregister.gov/api/v1/documents.json"
FIELDS = ["title", "abstract", "publication_date", "html_url", "agencies", "docket_ids", "type"]


def fetch_federal_register(
    source_name: str, agencies: list[str], types: list[str], term: str | None = None
) -> list[Item]:
    params = [
        ("conditions[agencies][]", agency) for agency in agencies
    ] + [
        ("conditions[type][]", doc_type) for doc_type in types
    ] + [
        ("order", "newest"),
        ("per_page", "50"),
    ] + [("fields[]", field) for field in FIELDS]
    if term:
        params.append(("conditions[term]", term))

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    items = []
    for doc in payload.get("results", []):
        abstract = doc.get("abstract") or ""
        items.append(
            Item(
                title=doc["title"],
                url=doc["html_url"],
                source=f"federal_register:{source_name}",
                source_trust="official",
                published_at=doc["publication_date"],
                summary=abstract.split(". ")[0].strip() if abstract else "",
                raw=doc,
            )
        )
    return items
