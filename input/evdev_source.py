"""evdev keyboard input source for a bare Linux console (no X).

Implements the source contract the editor loop expects -- ``next(timeout_ms)``
returns a decoded character, or None on a poll timeout (which lets the loop run
its debounce). All the genuinely tricky logic (shift state, name->char) lives in
the pure KeyDecoder/keymap and is unit-tested; this file is the I/O glue that
can only be verified on hardware, so it is kept thin.

Reading runs on a background daemon thread that continuously drains the kernel
evdev buffer into an unbounded in-process queue. This is essential on e-paper:
the main loop blocks for ~0.7s (partial) or ~4s (full) inside each panel
refresh, and if nothing drained the keyboard during that window the small
kernel buffer would overflow and *drop* keystrokes when typing fast. The panel's
SPI transfer and busy-wait release the GIL, so the reader thread runs even on
the single-core Zero while the main thread is rendering.

Robustness the brief demands:
  * device discovery -- pick the keyboard out of /dev/input/event*
  * graceful reconnect -- a foldable BT keyboard's device node vanishes when it
    sleeps; the reader thread keeps polling and never crashes on a vanished node
"""

import logging
import queue
import select
import threading
import time

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
        self._decoder = KeyDecoder()
        self._chars: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._reader = threading.Thread(target=self._read_loop, name="evdev-reader", daemon=True)
        self._reader.start()

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

    def is_present(self) -> bool:
        """Whether a keyboard is currently discoverable (used by the boot wait)."""
        device = self._find_device()
        if device is None:
            return False
        try:
            device.close()
        except OSError:
            pass
        return True

    # -- reading (background thread) --------------------------------------------

    def _read_loop(self) -> None:
        device = None
        try:
            while not self._stop.is_set():
                if device is None:
                    device = self._find_device()
                    if device is None:
                        # No keyboard yet (asleep / not paired). Wait, don't spin.
                        self._stop.wait(self._reconnect_poll_s)
                        continue
                try:
                    # Short timeout so we notice a stop request / reconnect promptly.
                    readable, _, _ = select.select([device.fd], [], [], 0.2)
                    if not readable:
                        continue
                    for event in device.read():
                        if event.type != self._ecodes.EV_KEY:
                            continue
                        name = self._key_name(event.code)
                        if name is None:
                            continue
                        char = self._decoder.feed(name, event.value)
                        if char is not None:
                            self._chars.put(char)
                except OSError:
                    # The BT keyboard slept and its node vanished mid-read. Drop
                    # it; we'll rediscover it when it wakes.
                    logger.warning("keyboard disconnected; awaiting reconnect")
                    device = None
        finally:
            if device is not None:
                try:
                    device.close()
                except OSError:
                    pass

    def next(self, timeout_ms: int):
        """Return the next typed character, or None if none within the timeout."""
        try:
            return self._chars.get(timeout=timeout_ms / 1000.0)
        except queue.Empty:
            return None

    def _key_name(self, code):
        name = self._ecodes.KEY.get(code)
        if isinstance(name, list):  # some codes map to several names
            return name[0]
        return name

    def close(self) -> None:
        self._stop.set()
        self._reader.join(timeout=1.0)
