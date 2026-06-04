"""Development display backend: renders frames to PNG files and logs refreshes.

This is how the refresh strategy is verified without hardware. Every present()
renders the frame with the real PIL renderer, writes a numbered PNG for visual
inspection, and records a RefreshEvent (type + render time) -- both to an
in-memory log a test can assert on and to the standard logger for live viewing.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from display.base import Display
from editor.frame import Frame
from render import Renderer

logger = logging.getLogger("writerdeck.display.mock")


@dataclass(frozen=True)
class RefreshEvent:
    kind: str  # "partial" or "full"
    duration_ms: float
    path: str


class MockDisplay(Display):
    def __init__(self, config, output_dir):
        self._renderer = Renderer(config)
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._count = 0
        self.log: list[RefreshEvent] = []

    def present(self, frame: Frame, *, full: bool) -> None:
        kind = "full" if full else "partial"
        start = time.perf_counter()
        image = self._renderer.render(frame)
        path = self._dir / f"frame_{self._count:04d}_{kind}.png"
        image.save(path)
        duration_ms = (time.perf_counter() - start) * 1000

        event = RefreshEvent(kind=kind, duration_ms=duration_ms, path=str(path))
        self.log.append(event)
        logger.info("%s refresh #%d in %.1fms -> %s", kind, self._count, duration_ms, path)
        self._count += 1

    def sleep(self) -> None:
        logger.info("display sleep (mock no-op)")
