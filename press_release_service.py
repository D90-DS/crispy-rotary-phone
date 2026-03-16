from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PressReleaseService:
    """
    Lightweight service for querying press releases stored in JSON.

    This keeps the project simple:
      - no vector store
      - no extra indexing layer
      - easy to explain in an interview
    """

    def __init__(self, json_path: str | Path):
        self.json_path = Path(json_path)
        self.items = self._load_items()

    def _load_items(self) -> list[dict[str, Any]]:
        with self.json_path.open("r", encoding="utf-8") as f:
            items = json.load(f)

        # Keep newest first.
        return sorted(items, key=lambda x: x.get("date", ""), reverse=True)

    def list_recent(self, limit: int = 5) -> list[dict[str, Any]]:
        """Return the most recent press releases."""
        return self.items[:limit]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Basic keyword search across title, summary, category, and tags.
        """
        q = query.lower().strip()
        results = []

        for item in self.items:
            haystack = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("summary", "")),
                    str(item.get("category", "")),
                    " ".join(item.get("tags", [])),
                ]
            ).lower()

            if q in haystack:
                results.append(item)

        return results[:limit]

    def extract_insight_counts(self) -> dict[str, int]:
        """
        Count high-level press release themes for quick dashboard/chat summaries.
        """
        counts = {
            "acquisition": 0,
            "expansion": 0,
            "quarterly_update": 0,
            "business_update": 0,
        }

        for item in self.items:
            category = str(item.get("category", "business_update")).lower()
            if category in counts:
                counts[category] += 1
            else:
                counts["business_update"] += 1

        return counts
