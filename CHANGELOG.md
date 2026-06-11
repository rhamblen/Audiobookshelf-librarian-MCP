# Changelog

## [0.2.6] - 2026-06-12

### Fixed
- `set_cover` no longer crashes when ABS search_covers returns a list of URL strings instead of dicts

## [0.2.5] - 2026-06-12

### Fixed
- `scan_library` and `quick_match` no longer crash on non-JSON ABS responses (all HTTP methods now use try/except around `.json()`)
- `tool_fs_move` and `tool_fs_quarantine` no longer crash with duplicate `dry_run` kwarg in `log_operation` call
- `tool_fs_tree` no longer returns oversized responses — audio file lists suppressed at all depths (counts still shown)

## [0.2.4] - 2026-06-12

### Fixed
- `list_missing` and `purge_missing` now correctly filter missing items by base64-encoding the ABS filter parameter (`issues.missing`)

## [0.2.3] - 2026-06-12

### Fixed
- `find_items` and `library_overview` now return authors and series correctly by passing `include=authors,series` to the ABS library items endpoint

## [Unreleased]

### Added
- Initial release: all v1 tools from the project brief
- ABS API tools: `library_overview`, `find_items`, `get_item`, `batch_update_metadata`, `quick_match`, `set_cover`, `scan_library`, `list_missing`, `purge_missing`, `create_backup`
- File-system tools: `fs_tree`, `detect_blobs`, `fs_make_book_folders`, `fs_flatten`, `fs_move`, `fs_quarantine`
- Path jail, audit log, dry-run-by-default safety model
- Docker image with GHCR CI/CD; Unraid community-apps template
