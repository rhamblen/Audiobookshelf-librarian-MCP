"""Append-only JSON-lines audit log for every file operation."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_lock = threading.Lock()


def log_operation(
    audit_log_path: str,
    operation: str,
    dry_run: bool,
    **kwargs: Any,
) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "op": operation,
        "dry_run": dry_run,
        **kwargs,
    }
    path = Path(audit_log_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
    except OSError:
        # Never crash the MCP server over a logging failure; silently skip.
        pass
