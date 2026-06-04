"""Behavioral tests for evdev key-event decoding (shift state + key states).

The decoder is the testable core of input handling: it turns a stream of
(key_name, key_state) events -- the shape evdev gives us -- into editor
characters, tracking shift across events. It imports no evdev, so it runs
anywhere; the actual device I/O (discovery, reconnect, select-with-timeout) is
thin glue around it and is verified on hardware.

evdev key states: 0 = key up, 1 = key down, 2 = autorepeat.
"""

from input.decoder import KeyDecoder


def test_a_keydown_yields_a_character_and_keyup_yields_nothing():
    decoder = KeyDecoder()

    assert decoder.feed("KEY_A", 1) == "a"
    assert decoder.feed("KEY_A", 0) is None


def test_shift_is_held_across_events():
    decoder = KeyDecoder()

    assert decoder.feed("KEY_LEFTSHIFT", 1) is None  # modifier press -> no char
    assert decoder.feed("KEY_A", 1) == "A"  # shifted
    assert decoder.feed("KEY_LEFTSHIFT", 0) is None  # release shift
    assert decoder.feed("KEY_A", 1) == "a"  # back to lowercase


def test_autorepeat_still_produces_characters():
    decoder = KeyDecoder()

    assert decoder.feed("KEY_A", 1) == "a"  # initial press
    assert decoder.feed("KEY_A", 2) == "a"  # held down -> repeats
