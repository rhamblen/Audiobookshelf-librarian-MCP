"""Path-jail security tests — most critical unit tests in the project."""

import os
import tempfile
from pathlib import Path

import pytest

from abs_librarian.jail import PathJailError, resolve_safe


@pytest.fixture()
def tmp_root(tmp_path):
    lib = tmp_path / "audiobooks"
    lib.mkdir()
    return lib


def test_path_inside_root_accepted(tmp_root):
    book = tmp_root / "mybook"
    book.mkdir()
    result = resolve_safe(str(book), [str(tmp_root)])
    assert result == book.resolve()


def test_path_outside_root_rejected(tmp_root, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(PathJailError):
        resolve_safe(str(other), [str(tmp_root)])


def test_dotdot_traversal_rejected(tmp_root):
    evil = str(tmp_root / ".." / "etc" / "passwd")
    with pytest.raises(PathJailError):
        resolve_safe(evil, [str(tmp_root)])


def test_absolute_path_outside_rejected(tmp_root):
    with pytest.raises(PathJailError):
        resolve_safe("/etc/passwd", [str(tmp_root)])


def test_multiple_roots_first_match(tmp_path):
    root1 = tmp_path / "lib1"
    root2 = tmp_path / "lib2"
    root1.mkdir()
    root2.mkdir()
    book = root2 / "book"
    book.mkdir()
    result = resolve_safe(str(book), [str(root1), str(root2)])
    assert result == book.resolve()


def test_symlink_outside_jail_rejected(tmp_root, tmp_path):
    outside = tmp_path / "secret"
    outside.mkdir()
    link = tmp_root / "evil_link"
    link.symlink_to(outside)
    with pytest.raises(PathJailError):
        resolve_safe(str(link / "data"), [str(tmp_root)])
