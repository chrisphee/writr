"""Plain-text editing buffer modelled as a list of logical lines.

The buffer knows nothing about rendering, wrapping, or the display panel.
Word-wrap is purely visual and happens later in the renderer; here a line is a
logical line that only ends at an explicit newline. The cursor is a
``(row, col)`` position measured in those logical-line coordinates.
"""


class TextBuffer:
    def __init__(self):
        self._lines = [""]
        self._row = 0
        self._col = 0

    @classmethod
    def from_text(cls, text: str) -> "TextBuffer":
        """Seed a buffer from text, cursor at the origin (also used to load files)."""
        buffer = cls()
        buffer._lines = text.split("\n")
        return buffer

    @property
    def text(self) -> str:
        return "\n".join(self._lines)

    @property
    def cursor(self) -> tuple[int, int]:
        return (self._row, self._col)

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self._lines)

    # -- cursor motions ---------------------------------------------------------
    # The cursor may rest at column len(line) (just past the last char) so that
    # append/end-of-line editing is uniform. Vertical motion clamps the column to
    # the target line and does not remember a "desired" column (a simplification
    # of vim's behaviour that is fine for prose).

    def move_left(self) -> None:
        if self._col > 0:
            self._col -= 1

    def move_right(self) -> None:
        if self._col < len(self._lines[self._row]):
            self._col += 1

    def move_up(self) -> None:
        if self._row > 0:
            self._row -= 1
            self._col = min(self._col, len(self._lines[self._row]))

    def move_down(self) -> None:
        if self._row < len(self._lines) - 1:
            self._row += 1
            self._col = min(self._col, len(self._lines[self._row]))

    def move_line_start(self) -> None:
        self._col = 0

    def move_line_end(self) -> None:
        self._col = len(self._lines[self._row])

    def _word_spans(self) -> list[tuple[int, int, int]]:
        """All words as (row, start_col, last_col); a word is a run of non-space."""
        spans = []
        for row, line in enumerate(self._lines):
            col = 0
            while col < len(line):
                if line[col].isspace():
                    col += 1
                    continue
                start = col
                while col < len(line) and not line[col].isspace():
                    col += 1
                spans.append((row, start, col - 1))
        return spans

    def _end_of_buffer(self) -> tuple[int, int]:
        last_row = len(self._lines) - 1
        return (last_row, len(self._lines[last_row]))

    def move_word_forward(self) -> None:
        cursor = (self._row, self._col)
        for row, start, _last in self._word_spans():
            if (row, start) > cursor:
                self._row, self._col = row, start
                return
        self._row, self._col = self._end_of_buffer()

    def move_word_end(self) -> None:
        cursor = (self._row, self._col)
        for row, _start, last in self._word_spans():
            if (row, last) > cursor:
                self._row, self._col = row, last
                return
        self._row, self._col = self._end_of_buffer()

    def move_word_back(self) -> None:
        cursor = (self._row, self._col)
        target = (0, 0)
        for row, start, _last in self._word_spans():
            if (row, start) < cursor:
                target = (row, start)
            else:
                break
        self._row, self._col = target

    def move_buffer_start(self) -> None:
        self._row = 0
        self._col = 0

    def move_buffer_end(self) -> None:
        self._row = len(self._lines) - 1
        self._col = 0

    def delete_char(self) -> None:
        """Delete the character under the cursor (vim 'x'); no-op past line end."""
        line = self._lines[self._row]
        if self._col < len(line):
            self._lines[self._row] = line[: self._col] + line[self._col + 1 :]
            self._col = min(self._col, len(self._lines[self._row]))

    def delete_line(self) -> None:
        """Delete the current line (vim 'dd'); the buffer keeps at least one line."""
        del self._lines[self._row]
        if not self._lines:
            self._lines = [""]
        self._row = min(self._row, len(self._lines) - 1)
        self._col = 0

    def open_below(self) -> None:
        """Insert an empty line below the cursor line and move onto it."""
        self._lines.insert(self._row + 1, "")
        self._row += 1
        self._col = 0

    def open_above(self) -> None:
        """Insert an empty line above the cursor line and move onto it."""
        self._lines.insert(self._row, "")
        self._col = 0

    def insert(self, ch: str) -> None:
        line = self._lines[self._row]
        self._lines[self._row] = line[: self._col] + ch + line[self._col :]
        self._col += len(ch)

    def newline(self) -> None:
        line = self._lines[self._row]
        before, after = line[: self._col], line[self._col :]
        self._lines[self._row] = before
        self._lines.insert(self._row + 1, after)
        self._row += 1
        self._col = 0

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def backspace(self) -> None:
        if self._col == 0:
            return
        line = self._lines[self._row]
        self._lines[self._row] = line[: self._col - 1] + line[self._col :]
        self._col -= 1
