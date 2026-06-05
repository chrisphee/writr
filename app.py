"""The editor event loop.

Every collaborator is injected, so the loop has no hardware or PIL dependency of
its own: the input source drains characters (a possibly-empty batch, with QUIT
to stop), the clock yields monotonic milliseconds, and the display accepts
Frames to present.

Each turn the loop drains *every* keystroke queued right now, applies the whole
batch to the ModalEditor, and asks the RefreshController for a single decision.
Draining-then-deciding is what makes a held h/j/k/l (or a fast typing burst)
collapse to one panel refresh of the final state instead of one slow refresh per
key. The controller owns the rest: debounce batching while typing, the periodic
ghosting-clear, and deferring that full refresh to a pause so it never flashes
mid-word.
"""

from editor.frame import Frame
from editor.modal import Outcome
from editor.refresh import WORD_BOUNDARY_CHARS, Refresh

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
    def __init__(self, *, state, controller, source, display, now_ms, poll_ms, autosave=None):
        self._state = state
        self._controller = controller
        self._source = source
        self._display = display
        self._now_ms = now_ms
        self._poll_ms = poll_ms
        self._autosave = autosave
        self._last_saved = state.buffer.text

    def run(self) -> None:
        while True:
            batch = self._source.drain(self._poll_ms)
            now = self._now_ms()
            if not batch:
                # Idle poll: let the controller flush batched text or pay a
                # deferred ghosting-clear if we have now paused long enough.
                self._act(self._controller.after_idle(now))
                continue
            stop = QUIT in batch
            if stop:
                batch = batch[: batch.index(QUIT)]  # apply keys typed before quit
            if batch:
                summary = self._apply(batch)
                self._act(self._controller.after_input(now_ms=now, **summary))
            if stop:
                break

    def _apply(self, batch) -> dict:
        """Apply a whole batch of keys; report what it did for the controller."""
        changed = texted = boundary = commanded = False
        for ch in batch:
            outcome = self._state.handle(ch)
            if outcome is Outcome.TEXT:
                changed = texted = True
                if ch in WORD_BOUNDARY_CHARS:
                    boundary = True
            elif outcome is Outcome.CHANGED:
                changed = commanded = True
            # Outcome.NONE: this key did nothing.
        return {
            "changed": changed,
            "texted": texted,
            "boundary": boundary,
            "commanded": commanded,
        }

    def _act(self, decision: Refresh) -> None:
        if decision is Refresh.NONE:
            return
        # Persist before the slow panel transfer so words survive a power cut.
        self._maybe_autosave()
        self._present(full=decision is Refresh.FULL)

    def show(self) -> None:
        """Draw the current state once (full refresh) -- used on launch/open."""
        self._present(full=True)

    def _present(self, full: bool) -> None:
        buffer = self._state.buffer
        frame = Frame(
            lines=buffer.lines,
            cursor=buffer.cursor,
            status=f"{self._state.mode.value}  {buffer.word_count} words",
        )
        self._display.present(frame, full=full)

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
