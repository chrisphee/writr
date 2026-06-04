"""evdev keyboard input source for a bare Linux console (no X).

Implements the source contract the editor loop expects -- ``next(timeout_ms)``
returns a decoded character, or None on a poll timeout (which lets the loop run
its debounce). All the genuinely tricky logic (shift state, name->char) lives in
the pure KeyDecoder/keymap and is unit-tested; this file is the I/O glue that
can only be verified on hardware, so it is kept thin.

Robustness the brief demands:
  * device discovery -- pick the keyboard out of /dev/input/event*
  * graceful reconnect -- a foldable BT keyboard's device node vanishes when it
    sleeps; we must never crash, just keep polling until it reappears
"""

import logging
import select
import time
from collections import deque

from input.decoder import KeyDecoder

logger = logging.getLogger("writerdeck.input.evdev")


class EvdevKeyboard:
    def __init__(self, device_path=None, reconnect_poll_s=1.0):
        # Lazy import: the dev laptop has no python3-evdev, and this object is
        # only ever constructed on the Pi.
        import evdev
        from evdev import ecodes

        self._evdev = evdev
        self._ecodes = ecodes
        self._preferred_path = device_path
        self._reconnect_poll_s = reconnect_poll_s
        self._device = None
        self._decoder = KeyDecoder()
        self._queue: deque[str] = deque()

    # -- discovery / connection -------------------------------------------------

    def _looks_like_keyboard(self, device) -> bool:
        keys = device.capabilities().get(self._ecodes.EV_KEY, [])
        # A real text keyboard exposes the whole letter block.
        return self._ecodes.KEY_A in keys and self._ecodes.KEY_Z in keys

    def _find_device(self):
        if self._preferred_path:
            try:
                return self._evdev.InputDevice(self._preferred_path)
            except OSError:
                return None
        for path in self._evdev.list_devices():
            try:
                device = self._evdev.InputDevice(path)
            except OSError:
                continue
            if self._looks_like_keyboard(device):
                logger.info("keyboard connected: %s (%s)", device.name, path)
                return device
        return None

    def _ensure_device(self) -> bool:
        if self._device is None:
            self._device = self._find_device()
        return self._device is not None

    # -- reading ----------------------------------------------------------------

    def next(self, timeout_ms: int):
        if self._queue:
            return self._queue.popleft()

        if not self._ensure_device():
            # No keyboard yet (asleep / not paired). Wait a beat so we don't
            # busy-spin, then report a timeout so the loop can still flush.
            time.sleep(min(self._reconnect_poll_s, max(timeout_ms / 1000.0, 0.0)))
            return None

        try:
            readable, _, _ = select.select([self._device.fd], [], [], timeout_ms / 1000.0)
            if not readable:
                return None  # poll timeout -> debounce tick
            for event in self._device.read():
                if event.type != self._ecodes.EV_KEY:
                    continue
                name = self._key_name(event.code)
                if name is None:
                    continue
                char = self._decoder.feed(name, event.value)
                if char is not None:
                    self._queue.append(char)
        except OSError:
            # The BT keyboard slept and its node disappeared mid-read. Drop it;
            # _ensure_device() will rediscover it when it wakes.
            logger.warning("keyboard disconnected; awaiting reconnect")
            self._device = None
            return None

        return self._queue.popleft() if self._queue else None

    def _key_name(self, code):
        name = self._ecodes.KEY.get(code)
        if isinstance(name, list):  # some codes map to several names
            return name[0]
        return name

    def close(self) -> None:
        if self._device is not None:
            try:
                self._device.close()
            except OSError:
                pass
            self._device = None
