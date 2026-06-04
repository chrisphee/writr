"""Behavioral tests for the launch file picker (selection logic only).

The picker shows drafts most-recent-first plus a "new draft" entry, navigated
with j/k and committed with Enter (or 'n' for a fresh draft). This is the pure
logic; the driver loop that reads keys and renders it is thin glue. Values can be
anything (Paths in production, strings here); a label function renders them.
"""

from editor.frame import Frame
from picker import FilePicker


def test_most_recent_draft_is_selected_first():
    picker = FilePicker(["newest.md", "older.md"])

    assert picker.current == "newest.md"


def test_j_and_k_navigate_and_clamp_at_the_ends():
    picker = FilePicker(["a.md", "b.md"])  # entries: a.md, b.md, [new]

    assert picker.handle("j") == "moved"
    assert picker.current == "b.md"
    assert picker.handle("j") == "moved"
    assert picker.current is FilePicker.NEW
    assert picker.handle("j") == "none"  # clamped at the bottom

    picker.handle("k")
    picker.handle("k")
    assert picker.current == "a.md"
    assert picker.handle("k") == "none"  # clamped at the top


def test_enter_commits_the_highlighted_entry():
    picker = FilePicker(["a.md", "b.md"])
    picker.handle("j")  # highlight b.md

    assert picker.handle("\n") == "chosen"
    assert picker.current == "b.md"


def test_n_commits_a_new_draft_from_anywhere():
    picker = FilePicker(["a.md"])

    assert picker.handle("n") == "chosen"
    assert picker.current is FilePicker.NEW


def test_empty_directory_offers_only_the_new_draft_option():
    picker = FilePicker([])

    assert picker.current is FilePicker.NEW
    assert picker.handle("\n") == "chosen"
    assert picker.current is FilePicker.NEW


def test_frame_marks_the_selected_row_and_lists_the_new_option():
    picker = FilePicker(["a.md"], label=lambda v: v)

    frame = picker.frame()

    assert isinstance(frame, Frame)
    assert frame.lines[0].startswith(">")  # selected draft marked
    assert "new draft" in frame.lines[-1]  # the new-draft entry
    assert frame.cursor == (0, 0)  # cursor on the selected row
