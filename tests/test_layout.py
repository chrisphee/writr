"""Behavioral tests for pure text layout: word-wrap and viewport scrolling.

Layout is the part of rendering that has no pixels in it -- given logical lines,
a cursor, and a character grid size, it decides which visual rows are shown and
where the cursor lands. Keeping it pure means the wrap/scroll behaviour is tested
anywhere, and the PIL renderer is left to do nothing but paint these rows.
"""

from editor.layout import cursor_view, wrap_line


def test_a_line_shorter_than_the_width_is_a_single_row():
    assert wrap_line("hello", width=10) == ["hello"]


def test_an_empty_line_still_occupies_one_row():
    assert wrap_line("", width=10) == [""]


def test_a_long_line_wraps_on_word_boundaries():
    assert wrap_line("the quick brown fox", width=10) == ["the quick", "brown fox"]


def test_a_word_longer_than_the_width_is_hard_broken():
    assert wrap_line("supercalifragilistic", width=10) == ["supercalif", "ragilistic"]


def test_no_visual_row_exceeds_the_width():
    rows = wrap_line("alpha beta gamma delta epsilon", width=12)
    assert all(len(row) <= 12 for row in rows)


def test_cursor_view_shows_all_rows_and_locates_the_cursor():
    rows, cur_row, cur_col = cursor_view(["hello", "world"], (1, 3), width=10, height=8)

    assert rows == ["hello", "world"]
    assert (cur_row, cur_col) == (1, 3)


def test_cursor_view_scrolls_to_keep_the_cursor_visible_at_the_bottom():
    lines = ["l0", "l1", "l2", "l3", "l4"]

    rows, cur_row, cur_col = cursor_view(lines, (4, 1), width=10, height=3)

    assert rows == ["l2", "l3", "l4"]
    assert cur_row == 2  # pinned to the bottom visible row
    assert cur_col == 1


def test_cursor_view_follows_the_cursor_up_to_the_top():
    lines = ["l0", "l1", "l2", "l3", "l4"]

    rows, cur_row, cur_col = cursor_view(lines, (0, 0), width=10, height=3)

    assert rows == ["l0", "l1", "l2"]
    assert (cur_row, cur_col) == (0, 0)


def test_cursor_view_counts_wrapped_rows_and_maps_the_cursor_into_them():
    # "aaaa bbbb cccc" wraps to 3 rows at width 4; cursor at end of the line.
    rows, cur_row, cur_col = cursor_view(["aaaa bbbb cccc"], (0, 14), width=4, height=10)

    assert rows == ["aaaa", "bbbb", "cccc"]
    assert cur_row == 2  # third visual row
    assert cur_col == 4  # just past 'cccc'
