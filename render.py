"""Frame -> PIL.Image rendering for the e-paper panel.

This is the only editor module that imports PIL. It paints the visual rows the
layout module decides (word-wrapped, scrolled) into a 1-bit image the size of
the panel, with a thin status line pinned to the bottom. It owns no panel/SPI
knowledge -- a display backend takes the finished image from here.
"""

from PIL import Image, ImageDraw, ImageFont

from editor.layout import cursor_view


def _load_font(font_paths, size):
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    # No TTF found. Fall back to PIL's builtin font. Raspberry Pi OS (Bookworm)
    # ships Pillow 9.4, whose load_default() has no size argument (added in
    # 10.1), so degrade gracefully rather than crash -- though installing
    # fonts-dejavu-core is strongly preferred for legible text.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


class Renderer:
    def __init__(self, config):
        self._config = config
        self._font = _load_font(config.font_paths, config.font_size)

        ascent, descent = self._font.getmetrics()
        self._line_h = ascent + descent + config.line_spacing
        self._char_w = max(1, round(self._font.getlength("M")))

        usable_w = config.panel_width - 2 * config.margin
        self._chars_per_line = max(1, usable_w // self._char_w)
        self._status_h = self._line_h

    @property
    def chars_per_line(self) -> int:
        return self._chars_per_line

    @property
    def lines_on_screen(self) -> int:
        text_area = self._config.panel_height - self._status_h - self._config.margin
        return max(1, text_area // self._line_h)

    def render(self, frame) -> Image.Image:
        config = self._config
        image = Image.new("1", (config.panel_width, config.panel_height), 255)
        draw = ImageDraw.Draw(image)

        rows, cur_row, cur_col = cursor_view(
            list(frame.lines), frame.cursor, self._chars_per_line, self.lines_on_screen
        )
        y = config.margin
        for row in rows:
            draw.text((config.margin, y), row, font=self._font, fill=0)
            y += self._line_h

        self._draw_cursor(draw, cur_row, cur_col)

        separator_y = config.panel_height - self._status_h
        draw.line([(0, separator_y), (config.panel_width, separator_y)], fill=0)
        draw.text((config.margin, separator_y + 2), frame.status, font=self._font, fill=0)
        return image

    def _draw_cursor(self, draw, cur_row: int, cur_col: int) -> None:
        # An underline cursor: visible feedback that never obscures the glyph,
        # which suits a 1-bit panel and reads the same in NORMAL and INSERT.
        x = self._config.margin + cur_col * self._char_w
        y = self._config.margin + cur_row * self._line_h
        draw.rectangle([x, y + self._line_h - 3, x + self._char_w, y + self._line_h - 1], fill=0)
