"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    abs_url: str
    abs_token: str
    library_roots: list[str]
    quarantine_dir: str
    mcp_token: str
    dry_run_default: bool
    port: int
    audit_log: str
    # detect_blobs defaults (overridable per-call)
    blob_hours_threshold: float
    blob_file_count_threshold: int

    @classmethod
    def from_env(cls) -> Config:
        abs_url = os.environ["ABS_URL"].rstrip("/")
        abs_token = os.environ["ABS_TOKEN"]
        roots_raw = os.environ.get("LIBRARY_ROOTS", "")
        library_roots = [r for r in roots_raw.split(":") if r]
        quarantine_dir = os.environ.get("QUARANTINE_DIR", "/quarantine")
        mcp_token = os.environ.get("MCP_TOKEN", "")
        dry_run_default = (
            os.environ.get("DRY_RUN_DEFAULT", "true").lower() not in ("false", "0", "no")
        )
        port = int(os.environ.get("PORT", "8000"))
        audit_log = os.environ.get("AUDIT_LOG", "/audiobooks/.abs-librarian-audit.jsonl")
        blob_hours = float(os.environ.get("BLOB_HOURS_THRESHOLD", "6.0"))
        blob_files = int(os.environ.get("BLOB_FILE_COUNT_THRESHOLD", "10"))
        return cls(
            abs_url=abs_url,
            abs_token=abs_token,
            library_roots=library_roots,
            quarantine_dir=quarantine_dir,
            mcp_token=mcp_token,
            dry_run_default=dry_run_default,
            port=port,
            audit_log=audit_log,
            blob_hours_threshold=blob_hours,
            blob_file_count_threshold=blob_files,
        )
