"""Keyword-rule tagging. No LLM/API key needed for v0 -- upgrade path is
described in CONTRIBUTING.md once the pipeline is proven end-to-end."""
from __future__ import annotations

from normalize import Item

# Order matters only for readability; every matching category is kept.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "stem_opt": ["stem opt", "stem-opt", "24-month extension", "24 month extension"],
    "opt": ["optional practical training", " opt ", "opt extension", "post-completion opt"],
    "f1": ["f-1", "f1 visa", "sevis", "sevp", "i-20", "student visa"],
    "h1b": ["h-1b", "h1b", "specialty occupation", "h-1b cap", "lottery registration"],
    "green_card": [
        "green card", "permanent resident", "immigrant visa", "employment-based",
        "eb-1", "eb-2", "eb-3", "eb-4", "eb-5", "i-485", "adjustment of status",
        "visa bulletin",
    ],
    "travel_entry": [
        "travel ban", "port of entry", "cbp", "customs and border", "entry restriction",
        "visa waiver", "travel advisory", "reentry",
    ],
}

ACTIONABLE_KEYWORDS = [
    "final rule", "effective on", "effective date", "deadline", "fee increase",
    "fee schedule", "new fee", "expires", "expiration", "extension of status",
    "revocation", "suspend", "terminate", "must file", "last day to",
]


def _matches(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def tag(item: Item) -> Item:
    text = f"{item.title} {item.summary}".lower()
    categories = [cat for cat, keywords in CATEGORY_KEYWORDS.items() if _matches(text, keywords)]
    item.categories = categories or ["general"]
    item.actionable = _matches(text, ACTIONABLE_KEYWORDS)
    return item
