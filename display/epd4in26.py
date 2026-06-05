"""Hardware display backend for the Waveshare 4.26" e-Paper HAT (800x480, SPI).

This is the only backend that touches the panel. It is never exercised by the
automated suite (no SPI/GPIO on the dev box) -- the human verifies it on the Pi.
The driver import is lazy so importing this module stays safe off-hardware.

The method names below are taken verbatim from the vendored upstream
``waveshare_epd/epd4in26.py`` (read, not guessed):

  init()              full slow init (returns -1 on failure)
  Clear()             blank the panel to white
  getbuffer(image)    PIL 1-bit image -> packed byte buffer (expects 800x480)
  display_Base(buf)   full refresh AND store the base image partial diffs against
  display_Partial(buf) fast (~0.7s) partial refresh
  TurnOnDisplay_Fast() activate the fast (~1.5s) full-update waveform
  sleep()             deep sleep + release GPIO/SPI

Refresh model:
  * The first frame goes through display_Base -- a slow (~4s) full refresh that
    lays down a pristine base for partial diffs.
  * Every later ``full`` (the periodic ghosting-clear) re-arms that base the same
    way -- writing both the BW (0x24) and base (0x26) RAM -- but triggers the
    FAST waveform (~1.5s) instead of the slow one, so the screen-clearing flash
    is quick. The RefreshController only ever asks for this at a typing pause.
  * Everything else is a display_Partial.

The fast-base path drives the vendored driver's own primitives (send_command /
send_data2 / TurnOnDisplay_Fast); it is the only backend that touches the panel
and is verified by hand on the Pi, never by the automated suite.
"""

import logging

from display.base import Display
from editor.frame import Frame
from render import Renderer

logger = logging.getLogger("writerdeck.display.epd4in26")


class Epd4in26Display(Display):
    def __init__(self, config):
        # Imported here, not at module top, so the dev machine (no spidev/gpiozero)
        # can still import this file; the import only runs when we're on the Pi.
        from waveshare_epd import epd4in26

        self._renderer = Renderer(config)
        self._epd = epd4in26.EPD()
        if self._epd.init() != 0:
            raise RuntimeError("epd4in26 init() failed (panel not connected?)")
        self._epd.Clear()
        self._base_written = False

    def present(self, frame: Frame, *, full: bool) -> None:
        image = self._renderer.render(frame)
        # The driver's getbuffer() packs 800x480 in a pure-Python double loop --
        # seconds per refresh on the Pi Zero's single core. For a full-screen
        # 1-bit image whose width is a multiple of 8, PIL's tobytes() produces the
        # byte-identical framebuffer in C (see test_tobytes_matches_the_drivers_
        # getbuffer_packing), so we use it directly and skip the slow loop.
        buffer = image.tobytes()
        if not self._base_written:
            # First frame: slow, pristine full refresh that arms the partial base.
            self._epd.display_Base(buffer)
            self._base_written = True
            logger.info("full refresh (base)")
        elif full:
            self._fast_base(buffer)
            logger.info("full refresh (fast)")
        else:
            self._epd.display_Partial(buffer)
            logger.info("partial refresh")

    def _fast_base(self, buffer) -> None:
        # Mirror display_Base -- write BW RAM (0x24) and base RAM (0x26) so the
        # following partials still diff cleanly -- but drive it with the fast
        # update sequence (~1.5s) instead of display_Base's slow one (~4s).
        epd = self._epd
        epd.send_command(0x24)
        epd.send_data2(buffer)
        epd.send_command(0x26)
        epd.send_data2(buffer)
        epd.TurnOnDisplay_Fast()

    def sleep(self) -> None:
        self._epd.sleep()
