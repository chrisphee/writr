"""Behavioral tests for the editor event loop (the M1 type-and-see loop).

The loop is wired from injected collaborators so it runs with zero hardware and
zero PIL: a scripted input source, a fake monotonic clock, and a display double
that records the frames it is asked to present. We assert on *observable
behaviour* -- how many refreshes happened, of what kind, and what they showed --
never on the loop's internals.
"""

from app import Editor, QUIT, run_picker
from editor.buffer import TextBuffer
from editor.modal import Mode, ModalEditor
from editor.refresh import GhostingCounter, RefreshPolicy
from picker import FilePicker


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


def test_show_draws_the_initial_state_once_with_a_full_refresh():
    display = RecordingDisplay()
    editor = Editor(
        state=ModalEditor(TextBuffer.from_text("loaded draft")),
        policy=RefreshPolicy(),
        source=ScriptedInput(FakeClock(), [(0, QUIT)]),
        display=display,
        now_ms=lambda: 0,
        poll_ms=100,
    )

    editor.show()

    assert len(display.calls) == 1
    kind, frame = display.calls[0]
    assert kind == "full"
    assert frame.lines == ("loaded draft",)


def test_run_picker_navigates_and_returns_the_chosen_draft():
    clock = FakeClock()
    display = RecordingDisplay()
    picker = FilePicker(["newest.md", "older.md"])
    source = ScriptedInput(clock, [(5, "j"), (5, "\n")])  # down to older, then open

    chosen = run_picker(picker, source, display, poll_ms=100)

    assert chosen == "older.md"
    # first frame full (the list), then a partial when the selection moved
    assert [kind for kind, _ in display.calls] == ["full", "partial"]


def test_autosave_persists_text_after_a_word_is_typed():
    clock = FakeClock()
    saved = []
    editor = Editor(
        state=ModalEditor(TextBuffer(), mode=Mode.INSERT),
        policy=RefreshPolicy(debounce_ms=400),
        source=ScriptedInput(clock, [(10, "h"), (10, "i"), (5, " "), (0, QUIT)]),
        display=RecordingDisplay(),
        now_ms=lambda: clock.now_ms,
        poll_ms=100,
        autosave=saved.append,
    )

    editor.run()

    assert saved == ["hi "]  # saved once, when the word boundary flushed


def test_autosave_does_not_fire_for_a_motion_that_changes_no_text():
    clock = FakeClock()
    saved = []
    editor = Editor(
        state=ModalEditor(TextBuffer.from_text("hello")),  # NORMAL
        policy=RefreshPolicy(debounce_ms=400),
        source=ScriptedInput(clock, [(10, "l"), (0, QUIT)]),
        display=RecordingDisplay(),
        now_ms=lambda: clock.now_ms,
        poll_ms=100,
        autosave=saved.append,
    )

    editor.run()

    assert saved == []  # the cursor moved but the text is unchanged


def test_a_full_refresh_is_forced_every_n_refreshes_to_clear_ghosting():
    clock = FakeClock()
    display = RecordingDisplay()
    editor = Editor(
        state=ModalEditor(TextBuffer.from_text("l0\nl1\nl2\nl3\nl4\nl5\nl6")),  # NORMAL
        policy=RefreshPolicy(debounce_ms=400),
        source=ScriptedInput(clock, [(5, "j")] * 6 + [(0, QUIT)]),  # 6 down moves
        display=display,
        now_ms=lambda: clock.now_ms,
        poll_ms=100,
        ghosting=GhostingCounter(full_every=3),
    )

    editor.run()

    kinds = [kind for kind, _ in display.calls]
    assert kinds == ["partial", "partial", "full", "partial", "partial", "full"]


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
