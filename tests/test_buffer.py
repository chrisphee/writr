"""Behavioral tests for the editor text buffer.

These exercise TextBuffer purely through its public interface (no internals),
so they survive any change to how text is stored. Dependency-free: runs under
both pytest and `python -m unittest`.
"""

from editor.buffer import TextBuffer


def test_typing_a_character_puts_it_in_the_text_and_advances_the_cursor():
    buffer = TextBuffer()

    buffer.insert("h")

    assert buffer.text == "h"
    assert buffer.cursor == (0, 1)


def test_characters_accumulate_and_backspace_deletes_the_one_before_the_cursor():
    buffer = TextBuffer()

    for ch in "helo":
        buffer.insert(ch)
    assert buffer.text == "helo"

    buffer.backspace()

    assert buffer.text == "hel"
    assert buffer.cursor == (0, 3)


def test_from_text_seeds_lines_with_the_cursor_at_the_origin():
    buffer = TextBuffer.from_text("hello\nworld")

    assert buffer.lines == ("hello", "world")
    assert buffer.cursor == (0, 0)


def test_move_right_and_left_clamp_within_the_line():
    buffer = TextBuffer.from_text("hi")

    buffer.move_right()
    buffer.move_right()
    assert buffer.cursor == (0, 2)  # may rest just past the last char
    buffer.move_right()
    assert buffer.cursor == (0, 2)  # clamped at line end

    buffer.move_left()
    buffer.move_left()
    buffer.move_left()
    assert buffer.cursor == (0, 0)  # clamped at column 0


def test_vertical_motion_clamps_column_to_the_target_line_length():
    buffer = TextBuffer.from_text("hello\nhi")
    buffer.move_right()
    buffer.move_right()
    buffer.move_right()  # column 3 on "hello"

    buffer.move_down()
    assert buffer.cursor == (1, 2)  # "hi" is only length 2


def test_vertical_motion_clamps_at_the_first_and_last_line():
    buffer = TextBuffer.from_text("a\nb")

    buffer.move_up()
    assert buffer.cursor == (0, 0)  # already at the top

    buffer.move_down()
    buffer.move_down()
    assert buffer.cursor == (1, 0)  # clamped at the last line


def test_line_start_and_line_end_motions():
    buffer = TextBuffer.from_text("hello")

    buffer.move_line_end()
    assert buffer.cursor == (0, 5)
    buffer.move_line_start()
    assert buffer.cursor == (0, 0)


def test_move_buffer_start_and_end_go_to_first_and_last_line():
    buffer = TextBuffer.from_text("one\ntwo\nthree")

    buffer.move_buffer_end()
    assert buffer.cursor == (2, 0)
    buffer.move_buffer_start()
    assert buffer.cursor == (0, 0)


def test_word_forward_moves_to_next_word_start_crossing_lines():
    buffer = TextBuffer.from_text("the quick\nbrown")

    buffer.move_word_forward()
    assert buffer.cursor == (0, 4)  # 'quick'
    buffer.move_word_forward()
    assert buffer.cursor == (1, 0)  # 'brown' on the next line


def test_word_forward_at_the_last_word_lands_at_end_of_buffer():
    buffer = TextBuffer.from_text("hi there")
    buffer.move_word_forward()  # 'there' at (0,3)

    buffer.move_word_forward()
    assert buffer.cursor == (0, 8)  # end of the line, no further word


def test_word_end_moves_to_the_end_of_the_next_word():
    buffer = TextBuffer.from_text("the quick")

    buffer.move_word_end()
    assert buffer.cursor == (0, 2)  # last char of 'the'
    buffer.move_word_end()
    assert buffer.cursor == (0, 8)  # last char of 'quick'


def test_delete_char_removes_the_character_under_the_cursor():
    buffer = TextBuffer.from_text("hello")  # cursor (0,0)

    buffer.delete_char()

    assert buffer.text == "ello"
    assert buffer.cursor == (0, 0)


def test_delete_char_past_the_last_character_is_a_noop():
    buffer = TextBuffer.from_text("hi")
    buffer.move_line_end()  # (0,2), nothing under the cursor

    buffer.delete_char()

    assert buffer.text == "hi"


def test_delete_line_removes_the_current_line():
    buffer = TextBuffer.from_text("one\ntwo\nthree")
    buffer.move_down()  # (1,0) on 'two'

    buffer.delete_line()

    assert buffer.lines == ("one", "three")
    assert buffer.cursor == (1, 0)


def test_deleting_the_only_line_leaves_one_empty_line():
    buffer = TextBuffer.from_text("solo")

    buffer.delete_line()

    assert buffer.lines == ("",)
    assert buffer.cursor == (0, 0)


def test_deleting_the_last_line_moves_the_cursor_up():
    buffer = TextBuffer.from_text("one\ntwo")
    buffer.move_down()  # (1,0)

    buffer.delete_line()

    assert buffer.lines == ("one",)
    assert buffer.cursor == (0, 0)


def test_word_back_moves_to_previous_word_start_and_clamps():
    buffer = TextBuffer.from_text("the quick brown")
    buffer.move_line_end()  # (0,15)

    buffer.move_word_back()
    assert buffer.cursor == (0, 10)  # 'brown'
    buffer.move_word_back()
    assert buffer.cursor == (0, 4)  # 'quick'
    buffer.move_word_back()
    assert buffer.cursor == (0, 0)  # 'the'
    buffer.move_word_back()
    assert buffer.cursor == (0, 0)  # clamped at the first word


def test_open_below_inserts_an_empty_line_after_the_cursor_line():
    buffer = TextBuffer.from_text("hello\nworld")  # cursor at (0,0)

    buffer.open_below()

    assert buffer.lines == ("hello", "", "world")
    assert buffer.cursor == (1, 0)


def test_open_above_inserts_an_empty_line_before_the_cursor_line():
    buffer = TextBuffer.from_text("hello\nworld")
    buffer.move_down()  # cursor at (1,0) on "world"

    buffer.open_above()

    assert buffer.lines == ("hello", "", "world")
    assert buffer.cursor == (1, 0)


def test_newline_starts_a_new_logical_line_and_word_count_spans_the_buffer():
    buffer = TextBuffer()

    for ch in "hello":
        buffer.insert(ch)
    buffer.newline()
    for ch in "world":
        buffer.insert(ch)

    assert buffer.text == "hello\nworld"
    assert buffer.cursor == (1, 5)
    assert buffer.word_count == 2
