"""Behavioral tests for draft storage.

Data loss is the cardinal sin for a writing machine, so saves are atomic
(write a temp file, fsync, rename) -- a power cut mid-save can never leave a
half-written or empty draft. These tests use a real temp directory; they need
no PIL and no hardware.
"""

import os
from pathlib import Path

from drafts import DraftStore


def test_save_then_load_round_trips(tmp_path):
    store = DraftStore(tmp_path)
    path = store.new_path("2026-06-04-2153")

    store.save(path, "hello\nworld")

    assert store.load(path) == "hello\nworld"


def test_save_leaves_no_temp_file_behind(tmp_path):
    store = DraftStore(tmp_path)
    path = store.new_path("draft")

    store.save(path, "content")

    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["draft.md"]  # the temp file was renamed away, nothing dangling


def test_new_path_uses_the_timestamp_and_configured_extension(tmp_path):
    store = DraftStore(tmp_path, extension=".md")

    path = store.new_path("2026-06-04-2153")

    assert path.name == "2026-06-04-2153.md"
    assert path.parent == Path(tmp_path)


def test_list_returns_drafts_most_recently_modified_first(tmp_path):
    store = DraftStore(tmp_path)
    older = store.new_path("older")
    newer = store.new_path("newer")
    store.save(older, "o")
    store.save(newer, "n")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    assert store.list() == [newer, older]


def test_list_ignores_non_text_files(tmp_path):
    store = DraftStore(tmp_path)
    (tmp_path / "note.md").write_text("hi")
    (tmp_path / "essay.txt").write_text("yo")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG")

    assert {p.name for p in store.list()} == {"note.md", "essay.txt"}


def test_list_is_empty_when_the_directory_does_not_exist(tmp_path):
    store = DraftStore(tmp_path / "nope")

    assert store.list() == []
