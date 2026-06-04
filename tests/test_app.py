"""Behavioral tests for the editor event loop (the M1 type-and-see loop).

The loop is wired from injected collaborators so it runs with zero hardware and
zero PIL: a scripted input source, a fake monotonic clock, and a display double
that records the frames it is asked to present. We assert on *observable
behaviour* -- how many refreshes happened, of what kind, and what they showed --
never on the loop's internals.
"""

from app import Editor, QUIT
from editor.buffer import TextBuffer
from editor.modal import Mode, ModalEditor
from editor.refresh import RefreshPolicy


class FakeClock:
    """Monotonic millisecond clock advanced explicitly by the input script."""

    def __init__(self):
        self.now_ms = 0

    def advance(self, ms):
        self.now_ms += ms


class ScriptedInput:
    """Replays a script of (advance_ms, value) steps.

    value is a character, None (a poll timeout with no key), or QUIT to stop the
    loop. Each step advances the shared clock first, mimicking real elapsed time.
    """

    def __init__(self, clock, script):
        self._clock = clock
        self._script = list(script)
        self._i = 0

    def next(self, timeout_ms):
        advance, value = self._script[self._i]
        self._i += 1
        self._clock.advance(advance)
        return value


class RecordingDisplay:
    def __init__(self):
        self.calls = []  # (kind, frame) where kind is "partial" or "full"

    def present(self, frame, *, full):
        self.calls.append(("full" if full else "partial", frame))

    def sleep(self):
        pass


def build_editor(clock, script, display, debounce_ms=400):
    # These tests exercise the INSERT-mode debounce/word-boundary behaviour, so
    # start in INSERT (the editor itself launches in NORMAL).
    return Editor(
        state=ModalEditor(TextBuffer(), mode=Mode.INSERT),
        policy=RefreshPolicy(debounce_ms=debounce_ms),
        source=ScriptedInput(clock, script),
        display=display,
        now_ms=lambda: clock.now_ms,
        poll_ms=100,
    )


def test_normal_mode_command_refreshes_immediately_no_debounce_wait():
    clock = FakeClock()
    display = RecordingDisplay()
    editor = Editor(
        state=ModalEditor(TextBuffer.from_text("hello")),  # NORMAL
        policy=RefreshPolicy(debounce_ms=400),
        source=ScriptedInput(clock, [(10, "l"), (0, QUIT)]),
        display=display,
        now_ms=lambda: clock.now_ms,
        poll_ms=100,
    )

    editor.run()

    # 'l' moved the cursor -> one immediate partial, without any pause.
    assert [kind for kind, _ in display.calls] == ["partial"]


def test_normal_mode_noop_command_does_not_refresh():
    clock = FakeClock()
    display = RecordingDisplay()
    editor = Editor(
        state=ModalEditor(TextBuffer.from_text("hello")),  # cursor at (0,0)
        policy=RefreshPolicy(debounce_ms=400),
        source=ScriptedInput(clock, [(10, "h"), (0, QUIT)]),  # 'h' into the left wall
        display=display,
        now_ms=lambda: clock.now_ms,
        poll_ms=100,
    )

    editor.run()

    assert display.calls == []  # nothing moved, so no wasted e-paper refresh


def test_typing_a_word_then_a_space_causes_exactly_one_partial_refresh():
    clock = FakeClock()
    display = RecordingDisplay()
    script = [
        (10, "h"),   # mid-word: batched, no refresh
        (10, "i"),   # mid-word: batched, no refresh
        (5, " "),    # word boundary: one partial refresh
        (0, QUIT),
    ]
    editor = build_editor(clock, script, display)

    editor.run()

    partials = [frame for kind, frame in display.calls if kind == "partial"]
    assert len(partials) == 1
    assert partials[0].lines == ("hi ",)


def test_a_typing_pause_flushes_the_batched_text_once():
    clock = FakeClock()
    display = RecordingDisplay()
    script = [
        (10, "h"),
        (10, "i"),
        (400, None),  # poll timeout after a 400ms pause -> flush
        (0, QUIT),
    ]
    editor = build_editor(clock, script, display)

    editor.run()

    partials = [frame for kind, frame in display.calls if kind == "partial"]
    assert len(partials) == 1
    assert partials[0].lines == ("hi",)


def test_no_refresh_happens_while_typing_stays_within_the_debounce_window():
    clock = FakeClock()
    display = RecordingDisplay()
    script = [
        (10, "h"),
        (100, None),  # only 100ms pause -> still batching
        (10, "i"),
        (100, None),  # still within debounce
        (0, QUIT),
    ]
    editor = build_editor(clock, script, display)

    editor.run()

    assert display.calls == []  # nothing shown yet; words still being typed


def test_enter_splits_into_a_new_logical_line():
    clock = FakeClock()
    display = RecordingDisplay()
    script = [
        (10, "h"), (10, "i"),
        (5, "\n"),  # Enter -> new line (and a boundary refresh)
        (10, "y"), (10, "o"),
        (5, " "),
        (0, QUIT),
    ]
    editor = build_editor(clock, script, display)

    editor.run()

    last_frame = display.calls[-1][1]
    assert last_frame.lines == ("hi", "yo ")


def test_backspace_deletes_the_previous_character():
    clock = FakeClock()
    display = RecordingDisplay()
    script = [
        (10, "h"), (10, "i"), (10, "x"),
        (5, "\b"),  # remove the stray 'x'
        (5, " "),  # boundary -> refresh
        (0, QUIT),
    ]
    editor = build_editor(clock, script, display)

    editor.run()

    last_frame = display.calls[-1][1]
    assert last_frame.lines == ("hi ",)
