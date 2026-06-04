"""Behavioral tests for evdev key-name -> character translation.

The keymap is a pure function over evdev keycode *names* (the strings evdev's
``categorize().keycode`` yields, e.g. "KEY_A") plus the current shift state. It
deliberately does not import evdev, so it runs anywhere. Printable keys map to
their character; Enter/Space/Backspace map to control characters the editor loop
understands ("\\n", " ", "\\b"); pure modifiers and unmapped keys map to None.
"""

from input.keymap import key_to_char


def test_letters_respect_shift_state():
    assert key_to_char("KEY_A", shift=False) == "a"
    assert key_to_char("KEY_A", shift=True) == "A"


def test_space_enter_and_backspace_map_to_editor_control_characters():
    assert key_to_char("KEY_SPACE", shift=False) == " "
    assert key_to_char("KEY_ENTER", shift=False) == "\n"
    assert key_to_char("KEY_BACKSPACE", shift=False) == "\b"


def test_escape_maps_to_the_escape_character():
    assert key_to_char("KEY_ESC", shift=False) == "\x1b"


def test_modifier_and_unmapped_keys_produce_no_text():
    assert key_to_char("KEY_LEFTSHIFT", shift=False) is None
    assert key_to_char("KEY_LEFTCTRL", shift=False) is None
    assert key_to_char("KEY_F1", shift=False) is None


def test_digits_and_their_shifted_symbols():
    assert key_to_char("KEY_1", shift=False) == "1"
    assert key_to_char("KEY_1", shift=True) == "!"
    assert key_to_char("KEY_2", shift=True) == "@"
    assert key_to_char("KEY_0", shift=True) == ")"


def test_common_punctuation_with_and_without_shift():
    assert key_to_char("KEY_COMMA", shift=False) == ","
    assert key_to_char("KEY_COMMA", shift=True) == "<"
    assert key_to_char("KEY_DOT", shift=False) == "."
    assert key_to_char("KEY_APOSTROPHE", shift=False) == "'"
    assert key_to_char("KEY_APOSTROPHE", shift=True) == '"'
    assert key_to_char("KEY_MINUS", shift=True) == "_"
