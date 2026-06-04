"""Behavioral tests for the boot-time wait-for-keyboard loop.

On a Pi the Bluetooth keyboard often pairs a few seconds after boot, so the app
polls for it before starting rather than crashing when it is briefly absent.
The polling logic is pure (the presence check and sleep are injected); the
evdev device probe behind it is hardware glue.
"""

from main import wait_for_keyboard


def test_returns_immediately_without_sleeping_when_already_present():
    sleeps = []

    present = wait_for_keyboard(lambda: True, sleeps.append)

    assert present is True
    assert sleeps == []


def test_polls_until_the_keyboard_appears():
    checks = iter([False, False, True])
    sleeps = []

    present = wait_for_keyboard(lambda: next(checks), sleeps.append, poll_seconds=0.5)

    assert present is True
    assert sleeps == [0.5, 0.5]  # slept between the two failed checks


def test_gives_up_after_max_attempts_without_crashing():
    sleeps = []

    present = wait_for_keyboard(lambda: False, sleeps.append, max_attempts=3)

    assert present is False
    assert len(sleeps) == 3
