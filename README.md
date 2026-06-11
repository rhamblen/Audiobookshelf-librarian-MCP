# Audiobookshelf Librarian MCP

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant fully manage a self-hosted [Audiobookshelf](https://www.audiobookshelf.org/) library — including the file-system fixes the ABS API cannot do.

## Features

| Category | Tools |
|---|---|
| **Library info** | `library_overview`, `find_items`, `get_item` |
| **Metadata** | `batch_update_metadata`, `quick_match`, `set_cover` |
| **Maintenance** | `scan_library`, `list_missing`, `purge_missing`, `create_backup` |
| **File system** | `fs_tree`, `detect_blobs`, `fs_make_book_folders`, `fs_flatten`, `fs_move`, `fs_quarantine` |

### What makes this different

Existing ABS MCPs only wrap the read/manage API. This server also ships **file-system tools**:

- **`fs_make_book_folders`** — splits "blob" folders (many books scanned as one) by moving each audio file into its own named subfolder.
- **`fs_flatten`** — merges per-disc/CD/part subfolders up into the parent with prefixed filenames.
- **`fs_quarantine`** — moves duplicates or unwanted files to a quarantine folder. Nothing is ever deleted.

## Safety model

- **Move-only / no delete**: quarantine instead of delete everywhere.
- **Dry-run by default**: every file tool returns a plan unless you pass `confirm=true`.
- **Path jail**: all paths are validated against configured library roots; `..` traversal, symlinks that exit the jail, and absolute paths outside roots are rejected and logged.
- **Audit log**: every file operation is appended to a JSON-lines file inside your library mount.
- **Dedicated ABS token**: never your login credentials.

## Quick start

### docker run

```bash
docker run -d \
  --name abs-librarian-mcp \
  -p 8000:8000 \
  -v /mnt/user/audiobooks:/audiobooks:rw \
  -v /mnt/user/quarantine:/quarantine:rw \
  -e ABS_URL=http://192.168.1.100:13378 \
  -e ABS_TOKEN=your-abs-token \
  -e LIBRARY_ROOTS=/audiobooks \
  -e QUARANTINE_DIR=/quarantine \
  -e MCP_TOKEN=your-long-random-secret \
  ghcr.io/rhamblen/audiobookshelf-librarian-mcp:latest
```

### docker compose

Copy `.env.example` to `.env`, fill in your values, then:

```bash
docker compose up -d
```

### Unraid

Import `unraid-template.xml` via Community Applications → "Add Container from XML", or add the GitHub URL to your template repositories.

## Claude connector setup

In Claude Desktop (`claude_desktop_config.json`) or the Claude web app (Settings → Connectors):

```json
{
  "mcpServers": {
    "abs-librarian": {
      "url": "http://YOUR-SERVER-IP:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

Replace `YOUR-SERVER-IP` and `YOUR_MCP_TOKEN` with your values.

## Configuration (environment variables)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ABS_URL` | ✅ | — | Audiobookshelf base URL |
| `ABS_TOKEN` | ✅ | — | ABS API token |
| `LIBRARY_ROOTS` | ✅ | — | Colon-separated container paths for the library |
| `QUARANTINE_DIR` | ✅ | `/quarantine` | Where unwanted files are moved |
| `MCP_TOKEN` | ✅ | — | Bearer token for Claude to authenticate |
| `DRY_RUN_DEFAULT` | — | `true` | File tools default to dry-run |
| `PORT` | — | `8000` | Server listen port |
| `AUDIT_LOG` | — | `/audiobooks/.abs-librarian-audit.jsonl` | Audit log path |
| `BLOB_HOURS_THRESHOLD` | — | `6.0` | `detect_blobs` hours threshold (overridable per-call) |
| `BLOB_FILE_COUNT_THRESHOLD` | — | `10` | `detect_blobs` file-count threshold (overridable per-call) |

## Tool reference

### `library_overview`
Returns counts per library: items, authors, series, no-cover, no-series, missing.

### `find_items(library_id, ...)`
Filtered search. Filters: `title_regex`, `author`, `series`, `no_cover`, `no_series`, `missing`, `min/max_duration_hours`, `min/max_file_count`. Returns compact results (limit 200 default).

### `get_item(item_id)`
Full detail for one item including file list.

### `batch_update_metadata(library_id, updates)`
Bulk metadata update. Each update: `{id, title?, authors?, narrators?, series?, genres?, tags?}`. Series names are auto-resolved to existing series IDs to avoid duplicates.

### `quick_match(item_ids, provider?, override_cover?, override_details?)`
Batch quick-match against Audible (default) or another provider.

### `set_cover(item_id, url? | search_title?, search_author?, provider?)`
Set a cover from a URL or from a provider cover search.

### `scan_library(library_id)`
Trigger an ABS library scan.

### `list_missing(library_id)` / `purge_missing(library_id, confirm?)`
List or delete ABS records for missing items (files already gone; does not touch disk).

### `create_backup()`
Trigger an ABS backup.

### `fs_tree(path, max_depth?)`
Folder tree with audio-file counts and sizes (depth-limited, default 3).

### `detect_blobs(path, hours_threshold?, file_count_threshold?)`
Heuristic scan: flags items above the hour or file-count threshold and notes which have disc subfolders.

### `fs_make_book_folders(path, confirm?)`
Splits a blob folder: each loose audio file → own named subfolder. Dry-run unless `confirm=true`.

### `fs_flatten(path, confirm?)`
Merges disc/CD/part subfolders into the parent with prefixed filenames. Dry-run unless `confirm=true`.

### `fs_move(src, dest, confirm?)`
Moves a file or folder within the library. No overwrite. Dry-run unless `confirm=true`.

### `fs_quarantine(path, confirm?)`
Moves a file or folder to quarantine, preserving relative structure. Dry-run unless `confirm=true`.

## Example prompts

```
Show me a library overview.

Find all items with no series assigned in library lib_abc123.

Batch-update genres for these 50 items to ["Science Fiction"]: [...]

Show me the folder tree at /audiobooks/Author Name — depth 2.

Detect blobs under /audiobooks with more than 8 hours estimated runtime.

Split the blob at /audiobooks/Author Name/Big Omnibus — dry run first, then confirm.

Flatten the disc folders in /audiobooks/Author Name/Series Book 1 — dry run.

Quarantine /audiobooks/Author Name/Series Book 1 (mp3 copy) — confirm.
```

## Development

```bash
git clone https://github.com/rhamblen/Audiobookshelf-librarian-MCP
cd Audiobookshelf-librarian-MCP
pip install -e ".[dev]"
cp .env.example .env   # fill in your values
python -m abs_librarian

# Tests
pytest
```

## License

MIT © Richard Hamblen
