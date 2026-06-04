"""The display abstraction the editor loop talks to.

A Display takes editor Frames and is responsible for getting them onto a screen;
how it does so (write a PNG, drive an SPI panel) is the backend's business. The
loop only ever calls ``present`` and ``sleep``, so it never depends on PIL or
hardware. ``full`` selects a slow ghosting-clearing refresh over a fast partial
one -- a backend with only one refresh path may ignore it.
"""

from abc import ABC, abstractmethod

from editor.frame import Frame


class Display(ABC):
    @abstractmethod
    def present(self, frame: Frame, *, full: bool) -> None:
        """Render and show a frame; ``full`` requests a full (vs partial) refresh."""

    @abstractmethod
    def sleep(self) -> None:
        """Put the panel into its low-power state (no-op for backends without one)."""
