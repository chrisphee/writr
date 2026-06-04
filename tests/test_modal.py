"""Behavioral tests for the modal (NORMAL/INSERT) state machine.

ModalEditor wraps a TextBuffer and interprets keys differently per mode. Tests
drive it through its public surface -- handle(key), mode, and the resulting
buffer text/cursor -- never its internals. Pure: no display, no clock, no
hardware. Buffer-level edge cases (clamping, empty lines) are covered in
test_buffer; here we verify mode behaviour and that keys dispatch as expected.
"""

from editor.buffer import TextBuffer
from editor.modal import Mode, ModalEditor, Outcome

ESC = "\x1b"


def test_editor_starts_in_normal_mode():
    editor = ModalEditor(TextBuffer())

    assert editor.mode is Mode.NORMAL


def test_i_enters_insert_mode_without_changing_text():
    editor = ModalEditor(TextBuffer())

    outcome = editor.handle("i")

    assert editor.mode is Mode.INSERT
    assert outcome is Outcome.CHANGED
    assert editor.buffer.text == ""


def test_typing_in_insert_mode_inserts_text():
    editor = ModalEditor(TextBuffer(), mode=Mode.INSERT)

    outcome = editor.handle("h")

    assert outcome is Outcome.TEXT
    assert editor.buffer.text == "h"
    assert editor.buffer.cursor == (0, 1)


def test_enter_in_insert_mode_splits_the_line():
    editor = ModalEditor(TextBuffer(), mode=Mode.INSERT)
    for ch in "hi":
        editor.handle(ch)

    outcome = editor.handle("\n")

    assert outcome is Outcome.TEXT
    assert editor.buffer.lines == ("hi", "")


def test_backspace_in_insert_mode_deletes_backward():
    editor = ModalEditor(TextBuffer(), mode=Mode.INSERT)
    for ch in "hi":
        editor.handle(ch)

    outcome = editor.handle("\b")

    assert outcome is Outcome.TEXT
    assert editor.buffer.text == "h"


def test_escape_returns_to_normal_mode():
    editor = ModalEditor(TextBuffer(), mode=Mode.INSERT)
    editor.handle("h")

    outcome = editor.handle(ESC)

    assert editor.mode is Mode.NORMAL
    assert outcome is Outcome.CHANGED


def test_letters_in_normal_mode_are_commands_not_text():
    editor = ModalEditor(TextBuffer())  # NORMAL

    editor.handle("z")  # unbound -> ignored

    assert editor.buffer.text == ""


def test_hjkl_move_the_cursor():
    editor = ModalEditor(TextBuffer.from_text("hello\nworld"))

    assert editor.handle("l") is Outcome.CHANGED
    assert editor.buffer.cursor == (0, 1)
    editor.handle("j")
    assert editor.buffer.cursor == (1, 1)
    editor.handle("h")
    assert editor.buffer.cursor == (1, 0)
    editor.handle("k")
    assert editor.buffer.cursor == (0, 0)


def test_a_motion_into_a_wall_reports_no_change_so_no_refresh_happens():
    editor = ModalEditor(TextBuffer.from_text("hi"))  # cursor at (0,0)

    assert editor.handle("h") is Outcome.NONE  # nothing to the left
    assert editor.buffer.cursor == (0, 0)


def test_zero_and_dollar_jump_to_line_start_and_end():
    editor = ModalEditor(TextBuffer.from_text("hello"))

    editor.handle("$")
    assert editor.buffer.cursor == (0, 5)
    editor.handle("0")
    assert editor.buffer.cursor == (0, 0)


def test_x_deletes_the_character_under_the_cursor():
    editor = ModalEditor(TextBuffer.from_text("hello"))

    assert editor.handle("x") is Outcome.CHANGED
    assert editor.buffer.text == "ello"


def test_x_on_an_empty_line_reports_no_change():
    editor = ModalEditor(TextBuffer.from_text(""))

    assert editor.handle("x") is Outcome.NONE


def test_dd_deletes_the_current_line():
    editor = ModalEditor(TextBuffer.from_text("one\ntwo"))
    editor.handle("j")  # onto 'two'

    assert editor.handle("d") is Outcome.NONE  # pending
    assert editor.handle("d") is Outcome.CHANGED
    assert editor.buffer.lines == ("one",)


def test_wbe_dispatch_to_word_motions():
    editor = ModalEditor(TextBuffer.from_text("the quick brown"))

    assert editor.handle("w") is Outcome.CHANGED
    assert editor.buffer.cursor == (0, 4)  # 'quick'
    editor.handle("e")
    assert editor.buffer.cursor == (0, 8)  # end of 'quick'
    editor.handle("b")
    assert editor.buffer.cursor == (0, 4)  # back to 'quick' start


def test_capital_g_jumps_to_the_last_line():
    editor = ModalEditor(TextBuffer.from_text("one\ntwo\nthree"))

    assert editor.handle("G") is Outcome.CHANGED
    assert editor.buffer.cursor == (2, 0)


def test_gg_jumps_to_the_first_line():
    editor = ModalEditor(TextBuffer.from_text("one\ntwo\nthree"))
    editor.handle("G")  # at the last line

    assert editor.handle("g") is Outcome.NONE  # first g: pending, nothing shown yet
    assert editor.handle("g") is Outcome.CHANGED
    assert editor.buffer.cursor == (0, 0)


def test_a_dangling_g_does_not_swallow_the_next_command():
    editor = ModalEditor(TextBuffer.from_text("one\ntwo"))

    editor.handle("g")  # pending
    editor.handle("j")  # not 'g' -> cancel pending, run 'j' fresh
    assert editor.buffer.cursor == (1, 0)


def test_a_appends_after_the_cursor_in_insert_mode():
    editor = ModalEditor(TextBuffer.from_text("hi"))  # NORMAL, cursor (0,0)

    assert editor.handle("a") is Outcome.CHANGED
    assert editor.mode is Mode.INSERT
    assert editor.buffer.cursor == (0, 1)
    editor.handle("X")
    assert editor.buffer.text == "hXi"


def test_capital_a_appends_at_end_of_line():
    editor = ModalEditor(TextBuffer.from_text("hi"))

    editor.handle("A")
    assert editor.mode is Mode.INSERT
    assert editor.buffer.cursor == (0, 2)


def test_capital_i_inserts_at_line_start():
    editor = ModalEditor(TextBuffer.from_text("hi"))
    editor.handle("$")  # move to end first

    editor.handle("I")
    assert editor.mode is Mode.INSERT
    assert editor.buffer.cursor == (0, 0)


def test_o_opens_a_line_below_in_insert_mode():
    editor = ModalEditor(TextBuffer.from_text("hello\nworld"))

    editor.handle("o")
    assert editor.mode is Mode.INSERT
    assert editor.buffer.lines == ("hello", "", "world")
    assert editor.buffer.cursor == (1, 0)


def test_capital_o_opens_a_line_above_in_insert_mode():
    editor = ModalEditor(TextBuffer.from_text("hello\nworld"))
    editor.handle("j")  # onto "world"

    editor.handle("O")
    assert editor.mode is Mode.INSERT
    assert editor.buffer.lines == ("hello", "", "world")
    assert editor.buffer.cursor == (1, 0)
