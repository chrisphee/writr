"""INSERT-mode refresh decision.

E-paper partial refreshes are slow (~0.7s) and ugly per keystroke, so while
typing we batch characters and only refresh on a natural boundary: either a
finished word (space / newline) or a typing pause (debounce). NORMAL-mode
refresh-per-action and the periodic ghosting-clearing full refresh are decided
elsewhere -- this policy owns only the INSERT-while-typing decision.

Time is taken as integer milliseconds. Integers keep debounce comparisons exact
(no float-epsilon jitter at the threshold) and match how the debounce is
configured ("400ms"); the event loop supplies a monotonic millisecond clock.
"""

from enum import Enum

WORD_BOUNDARY_CHARS = frozenset({" ", "\n", "\t"})


class RefreshPolicy:
    def __init__(self, debounce_ms: int = 400):
        self._debounce_ms = debounce_ms
        self._pending = False
        self._last_keystroke_ms = 0

    def note_keystroke(self, ch: str, now_ms: int) -> bool:
        """Record a keystroke; return True if it should refresh immediately."""
        self._pending = True
        self._last_keystroke_ms = now_ms
        return ch in WORD_BOUNDARY_CHARS

    def due(self, now_ms: int) -> bool:
        """True when batched changes have waited out the debounce interval."""
        return self._pending and (now_ms - self._last_keystroke_ms) >= self._debounce_ms

    def mark_refreshed(self) -> None:
        """Tell the policy a refresh just happened; clears the batched change."""
        self._pending = False


class GhostingCounter:
    """Decides when a refresh should be a full (ghosting-clearing) one.

    Partial refreshes accumulate ghosting on e-paper, so every ``full_every``
    refreshes one is promoted to a full refresh. The loop calls next_is_full()
    once per refresh; reset() restarts the count after a full refresh forced
    elsewhere (e.g. on file save).
    """

    def __init__(self, full_every: int):
        self._full_every = full_every
        self._count = 0

    def next_is_full(self) -> bool:
        self._count += 1
        if self._count >= self._full_every:
            self._count = 0
            return True
        return False

    def reset(self) -> None:
        self._count = 0


class Refresh(Enum):
    """What the loop should do after asking the controller for a decision."""

    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"


class RefreshController:
    """The single owner of *when and how* the panel refreshes.

    It composes the INSERT-mode debounce policy and the ghosting cadence, and
    adds the one rule the loop used to lack: a full (whole-screen, flashing)
    refresh is **deferred until typing/motion pauses**, so the ghosting-clear
    never interrupts you mid-word or mid-scroll -- the source of the "random
    full-screen flicker". The editor loop applies a whole drained batch of
    input, then asks this controller for a single decision.

    The loop reports what a batch did via four flags:
      * ``changed``   -- the editor state changed at all (else: nothing to show)
      * ``texted``    -- the batch was INSERT typing
      * ``boundary``  -- that typing included a word boundary (space/newline)
      * ``commanded`` -- the batch included a NORMAL command or a mode switch

    A pure mid-word batch is held back for the debounce; anything that finishes a
    word or runs a command is shown immediately, as a partial. A full only ever
    fires from ``after_idle`` -- i.e. once you have actually paused.
    """

    def __init__(self, *, debounce_ms: int = 400, full_every: int = 30):
        self._policy = RefreshPolicy(debounce_ms)
        self._ghosting = GhostingCounter(full_every)
        self._debounce_ms = debounce_ms
        self._owe_full = False
        self._last_activity_ms = 0

    def after_input(self, *, changed, texted, boundary, commanded, now_ms) -> Refresh:
        """Decide after a non-empty batch of keys was applied to the editor."""
        if not changed:
            return Refresh.NONE
        self._last_activity_ms = now_ms
        if commanded or boundary:
            # A finished word, a NORMAL command, or a mode switch: show it now,
            # but keep any owed ghosting-clear for the next pause (deferring).
            return self._fire(deferring=True)
        # Pure mid-word typing: batch it; a pause (after_idle) will flush it.
        self._policy.note_keystroke("x", now_ms)
        return Refresh.NONE

    def after_idle(self, now_ms) -> Refresh:
        """Decide on a poll timeout (no input within the poll window)."""
        if (now_ms - self._last_activity_ms) < self._debounce_ms:
            return Refresh.NONE  # not actually paused yet -- still mid-burst
        if self._policy.due(now_ms):
            return self._fire(deferring=False)  # flush batched text at the pause
        if self._owe_full:
            return self._fire(deferring=False, force_full=True)  # pay the debt now
        return Refresh.NONE

    def _fire(self, *, deferring: bool, force_full: bool = False) -> Refresh:
        if self._ghosting.next_is_full():
            self._owe_full = True
        self._policy.mark_refreshed()
        if force_full or (self._owe_full and not deferring):
            self._owe_full = False
            self._ghosting.reset()
            return Refresh.FULL
        return Refresh.PARTIAL
