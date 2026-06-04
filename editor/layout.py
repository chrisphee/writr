"""Pure text layout for the editor view: word-wrap, scrolling, cursor mapping.

No PIL, no panel knowledge -- just turning logical lines + cursor + a character
grid into the visual rows that appear on screen and where the cursor sits among
them. The renderer paints what this module decides.
"""


def _wrap_offsets(text: str, width: int) -> list[tuple[str, int]]:
    """Greedy word-wrap to ``width``, returning (row_text, source_start) pairs.

    Breaks at the last space that fits; a word longer than ``width`` is
    hard-broken. The source_start lets callers map a logical column back to the
    visual row/column it lands on. The single space at a soft break is dropped.
    """
    if text == "":
        return [("", 0)]

    rows: list[tuple[str, int]] = []
    i, n = 0, len(text)
    while i < n:
        if n - i <= width:
            rows.append((text[i:], i))
            break
        break_at = text.rfind(" ", i + 1, i + width + 1)
        if break_at == -1:  # no space to break on -> hard break
            rows.append((text[i : i + width], i))
            i += width
        else:
            rows.append((text[i:break_at], i))
            i = break_at + 1  # skip the breaking space
    return rows


def wrap_line(text: str, width: int) -> list[str]:
    """Wrap one logical line to ``width`` columns, returning >=1 visual rows."""
    return [row for row, _start in _wrap_offsets(text, width)]


def _locate(wrapped: list[tuple[str, int]], col: int) -> tuple[int, int]:
    """Map a logical column to (visual_row_index, column_within_row)."""
    for index, (row, start) in enumerate(wrapped):
        if start <= col <= start + len(row):
            return index, col - start
    last = len(wrapped) - 1
    return last, len(wrapped[last][0])


def cursor_view(lines, cursor, width: int, height: int):
    """Return (visible_rows, cursor_row, cursor_col) for the panel.

    Every logical line is wrapped; the window of ``height`` visual rows is chosen
    so the cursor's row is always visible, pinned to the bottom as text grows
    (typewriter feel) and following the cursor up when it moves back.
    """
    cur_row, cur_col = cursor
    visual_rows: list[str] = []
    cursor_visual_row = 0
    cursor_visual_col = 0

    for row_index, line in enumerate(lines):
        wrapped = _wrap_offsets(line, width)
        if row_index == cur_row:
            sub_row, col_in_row = _locate(wrapped, cur_col)
            cursor_visual_row = len(visual_rows) + sub_row
            cursor_visual_col = col_in_row
        visual_rows.extend(row for row, _start in wrapped)

    top = max(0, cursor_visual_row - height + 1)
    visible = visual_rows[top : top + height]
    return visible, cursor_visual_row - top, cursor_visual_col
