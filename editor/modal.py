"""Modal (vim-style) state machine over a TextBuffer.

Owns the current editing mode and interprets each key accordingly: in INSERT,
keys are text; in NORMAL, keys are motion/edit commands. It mutates the buffer
and reports an Outcome so the event loop knows how to refresh -- TEXT means
"INSERT typing, let the debounce policy decide", CHANGED means "act now"
(NORMAL command or mode switch), NONE means the key did nothing.

The editor launches in NORMAL, like vim.
"""

from enum import Enum

ESC = "\x1b"


class Mode(Enum):
    NORMAL = "NORMAL"
    INSERT = "INSERT"


class Outcome(Enum):
    TEXT = "text"  # a character typed in INSERT mode (subject to debounce)
    CHANGED = "changed"  # a NORMAL command or mode switch (refresh immediately)
    NONE = "none"  # key had no effect


class ModalEditor:
    def __init__(self, buffer, mode: Mode = Mode.NORMAL):
        self._buffer = buffer
        self._mode = mode
        self._pending = None  # first key of a two-key command (e.g. 'g' of 'gg')

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def buffer(self):
        return self._buffer

    def handle(self, key: str) -> Outcome:
        if self._mode is Mode.INSERT:
            return self._handle_insert(key)
        return self._handle_normal(key)

    def _handle_insert(self, key: str) -> Outcome:
        if key == ESC:
            self._mode = Mode.NORMAL
            return Outcome.CHANGED
        if key == "\n":
            self._buffer.newline()
        elif key == "\b":
            self._buffer.backspace()
        else:
            self._buffer.insert(key)
        return Outcome.TEXT

    def _handle_normal(self, key: str) -> Outcome:
        if self._pending is not None:
            prefix, self._pending = self._pending, None
            compound = _COMPOUND_COMMANDS.get((prefix, key))
            if compound is not None:
                return self._run(compound)
            # Not a valid pair -- don't swallow the key; run it on its own.
            return self._handle_normal(key)

        if key in _PREFIX_KEYS:
            self._pending = key
            return Outcome.NONE  # wait for the second key; nothing to show yet

        command = _NORMAL_COMMANDS.get(key)
        if command is None:
            return Outcome.NONE
        return self._run(command)

    def _run(self, command) -> Outcome:
        # Report CHANGED only if something actually moved or changed -- a motion
        # into a wall must not trigger a wasted e-paper refresh.
        before = self._snapshot()
        command(self)
        return Outcome.CHANGED if self._snapshot() != before else Outcome.NONE

    def _snapshot(self):
        return (self._mode, self._buffer.cursor, self._buffer.text)

    def _enter_insert(self) -> None:
        self._mode = Mode.INSERT

    def _append(self) -> None:
        self._buffer.move_right()
        self._mode = Mode.INSERT

    def _append_line_end(self) -> None:
        self._buffer.move_line_end()
        self._mode = Mode.INSERT

    def _insert_line_start(self) -> None:
        self._buffer.move_line_start()
        self._mode = Mode.INSERT

    def _open_below(self) -> None:
        self._buffer.open_below()
        self._mode = Mode.INSERT

    def _open_above(self) -> None:
        self._buffer.open_above()
        self._mode = Mode.INSERT


# NORMAL-mode command table: key -> method on ModalEditor. Each either moves the
# cursor (via the buffer) or switches mode; change detection lives in the caller.
_NORMAL_COMMANDS = {
    "i": ModalEditor._enter_insert,
    "a": ModalEditor._append,
    "A": ModalEditor._append_line_end,
    "I": ModalEditor._insert_line_start,
    "o": ModalEditor._open_below,
    "O": ModalEditor._open_above,
    "h": lambda e: e._buffer.move_left(),
    "l": lambda e: e._buffer.move_right(),
    "k": lambda e: e._buffer.move_up(),
    "j": lambda e: e._buffer.move_down(),
    "0": lambda e: e._buffer.move_line_start(),
    "$": lambda e: e._buffer.move_line_end(),
    "G": lambda e: e._buffer.move_buffer_end(),
    "w": lambda e: e._buffer.move_word_forward(),
    "b": lambda e: e._buffer.move_word_back(),
    "e": lambda e: e._buffer.move_word_end(),
    "x": lambda e: e._buffer.delete_char(),
}

# Keys that begin a two-key command; the next key is interpreted against the pair.
_PREFIX_KEYS = frozenset({"g", "d"})

_COMPOUND_COMMANDS = {
    ("g", "g"): lambda e: e._buffer.move_buffer_start(),
    ("d", "d"): lambda e: e._buffer.delete_line(),
}
