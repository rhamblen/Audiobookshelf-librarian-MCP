"""Tests for metadata payload builder and series cache."""

from abs_librarian.metadata import SeriesCache, build_metadata_payload


def test_build_metadata_only_supplied_fields():
    payload = build_metadata_payload(title="Dune", genres=["Sci-Fi"])
    assert payload == {"title": "Dune", "genres": ["Sci-Fi"]}
    assert "authors" not in payload
    assert "series" not in payload


def test_build_metadata_authors_as_strings():
    payload = build_metadata_payload(authors=["Frank Herbert"])
    assert payload["authors"] == [{"name": "Frank Herbert"}]


def test_series_cache_resolves_by_id():
    cache = SeriesCache()
    cache.seed([{"name": "Dune Chronicles", "id": "abc123"}])
    result = cache.resolve("Dune Chronicles", "1")
    assert result == {"id": "abc123", "sequence": "1"}


def test_series_cache_falls_back_to_name():
    cache = SeriesCache()
    result = cache.resolve("New Series", "2")
    assert result == {"name": "New Series", "sequence": "2"}


def test_series_cache_case_insensitive():
    cache = SeriesCache()
    cache.seed([{"name": "The Expanse", "id": "xyz"}])
    result = cache.resolve("the expanse", "3")
    assert result["id"] == "xyz"


def test_series_cache_add():
    cache = SeriesCache()
    cache.add("Brand New Series", "newid")
    assert cache.resolve("Brand New Series")["id"] == "newid"
