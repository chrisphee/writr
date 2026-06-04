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
