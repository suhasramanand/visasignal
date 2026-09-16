"""Common item shape shared by every source-specific fetcher."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Item:
    title: str
    url: str
    source: str
    source_trust: str
    published_at: str  # ISO 8601
    summary: str
    categories: list[str] = field(default_factory=list)
    actionable: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw")  # keep data.json lean; raw is only useful for debugging locally
        return d
