"""Path-jail enforcement — security-critical module.

Every file path used by fs_* tools must pass through resolve_safe() before use.
Rules:
  - Must resolve to a real path (no traversal via ..)
  - Must not be or pass through a symlink that exits the jail
  - Must sit under at least one configured library root OR the quarantine dir
"""

from __future__ import annotations

from pathlib import Path


class PathJailError(ValueError):
    """Raised when a path falls outside all permitted roots."""


def resolve_safe(raw: str, permitted_roots: list[str]) -> Path:
    """Return the resolved absolute Path of *raw* if it is inside a permitted root.

    Raises PathJailError otherwise.  Never follows symlinks outside the jail.
    """
    try:
        # strict=False so the path need not exist yet (e.g. destination of a move)
        candidate = Path(raw).resolve(strict=False)
    except (OSError, ValueError) as exc:
        raise PathJailError(f"Cannot resolve path {raw!r}: {exc}") from exc

    # Reject if any existing prefix is a symlink pointing outside a root
    _check_no_escaping_symlinks(candidate, permitted_roots)

    for root in permitted_roots:
        try:
            resolved_root = Path(root).resolve(strict=False)
        except (OSError, ValueError):
            continue
        try:
            candidate.relative_to(resolved_root)
            return candidate
        except ValueError:
            continue

    raise PathJailError(
        f"Path {raw!r} (resolved: {candidate}) is outside all permitted roots: {permitted_roots}"
    )


def _check_no_escaping_symlinks(path: Path, permitted_roots: list[str]) -> None:
    """Walk path components; if any existing part is a symlink, verify it resolves inside a root."""
    parts = list(path.parts)
    for i in range(1, len(parts) + 1):
        partial = Path(*parts[:i])
        if partial.is_symlink():
            real = partial.resolve(strict=False)
            inside = any(
                _is_inside(real, Path(r).resolve(strict=False)) for r in permitted_roots
            )
            if not inside:
                raise PathJailError(
                    f"Symlink {partial} points outside permitted roots (resolves to {real})"
                )


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
