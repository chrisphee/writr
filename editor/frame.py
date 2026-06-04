"""A renderable description of the editor's current view.

A Frame is plain data: the logical lines, the cursor position, and the status
text. It carries no pixels and no panel knowledge, which is what lets the event
loop be tested without PIL. The renderer turns a Frame into an image (handling
word-wrap and scroll); the display backend pushes that image to the panel.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    lines: tuple[str, ...]
    cursor: tuple[int, int]
    status: str = ""
