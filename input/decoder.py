"""Stateful decoding of evdev key events into editor characters.

Pure and evdev-free: it consumes (key_name, key_state) pairs and tracks shift
across them, delegating the name->character mapping to the keymap. The evdev
device layer feeds it raw events; the editor loop consumes the characters it
returns.
"""

from input.keymap import key_to_char

_SHIFT_KEYS = frozenset({"KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"})

# evdev key states.
_KEY_UP = 0


class KeyDecoder:
    def __init__(self):
        self._shift = False

    def feed(self, key_name: str, key_state: int) -> str | None:
        """Decode one key event; return a character or None (no text produced)."""
        if key_name in _SHIFT_KEYS:
            self._shift = key_state != _KEY_UP
            return None
        if key_state == _KEY_UP:
            return None
        return key_to_char(key_name, self._shift)
