"""Editor configuration.

A single dataclass with sane defaults that the human can tweak on the Pi. The
font is resolved from a candidate list so the same config works on the dev
laptop (Arch path) and the Pi (Bookworm path); the renderer falls back to PIL's
builtin font if none are present, so tests never depend on a specific TTF.
"""

from dataclasses import dataclass, field

# Tried in order; first that exists wins. Bookworm path first (the real target).
DEFAULT_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",  # Raspberry Pi OS
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",  # Arch dev box
)


@dataclass
class Config:
    # Waveshare 4.26" panel, landscape.
    panel_width: int = 800
    panel_height: int = 480

    # Text rendering.
    font_paths: tuple[str, ...] = DEFAULT_FONT_PATHS
    font_size: int = 28
    margin: int = 8
    line_spacing: int = 6  # extra pixels between baselines

    # INSERT-mode refresh batching.
    debounce_ms: int = 400
    # Clear accumulated ghosting after this many partial refreshes (M3).
    full_refresh_every: int = 30

    # Where drafts live (M4); new drafts get this extension.
    drafts_dir: str = "~/drafts"
    draft_extension: str = ".md"
