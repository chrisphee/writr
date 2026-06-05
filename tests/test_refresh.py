"""Behavioral tests for the INSERT-mode refresh decision.

The policy is the heart of the writerdeck: it decides *when* a partial refresh
should fire while typing, so we never refresh per keystroke. Time is injected as
integer milliseconds (``now_ms=``) so debounce behaviour is tested
deterministically without sleeping and without float-comparison jitter.
Dependency-free.
"""

from editor.refresh import GhostingCounter, Refresh, RefreshController, RefreshPolicy


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


def test_every_nth_refresh_is_a_full_refresh_to_clear_ghosting():
    counter = GhostingCounter(full_every=3)

    pattern = [counter.next_is_full() for _ in range(7)]

    assert pattern == [False, False, True, False, False, True, False]


def test_reset_restarts_the_partial_count():
    counter = GhostingCounter(full_every=3)
    counter.next_is_full()
    counter.next_is_full()  # two partials accumulated

    counter.reset()  # e.g. after a full refresh forced elsewhere (file save)

    assert counter.next_is_full() is False  # count started over


# -- RefreshController: the unified when/how decision -------------------------


def test_controller_unchanged_batch_does_not_refresh():
    controller = RefreshController()

    decision = controller.after_input(
        changed=False, texted=False, boundary=False, commanded=False, now_ms=0
    )

    assert decision is Refresh.NONE


def test_controller_normal_command_is_an_immediate_partial():
    controller = RefreshController(debounce_ms=400)

    decision = controller.after_input(
        changed=True, texted=False, boundary=False, commanded=True, now_ms=0
    )

    assert decision is Refresh.PARTIAL


def test_controller_word_boundary_is_an_immediate_partial():
    controller = RefreshController(debounce_ms=400)

    decision = controller.after_input(
        changed=True, texted=True, boundary=True, commanded=False, now_ms=0
    )

    assert decision is Refresh.PARTIAL


def test_controller_batches_midword_text_then_flushes_at_a_pause():
    controller = RefreshController(debounce_ms=400)

    # Mid-word characters are held back -- no refresh yet.
    assert controller.after_input(
        changed=True, texted=True, boundary=False, commanded=False, now_ms=0
    ) is Refresh.NONE
    assert controller.after_input(
        changed=True, texted=True, boundary=False, commanded=False, now_ms=50
    ) is Refresh.NONE

    # Still within the debounce window -> still nothing.
    assert controller.after_idle(now_ms=100) is Refresh.NONE
    # Paused past the debounce -> flush the batched text as a partial.
    assert controller.after_idle(now_ms=450) is Refresh.PARTIAL


def test_controller_defers_the_ghosting_full_until_a_pause():
    controller = RefreshController(debounce_ms=400, full_every=3)

    # Three commands in quick succession. The 3rd would be the ghosting full,
    # but we are mid-activity, so it stays a partial -- no flash mid-motion.
    for t in (0, 10, 20):
        decision = controller.after_input(
            changed=True, texted=False, boundary=False, commanded=True, now_ms=t
        )
        assert decision is Refresh.PARTIAL

    assert controller.after_idle(now_ms=100) is Refresh.NONE  # not paused yet
    # A genuine pause pays the deferred ghosting-clear, even in NORMAL mode.
    assert controller.after_idle(now_ms=420) is Refresh.FULL
    # Debt paid: a later pause does nothing.
    assert controller.after_idle(now_ms=2000) is Refresh.NONE
