"""Integration tests for the PIL renderer and the mock display backend.

These are the only tests that need Pillow; they auto-skip if it is absent so the
pure-logic suite still runs on a bare machine. They assert on observable image
properties (panel size, 1-bit mode, presence of ink) and on the mock backend's
externally-visible behaviour (PNG files written, refresh log entries) -- never on
pixel-exact output, which would be brittle across fonts.
"""

import pytest

pytest.importorskip("PIL")

from config import Config
from display.mock import MockDisplay
from editor.frame import Frame
from render import Renderer


def _ink_pixels(image) -> int:
    """Count black (ink) pixels in a 1-bit image (histogram bin 0 == black)."""
    return image.histogram()[0]


def test_renderer_produces_a_panel_sized_one_bit_image():
    config = Config()
    renderer = Renderer(config)

    image = renderer.render(Frame(lines=("hello world",), cursor=(0, 11), status="2 words"))

    assert image.size == (config.panel_width, config.panel_height)
    assert image.mode == "1"


def test_renderer_puts_ink_on_the_panel_for_typed_text():
    config = Config()
    renderer = Renderer(config)

    empty = renderer.render(Frame(lines=("",), cursor=(0, 0), status=""))
    typed = renderer.render(Frame(lines=("hello world",), cursor=(0, 11), status="2 words"))

    assert _ink_pixels(typed) > _ink_pixels(empty)


def _pack_like_waveshare_getbuffer(image):
    """Reference reimplementation of epd4in26.getbuffer()'s landscape branch.

    Mirrors the vendored driver exactly (init 0xFF, clear a bit per black pixel,
    MSB = leftmost pixel, rows of width/8 bytes) so we can prove that PIL's
    Image.tobytes() yields the identical framebuffer -- letting us skip the
    driver's slow pure-Python loop on the Pi.
    """
    width, height = image.size
    pixels = image.load()
    buf = bytearray([0xFF] * (width // 8 * height))
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 0:  # black
                buf[(x + y * width) // 8] &= ~(0x80 >> (x % 8))
    return bytes(buf)


def test_tobytes_matches_the_drivers_getbuffer_packing():
    config = Config()
    renderer = Renderer(config)
    frames = [
        Frame(lines=("",), cursor=(0, 0), status=""),  # mostly white
        Frame(lines=("the quick brown fox",), cursor=(0, 4), status="NORMAL  4 words"),
    ]

    for frame in frames:
        image = renderer.render(frame)
        assert image.size == (800, 480) and image.mode == "1"
        assert image.tobytes() == _pack_like_waveshare_getbuffer(image)


def test_cursor_is_drawn_at_a_position_derived_from_the_cursor():
    config = Config()
    renderer = Renderer(config)

    # Same text, cursor at two different columns -> the drawn cursor moves, so
    # the two images must differ.
    at_start = renderer.render(Frame(lines=("hello world",), cursor=(0, 0), status="NORMAL"))
    at_col5 = renderer.render(Frame(lines=("hello world",), cursor=(0, 5), status="NORMAL"))

    assert at_start.tobytes() != at_col5.tobytes()


def test_mock_display_writes_a_png_and_logs_every_refresh(tmp_path):
    display = MockDisplay(Config(), output_dir=tmp_path)

    display.present(Frame(lines=("hi ",), cursor=(0, 3), status="1 words"), full=False)
    display.present(Frame(lines=("hi there",), cursor=(0, 8), status="2 words"), full=True)

    pngs = sorted(tmp_path.glob("*.png"))
    assert len(pngs) == 2
    assert [event.kind for event in display.log] == ["partial", "full"]
    assert all(event.duration_ms >= 0 for event in display.log)
