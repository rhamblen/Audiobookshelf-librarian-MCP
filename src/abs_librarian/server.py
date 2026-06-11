"""Audiobookshelf Librarian MCP server entry point."""

from __future__ import annotations

import os
import re

from mcp.server.fastmcp import FastMCP

from .abs_client import AUDIBLE, ABSClient
from .config import Config
from .fs_tools import (
    detect_blobs,
    fs_flatten,
    fs_make_book_folders,
    fs_move,
    fs_quarantine,
    fs_tree,
)
from .jail import PathJailError
from .metadata import SeriesCache, build_metadata_payload

cfg = Config.from_env()
_series_cache = SeriesCache()

mcp = FastMCP(
    "Audiobookshelf Librarian",
    stateless_http=True,
)

if cfg.mcp_token:
    # FastMCP bearer-token auth: set via env so the framework picks it up
    os.environ.setdefault("MCP_AUTH_TOKEN", cfg.mcp_token)


def _client() -> ABSClient:
    return ABSClient(cfg.abs_url, cfg.abs_token)


def _permitted() -> list[str]:
    return cfg.library_roots


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@mcp.tool()
async def health() -> dict:
    """Return server status and ABS connectivity."""
    client = _client()
    try:
        libs = await client.get_libraries()
        return {"status": "ok", "abs_libraries": len(libs)}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# ABS: Library overview
# ---------------------------------------------------------------------------

@mcp.tool()
async def library_overview() -> dict:
    """Return compact counts per library: items, series, authors, missing."""
    client = _client()
    libs = await client.get_libraries()
    result = []
    for lib in libs:
        items = await client.get_library_items(lib["id"])
        authors: set[str] = set()
        series: set[str] = set()
        no_cover = 0
        no_series = 0
        missing = 0
        for item in items:
            media = item.get("media", {})
            meta = media.get("metadata", {})
            if item.get("isMissing"):
                missing += 1
            if not item.get("media", {}).get("coverPath"):
                no_cover += 1
            s = meta.get("series") or []
            if not s:
                no_series += 1
            else:
                for sv in s:
                    series.add(sv.get("name", ""))
            for a in meta.get("authors") or []:
                authors.add(a.get("name", ""))
        result.append({
            "id": lib["id"],
            "name": lib["name"],
            "items": len(items),
            "authors": len(authors),
            "series": len(series),
            "no_cover": no_cover,
            "no_series": no_series,
            "missing": missing,
        })
    return {"libraries": result}


# ---------------------------------------------------------------------------
# ABS: find_items
# ---------------------------------------------------------------------------

@mcp.tool()
async def find_items(
    library_id: str,
    title_regex: str | None = None,
    author: str | None = None,
    series: str | None = None,
    no_cover: bool = False,
    no_series: bool = False,
    missing: bool = False,
    min_duration_hours: float | None = None,
    max_duration_hours: float | None = None,
    min_file_count: int | None = None,
    max_file_count: int | None = None,
    limit: int = 200,
) -> dict:
    """Search library items with optional filters. Returns compact results."""
    client = _client()
    items = await client.get_library_items(library_id)

    pattern = re.compile(title_regex, re.IGNORECASE) if title_regex else None
    results = []

    for item in items:
        media = item.get("media", {})
        meta = media.get("metadata", {})

        if missing and not item.get("isMissing"):
            continue
        if no_cover and item.get("media", {}).get("coverPath"):
            continue
        item_series = meta.get("series") or []
        if no_series and item_series:
            continue
        if series and not any(
            series.lower() in (sv.get("name") or "").lower() for sv in item_series
        ):
            continue
        if author:
            authors_str = " ".join(a.get("name", "") for a in (meta.get("authors") or []))
            if author.lower() not in authors_str.lower():
                continue
        title = meta.get("title") or item.get("path", "").split("/")[-1]
        if pattern and not pattern.search(title):
            continue

        duration = media.get("duration") or 0
        duration_hours = duration / 3600
        if min_duration_hours is not None and duration_hours < min_duration_hours:
            continue
        if max_duration_hours is not None and duration_hours > max_duration_hours:
            continue

        files = media.get("audioFiles") or media.get("tracks") or []
        file_count = len(files)
        if min_file_count is not None and file_count < min_file_count:
            continue
        if max_file_count is not None and file_count > max_file_count:
            continue

        results.append({
            "id": item["id"],
            "title": title,
            "authors": [a.get("name") for a in (meta.get("authors") or [])],
            "series": [
                {"name": sv.get("name"), "sequence": sv.get("sequence")}
                for sv in item_series
            ],
            "duration_hours": round(duration_hours, 2),
            "file_count": file_count,
            "path": item.get("path"),
            "has_cover": bool(item.get("media", {}).get("coverPath")),
            "is_missing": item.get("isMissing", False),
        })

        if len(results) >= limit:
            break

    return {"count": len(results), "items": results}


# ---------------------------------------------------------------------------
# ABS: get_item
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_item(item_id: str) -> dict:
    """Return full detail for a single item including file list."""
    client = _client()
    return await client.get_item(item_id)


# ---------------------------------------------------------------------------
# ABS: batch_update_metadata
# ---------------------------------------------------------------------------

@mcp.tool()
async def batch_update_metadata(
    library_id: str,
    updates: list[dict],
) -> dict:
    """
    Bulk-update metadata for multiple items.

    Each update dict: {id, title?, authors?, narrators?, series?, genres?, tags?}
    series items: {name, sequence?} — series names are cached to reuse existing ids.
    """
    client = _client()

    # Seed series cache for this library if not already done
    if not _series_cache._cache:
        existing = await client.get_series(library_id)
        _series_cache.seed(existing)

    payloads = []
    for u in updates:
        item_id = u["id"]
        series_raw = u.get("series")
        resolved_series = None
        if series_raw is not None:
            resolved_series = [
                _series_cache.resolve(s["name"], s.get("sequence", ""))
                for s in series_raw
            ]
        meta = build_metadata_payload(
            title=u.get("title"),
            authors=u.get("authors"),
            narrators=u.get("narrators"),
            series=resolved_series,
            genres=u.get("genres"),
            tags=u.get("tags"),
        )
        payloads.append({"id": item_id, "mediaPayload": {"metadata": meta}})

    results = await client.batch_update(payloads)
    return {"updated": len(payloads), "results": results}


# ---------------------------------------------------------------------------
# ABS: quick_match
# ---------------------------------------------------------------------------

@mcp.tool()
async def quick_match(
    item_ids: list[str],
    provider: str = AUDIBLE,
    override_cover: bool = False,
    override_details: bool = False,
) -> dict:
    """Batch quick-match items against a metadata provider."""
    client = _client()
    result = await client.batch_quickmatch(item_ids, provider, override_cover, override_details)
    return {"matched": len(item_ids), "result": result}


# ---------------------------------------------------------------------------
# ABS: set_cover
# ---------------------------------------------------------------------------

@mcp.tool()
async def set_cover(
    item_id: str,
    url: str | None = None,
    search_title: str | None = None,
    search_author: str | None = None,
    provider: str = AUDIBLE,
) -> dict:
    """Set a cover from a URL, or search a provider and use the first result."""
    client = _client()
    if url:
        result = await client.set_cover_url(item_id, url)
        return {"item_id": item_id, "source": "url", "result": result}
    if search_title:
        covers = await client.search_covers(search_title, search_author or "", provider)
        if not covers:
            return {"error": "no covers found", "item_id": item_id}
        first_url = covers[0].get("image") or covers[0].get("url") or covers[0]
        if not isinstance(first_url, str):
            return {"error": "unexpected cover format", "raw": covers[0]}
        result = await client.set_cover_url(item_id, first_url)
        return {"item_id": item_id, "source": "search", "cover_url": first_url, "result": result}
    return {"error": "provide url or search_title"}


# ---------------------------------------------------------------------------
# ABS: scan_library
# ---------------------------------------------------------------------------

@mcp.tool()
async def scan_library(library_id: str) -> dict:
    """Trigger a library scan."""
    client = _client()
    result = await client.scan_library(library_id)
    return {"library_id": library_id, "result": result}


# ---------------------------------------------------------------------------
# ABS: list_missing / purge_missing
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_missing(library_id: str) -> dict:
    """List items marked as missing in ABS."""
    client = _client()
    items = await client.get_library_items_missing(library_id)
    return {
        "count": len(items),
        "items": [
            {
                "id": i["id"],
                "path": i.get("path"),
                "title": i.get("media", {}).get("metadata", {}).get("title"),
            }
            for i in items
        ],
    }


@mcp.tool()
async def purge_missing(library_id: str, confirm: bool = False) -> dict:
    """Delete ABS records for all missing items (does NOT touch files)."""
    client = _client()
    if not confirm:
        items = await client.get_library_items_missing(library_id)
        return {"dry_run": True, "would_purge": len(items), "items": [i["id"] for i in items]}
    items = await client.get_library_items_missing(library_id)
    deleted = []
    errors = []
    for item in items:
        try:
            await client.delete_item(item["id"])
            deleted.append(item["id"])
        except Exception as exc:
            errors.append({"id": item["id"], "error": str(exc)})
    return {"deleted": len(deleted), "errors": errors}


# ---------------------------------------------------------------------------
# ABS: create_backup
# ---------------------------------------------------------------------------

@mcp.tool()
async def create_backup() -> dict:
    """Trigger an ABS backup."""
    client = _client()
    return await client.create_backup()


# ---------------------------------------------------------------------------
# FS: fs_tree
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_fs_tree(path: str, max_depth: int = 3) -> dict:
    """Return a folder tree with audio-file counts (depth-limited)."""
    try:
        return fs_tree(path, _permitted(), max_depth)
    except PathJailError as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# FS: detect_blobs
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_detect_blobs(
    path: str,
    hours_threshold: float | None = None,
    file_count_threshold: int | None = None,
) -> dict:
    """Heuristic scan for blob folders and duplicate suspects."""
    try:
        return detect_blobs(
            path,
            _permitted(),
            hours_threshold if hours_threshold is not None else cfg.blob_hours_threshold,
            file_count_threshold
            if file_count_threshold is not None
            else cfg.blob_file_count_threshold,
        )
    except PathJailError as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# FS: fs_make_book_folders
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_fs_make_book_folders(path: str, confirm: bool = False) -> dict:
    """
    Split a blob folder: move each loose audio file into its own named subfolder.
    Default dry_run=True; pass confirm=True to execute.
    """
    try:
        return fs_make_book_folders(path, _permitted(), cfg.audit_log, confirm)
    except PathJailError as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# FS: fs_flatten
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_fs_flatten(path: str, confirm: bool = False) -> dict:
    """
    Flatten disc/CD/part subfolders into the parent with prefixed filenames.
    Default dry_run=True; pass confirm=True to execute.
    """
    try:
        return fs_flatten(path, _permitted(), cfg.audit_log, confirm)
    except PathJailError as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# FS: fs_move
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_fs_move(src: str, dest: str, confirm: bool = False) -> dict:
    """
    Move a file or folder within the library.
    No overwrite; creates parent dirs.
    Default dry_run=True; pass confirm=True to execute.
    """
    try:
        return fs_move(src, dest, _permitted(), cfg.audit_log, confirm)
    except PathJailError as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# FS: fs_quarantine
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_fs_quarantine(path: str, confirm: bool = False) -> dict:
    """
    Move a file or folder to the quarantine directory (preserves structure).
    Nothing is deleted.
    Default dry_run=True; pass confirm=True to execute.
    """
    try:
        return fs_quarantine(path, _permitted(), cfg.quarantine_dir, cfg.audit_log, confirm)
    except PathJailError as e:
        return {"error": str(e)}
