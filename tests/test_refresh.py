"""Behavioral tests for the INSERT-mode refresh decision.

The policy is the heart of the writerdeck: it decides *when* a partial refresh
should fire while typing, so we never refresh per keystroke. Time is injected as
integer milliseconds (``now_ms=``) so debounce behaviour is tested
deterministically without sleeping and without float-comparison jitter.
Dependency-free.
"""

from editor.refresh import RefreshPolicy


def test_word_boundary_keystroke_triggers_an_immediate_refresh():
    policy = RefreshPolicy(debounce_ms=400)

    # Mid-word characters should not trigger a refresh on their own.
    assert policy.note_keystroke("h", now_ms=0) is False
    assert policy.note_keystroke("i", now_ms=100) is False

    # A space ends a word -> refresh now (the reader can see a finished word).
    assert policy.note_keystroke(" ", now_ms=200) is True

    # Enter (newline) is also a word boundary.
    assert policy.note_keystroke("a", now_ms=300) is False
    assert policy.note_keystroke("\n", now_ms=400) is True


def test_typing_pause_makes_a_refresh_due_after_the_debounce_interval():
    policy = RefreshPolicy(debounce_ms=400)

    policy.note_keystroke("h", now_ms=0)

    assert policy.due(now_ms=300) is False  # still mid-pause, keep batching
    assert policy.due(now_ms=400) is True  # paused long enough -> flush


def test_each_new_keystroke_restarts_the_debounce_timer():
    policy = RefreshPolicy(debounce_ms=400)

    policy.note_keystroke("h", now_ms=0)
    policy.note_keystroke("i", now_ms=300)  # restarts the clock

    assert policy.due(now_ms=500) is False  # only 200ms since the last keystroke
    assert policy.due(now_ms=700) is True


def test_after_a_refresh_nothing_is_due_until_more_typing():
    policy = RefreshPolicy(debounce_ms=400)

    policy.note_keystroke("h", now_ms=0)
    assert policy.due(now_ms=400) is True

    policy.mark_refreshed()

    assert policy.due(now_ms=10_000) is False  # flushed; wait for new input
