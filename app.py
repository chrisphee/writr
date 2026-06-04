"""The editor event loop.

Every collaborator is injected, so the loop has no hardware or PIL dependency of
its own: the input source yields characters (or None on a poll timeout, or QUIT
to stop), the clock yields monotonic milliseconds, and the display accepts
Frames to present.

The loop hands each key to the ModalEditor and refreshes based on the outcome:
TEXT (INSERT typing) defers to the debounce policy so we never refresh per
keystroke; CHANGED (a NORMAL command or a mode switch) refreshes immediately,
because in NORMAL the user moves slowly and wants instant feedback; NONE does
nothing. During an INSERT pause, the debounce timeout flushes the batched text.
"""

from editor.frame import Frame
from editor.modal import Mode, Outcome

# Sentinel an input source returns to ask the loop to stop.
QUIT = object()


def run_picker(picker, source, display, poll_ms):
    """Drive the launch file picker until a draft is chosen; return the choice.

    Returns the picker's current value on commit, or None if the source asks to
    quit. The list is drawn full once, then partially on each selection move.
    """
    display.present(picker.frame(), full=True)
    while True:
        key = source.next(poll_ms)
        if key is QUIT:
            return None
        if key is None:
            continue  # idle poll; keep waiting
        outcome = picker.handle(key)
        if outcome == "chosen":
            return picker.current
        if outcome == "moved":
            display.present(picker.frame(), full=False)


class Editor:
    def __init__(
        self, *, state, policy, source, display, now_ms, poll_ms, ghosting=None, autosave=None
    ):
        self._state = state
        self._policy = policy
        self._source = source
        self._display = display
        self._now_ms = now_ms
        self._poll_ms = poll_ms
        self._ghosting = ghosting
        self._autosave = autosave
        self._last_saved = state.buffer.text

    def run(self) -> None:
        while True:
            ch = self._source.next(self._poll_ms)
            if ch is QUIT:
                break
            now = self._now_ms()
            if ch is None:
                # Poll timeout: only INSERT batches text, so only it can be due.
                if self._state.mode is Mode.INSERT and self._policy.due(now):
                    self._refresh()
                continue

            outcome = self._state.handle(ch)
            if outcome is Outcome.TEXT:
                if self._policy.note_keystroke(ch, now):
                    self._refresh()
            elif outcome is Outcome.CHANGED:
                self._refresh()
            # Outcome.NONE: the key did nothing; no refresh.

    def show(self) -> None:
        """Draw the current state once (full refresh) -- used on launch/open."""
        self._present(full=True)

    def _refresh(self) -> None:
        # Persist before the slow panel transfer so words survive a power cut.
        self._maybe_autosave()
        full = self._ghosting.next_is_full() if self._ghosting is not None else False
        self._present(full=full)

    def _present(self, full: bool) -> None:
        buffer = self._state.buffer
        frame = Frame(
            lines=buffer.lines,
            cursor=buffer.cursor,
            status=f"{self._state.mode.value}  {buffer.word_count} words",
        )
        self._display.present(frame, full=full)
        self._policy.mark_refreshed()

    def _maybe_autosave(self) -> None:
        if self._autosave is None:
            return
        text = self._state.buffer.text
        if text != self._last_saved:
            self._autosave(text)
            self._last_saved = text

    def flush(self) -> None:
        """Persist any unsaved text (call on shutdown, even mid-debounce)."""
        self._maybe_autosave()
