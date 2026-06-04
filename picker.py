"""Launch file picker: choose a draft to open, or start a new one.

Selection logic only -- it owns the list, the highlighted entry, and how keys
move/commit it. It renders into the same Frame the editor uses (a marked list
with the cursor on the selected row), so the existing renderer draws it. The
driver loop that feeds it keys is thin glue in main.
"""

from editor.frame import Frame


class FilePicker:
    NEW = object()  # sentinel entry meaning "start a new draft"

    def __init__(self, values, label=str):
        self._entries = list(values) + [self.NEW]
        self._label = label
        self._index = 0

    @property
    def current(self):
        return self._entries[self._index]

    def handle(self, key: str) -> str:
        """Return 'chosen' (committed), 'moved' (selection changed), or 'none'."""
        if key == "\n":
            return "chosen"
        if key == "n":
            self._index = len(self._entries) - 1  # the NEW entry
            return "chosen"
        if key == "j":
            return self._move(1)
        if key == "k":
            return self._move(-1)
        return "none"

    def _move(self, delta: int) -> str:
        new_index = max(0, min(self._index + delta, len(self._entries) - 1))
        if new_index == self._index:
            return "none"
        self._index = new_index
        return "moved"

    def frame(self) -> Frame:
        lines = []
        for i, entry in enumerate(self._entries):
            text = "[ new draft ]" if entry is self.NEW else self._label(entry)
            lines.append(("> " if i == self._index else "  ") + text)
        return Frame(
            lines=tuple(lines),
            cursor=(self._index, 0),
            status="select a draft   j/k move · enter open · n new",
        )
