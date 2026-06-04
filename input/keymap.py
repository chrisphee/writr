"""Translate evdev keycode names into editor characters.

Pure and evdev-free: it works on the *name* strings evdev produces (e.g.
"KEY_A"). The evdev input layer is responsible for turning raw events into these
names and tracking shift; this module only does name + shift -> character.
"""

_LETTERS = {f"KEY_{c.upper()}": c for c in "abcdefghijklmnopqrstuvwxyz"}

# US-layout keys whose character depends on shift: (unshifted, shifted).
_SHIFTED = {
    "KEY_1": ("1", "!"),
    "KEY_2": ("2", "@"),
    "KEY_3": ("3", "#"),
    "KEY_4": ("4", "$"),
    "KEY_5": ("5", "%"),
    "KEY_6": ("6", "^"),
    "KEY_7": ("7", "&"),
    "KEY_8": ("8", "*"),
    "KEY_9": ("9", "("),
    "KEY_0": ("0", ")"),
    "KEY_MINUS": ("-", "_"),
    "KEY_EQUAL": ("=", "+"),
    "KEY_LEFTBRACE": ("[", "{"),
    "KEY_RIGHTBRACE": ("]", "}"),
    "KEY_BACKSLASH": ("\\", "|"),
    "KEY_SEMICOLON": (";", ":"),
    "KEY_APOSTROPHE": ("'", '"'),
    "KEY_GRAVE": ("`", "~"),
    "KEY_COMMA": (",", "<"),
    "KEY_DOT": (".", ">"),
    "KEY_SLASH": ("/", "?"),
}

# Control keys the editor loop understands, as the characters it dispatches on.
_CONTROL = {
    "KEY_SPACE": " ",
    "KEY_ENTER": "\n",
    "KEY_KPENTER": "\n",
    "KEY_BACKSPACE": "\b",
    "KEY_TAB": "\t",
    "KEY_ESC": "\x1b",
}


def key_to_char(key: str, shift: bool) -> str | None:
    """Return the character a key produces, or None if it yields no text."""
    if key in _LETTERS:
        ch = _LETTERS[key]
        return ch.upper() if shift else ch
    if key in _SHIFTED:
        unshifted, shifted = _SHIFTED[key]
        return shifted if shift else unshifted
    if key in _CONTROL:
        return _CONTROL[key]
    return None
