"""Thin async HTTP client for the Audiobookshelf REST API."""

from __future__ import annotations

import base64
from typing import Any

import httpx

AUDIBLE = "audible"
_BATCH_SIZE = 100


class ABSClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url
        self._headers = {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, **params: Any) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self._base}{path}", headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, body: Any = None) -> Any:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{self._base}{path}", headers=self._headers, json=body)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _patch(self, path: str, body: Any) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(f"{self._base}{path}", headers=self._headers, json=body)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _delete(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.delete(f"{self._base}{path}", headers=self._headers)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    # ------------------------------------------------------------------
    # Libraries
    # ------------------------------------------------------------------

    async def get_libraries(self) -> list[dict]:
        data = await self._get("/api/libraries")
        return data.get("libraries", [])

    async def get_library_items(self, library_id: str) -> list[dict]:
        data = await self._get(f"/api/libraries/{library_id}/items", limit=0)
        return data.get("results", [])

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    async def get_item(self, item_id: str) -> dict:
        return await self._get(f"/api/items/{item_id}", expanded=1)

    async def patch_item_metadata(self, item_id: str, metadata: dict) -> dict:
        return await self._patch(f"/api/items/{item_id}/media", {"metadata": metadata})

    async def batch_update(self, updates: list[dict]) -> list[dict]:
        """Send updates in chunks of _BATCH_SIZE. Returns list of per-item results."""
        results: list[dict] = []
        for i in range(0, len(updates), _BATCH_SIZE):
            chunk = updates[i : i + _BATCH_SIZE]
            resp = await self._post("/api/items/batch/update", chunk)
            if isinstance(resp, list):
                results.extend(resp)
        return results

    async def batch_quickmatch(
        self,
        item_ids: list[str],
        provider: str = AUDIBLE,
        override_cover: bool = False,
        override_details: bool = False,
    ) -> dict:
        body = {
            "options": {
                "provider": provider,
                "overrideCover": override_cover,
                "overrideDetails": override_details,
            },
            "libraryItemIds": item_ids,
        }
        return await self._post("/api/items/batch/quickmatch", body)

    # ------------------------------------------------------------------
    # Covers
    # ------------------------------------------------------------------

    async def search_covers(self, title: str, author: str, provider: str = AUDIBLE) -> list[dict]:
        data = await self._get("/api/search/covers", title=title, author=author, provider=provider)
        return data if isinstance(data, list) else data.get("results", [])

    async def set_cover_url(self, item_id: str, url: str) -> dict:
        return await self._post(f"/api/items/{item_id}/cover", {"url": url})

    # ------------------------------------------------------------------
    # Library maintenance
    # ------------------------------------------------------------------

    async def scan_library(self, library_id: str) -> dict:
        return await self._post(f"/api/libraries/{library_id}/scan")

    async def get_library_items_missing(self, library_id: str) -> list[dict]:
        f = "issues." + base64.b64encode(b"missing").decode()
        data = await self._get(
            f"/api/libraries/{library_id}/items", filter=f, limit=0
        )
        return data.get("results", [])

    async def delete_item(self, item_id: str) -> dict:
        """Deletes an item *record* from ABS (used only for confirmed missing items)."""
        return await self._delete(f"/api/items/{item_id}")

    async def create_backup(self) -> dict:
        return await self._post("/api/backups")

    # ------------------------------------------------------------------
    # Series helpers
    # ------------------------------------------------------------------

    async def get_series(self, library_id: str) -> list[dict]:
        data = await self._get(f"/api/libraries/{library_id}/series", limit=0)
        return data.get("results", [])
