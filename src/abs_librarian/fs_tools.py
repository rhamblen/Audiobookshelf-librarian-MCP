"""File-system tools: tree, split blobs, flatten, move, quarantine, detect blobs."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from .audit import log_operation
from .jail import resolve_safe

AUDIO_EXTS = {".mp3", ".m4b", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wav", ".wma"}
META_FILES = {"metadata.json", "cover.jpg", "cover.png", "cover.jpeg", "cover.webp"}

# Patterns that suggest per-disc/part subfolders
_DISC_PATTERNS = re.compile(
    r"^(disc|disk|cd|part|vol|volume|book)\s*\d+$", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# fs_tree
# ---------------------------------------------------------------------------

def fs_tree(
    path: str,
    permitted_roots: list[str],
    max_depth: int = 3,
) -> dict[str, Any]:
    root = resolve_safe(path, permitted_roots)
    return {"path": str(root), "tree": _walk(root, max_depth, 0)}


def _walk(path: Path, max_depth: int, depth: int) -> dict[str, Any]:
    audio_files = []
    subdirs = []
    total_bytes = 0

    try:
        entries = sorted(path.iterdir())
    except PermissionError:
        return {"name": path.name, "error": "permission denied"}

    for entry in entries:
        if entry.is_symlink():
            continue
        if entry.is_file() and entry.suffix.lower() in AUDIO_EXTS:
            audio_files.append({"name": entry.name, "bytes": entry.stat().st_size})
            total_bytes += entry.stat().st_size
        elif entry.is_dir():
            if depth < max_depth:
                child = _walk(entry, max_depth, depth + 1)
                subdirs.append(child)
                total_bytes += child.get("total_bytes", 0)
            else:
                subdirs.append({"name": entry.name, "truncated": True})

    return {
        "name": path.name,
        "audio_count": len(audio_files),
        "total_bytes": total_bytes,
        "audio_files": [],
        "subdirs": subdirs,
    }


# ---------------------------------------------------------------------------
# detect_blobs
# ---------------------------------------------------------------------------

def detect_blobs(
    path: str,
    permitted_roots: list[str],
    hours_threshold: float,
    file_count_threshold: int,
) -> dict[str, Any]:
    root = resolve_safe(path, permitted_roots)
    suspects: list[dict] = []

    for item_dir in sorted(root.iterdir()):
        if not item_dir.is_dir() or item_dir.is_symlink():
            continue
        audio = _gather_audio(item_dir)
        if not audio:
            continue
        total_bytes = sum(f.stat().st_size for f in audio)
        # Rough duration estimate: 1 MB ≈ 1 minute for 128 kbps MP3; good enough for flagging
        est_hours = (total_bytes / (128 * 1024 / 8)) / 3600
        if len(audio) >= file_count_threshold or est_hours >= hours_threshold:
            suspects.append({
                "path": str(item_dir),
                "audio_count": len(audio),
                "est_hours": round(est_hours, 1),
                "has_disc_subfolders": _has_disc_subfolders(item_dir),
            })

    return {"suspects": suspects, "count": len(suspects)}


def _gather_audio(path: Path) -> list[Path]:
    return [
        f for f in path.rglob("*")
        if f.is_file() and f.suffix.lower() in AUDIO_EXTS
    ]


def _has_disc_subfolders(path: Path) -> bool:
    return any(
        _DISC_PATTERNS.match(d.name)
        for d in path.iterdir()
        if d.is_dir() and not d.is_symlink()
    )


# ---------------------------------------------------------------------------
# fs_make_book_folders  (blob split)
# ---------------------------------------------------------------------------

def fs_make_book_folders(
    path: str,
    permitted_roots: list[str],
    audit_log: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Move each loose audio file in *path* into its own named subfolder."""
    src = resolve_safe(path, permitted_roots)
    dry_run = not confirm

    moves: list[dict] = []
    for entry in sorted(src.iterdir()):
        if not entry.is_file() or entry.suffix.lower() not in AUDIO_EXTS:
            continue
        stem = entry.stem
        dest_dir = src / stem
        dest_file = dest_dir / entry.name
        moves.append({"src": str(entry), "dest": str(dest_file)})

    if not dry_run:
        for m in moves:
            s, d = Path(m["src"]), Path(m["dest"])
            d.parent.mkdir(parents=True, exist_ok=True)
            if d.exists():
                m["skipped"] = "destination exists"
                continue
            shutil.move(str(s), str(d))

    log_operation(audit_log, "fs_make_book_folders", dry_run, path=str(src), moves=moves)
    return {"dry_run": dry_run, "moves": moves, "count": len(moves)}


# ---------------------------------------------------------------------------
# fs_flatten  (disc/part folder merge)
# ---------------------------------------------------------------------------

def fs_flatten(
    path: str,
    permitted_roots: list[str],
    audit_log: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Merge disc/CD/part subfolders up into parent, prefixing filenames."""
    src = resolve_safe(path, permitted_roots)
    dry_run = not confirm

    moves: list[dict] = []
    for sub in sorted(src.iterdir()):
        if not sub.is_dir() or sub.is_symlink():
            continue
        prefix = sub.name
        for entry in sorted(sub.rglob("*")):
            if not entry.is_file():
                continue
            rel = entry.relative_to(sub)
            new_name = f"{prefix} - {str(rel).replace(os.sep, ' - ')}"
            dest = src / new_name
            moves.append({"src": str(entry), "dest": str(dest)})

    if not dry_run:
        for m in moves:
            s, d = Path(m["src"]), Path(m["dest"])
            if d.exists():
                m["skipped"] = "destination exists"
                continue
            shutil.move(str(s), str(d))
        # Remove now-empty subdirs
        for sub in sorted(src.iterdir()):
            if sub.is_dir() and not sub.is_symlink() and not any(sub.rglob("*")):
                sub.rmdir()

    log_operation(audit_log, "fs_flatten", dry_run, path=str(src), moves=moves)
    return {"dry_run": dry_run, "moves": moves, "count": len(moves)}


# ---------------------------------------------------------------------------
# fs_move
# ---------------------------------------------------------------------------

def fs_move(
    src: str,
    dest: str,
    permitted_roots: list[str],
    audit_log: str,
    confirm: bool = False,
) -> dict[str, Any]:
    dry_run = not confirm
    s = resolve_safe(src, permitted_roots)
    d = resolve_safe(dest, permitted_roots)

    result: dict[str, Any] = {"dry_run": dry_run, "src": str(s), "dest": str(d)}

    if not dry_run:
        if d.exists():
            result["error"] = "destination exists; move aborted (no overwrite)"
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s), str(d))
            result["ok"] = True

    log_kwargs = {k: v for k, v in result.items() if k != "dry_run"}
    log_operation(audit_log, "fs_move", dry_run, **log_kwargs)
    return result


# ---------------------------------------------------------------------------
# fs_quarantine
# ---------------------------------------------------------------------------

def fs_quarantine(
    path: str,
    permitted_roots: list[str],
    quarantine_dir: str,
    audit_log: str,
    confirm: bool = False,
) -> dict[str, Any]:
    dry_run = not confirm
    # Validate source is inside permitted roots
    s = resolve_safe(path, permitted_roots)
    # Quarantine dir is its own permitted root for the destination
    q = resolve_safe(quarantine_dir, permitted_roots + [quarantine_dir])

    # Preserve relative structure: find which root the file is under
    rel: Path | None = None
    for root in permitted_roots:
        rp = Path(root).resolve(strict=False)
        try:
            rel = s.relative_to(rp)
            break
        except ValueError:
            continue

    dest = q / (rel if rel else s.name)
    result: dict[str, Any] = {"dry_run": dry_run, "src": str(s), "dest": str(dest)}

    if not dry_run:
        if dest.exists():
            result["error"] = "destination exists in quarantine; aborted"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s), str(dest))
            result["ok"] = True

    log_kwargs = {k: v for k, v in result.items() if k != "dry_run"}
    log_operation(audit_log, "fs_quarantine", dry_run, **log_kwargs)
    return result
