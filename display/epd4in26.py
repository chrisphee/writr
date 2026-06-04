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
  sleep()             deep sleep + release GPIO/SPI

Refresh model: the first frame and every ``full`` refresh go through
display_Base (which both clears ghosting with the full waveform and re-arms the
partial base); everything else is a display_Partial.
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
        if full or not self._base_written:
            self._epd.display_Base(buffer)
            self._base_written = True
            logger.info("full refresh")
        else:
            self._epd.display_Partial(buffer)
            logger.info("partial refresh")

    def sleep(self) -> None:
        self._epd.sleep()
