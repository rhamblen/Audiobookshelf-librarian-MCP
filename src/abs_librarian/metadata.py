"""Helpers for building and filtering ABS metadata payloads."""

from __future__ import annotations

import re
from typing import Any


def build_metadata_payload(
    *,
    title: str | None = None,
    authors: list[str] | None = None,
    narrators: list[str] | None = None,
    series: list[dict] | None = None,
    genres: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Return a metadata dict containing only the fields that were supplied."""
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if authors is not None:
        payload["authors"] = [{"name": a} if isinstance(a, str) else a for a in authors]
    if narrators is not None:
        payload["narrators"] = [{"name": n} if isinstance(n, str) else n for n in narrators]
    if series is not None:
        # series items: {"name": "...", "sequence": "..."} or {"id": "...", "sequence": "..."}
        payload["series"] = series
    if genres is not None:
        payload["genres"] = genres
    if tags is not None:
        payload["tags"] = tags
    return payload


class SeriesCache:
    """Maps series name → ABS series id to avoid creating duplicates."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def seed(self, series_list: list[dict]) -> None:
        for s in series_list:
            name = (s.get("name") or "").strip().lower()
            if name and s.get("id"):
                self._cache[name] = s["id"]

    def resolve(self, name: str, sequence: str = "") -> dict:
        key = name.strip().lower()
        if key in self._cache:
            return {"id": self._cache[key], "sequence": sequence}
        return {"name": name.strip(), "sequence": sequence}

    def add(self, name: str, series_id: str) -> None:
        self._cache[name.strip().lower()] = series_id
