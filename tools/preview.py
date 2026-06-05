"""Generate sample PNG frames by driving the REAL editor loop through the mock.

No hardware, no evdev: a scripted keyboard plays a sentence into the same
`Editor` that runs on the Pi, backed by the MockDisplay. The point is twofold --
produce frames in ./mock_frames/ to eyeball the rendering, and print the refresh
log so the INSERT-mode strategy is visible (spaces/newlines cause an immediate
partial; a trailing word is flushed by the debounce timeout).

    python tools/preview.py "the quick brown fox"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import QUIT, Editor
from config import Config
from display.mock import MockDisplay
from editor.buffer import TextBuffer
from editor.modal import Mode, ModalEditor
from editor.refresh import RefreshController

DEFAULT_TEXT = "the quick brown fox jumps\nover the lazy dog"


class _Clock:
    def __init__(self):
        self.now_ms = 0

    def advance(self, ms):
        self.now_ms += ms


class _ScriptedKeyboard:
    """Plays (advance_ms, value) steps; value is a char, None (timeout), or QUIT."""

    def __init__(self, clock, steps):
        self._clock = clock
        self._steps = steps
        self._i = 0

    def next(self, timeout_ms):
        advance, value = self._steps[self._i]
        self._i += 1
        self._clock.advance(advance)
        return value

    def drain(self, timeout_ms):
        advance, value = self._steps[self._i]
        self._i += 1
        self._clock.advance(advance)
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        return [value]


def _steps_for(text, per_key_ms=80, debounce_ms=400):
    steps = [(per_key_ms, ch) for ch in text]
    steps.append((debounce_ms, None))  # pause -> debounce flush of the last word
    steps.append((0, QUIT))
    return steps


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = argv[0] if argv else DEFAULT_TEXT

    config = Config()
    out_dir = Path("mock_frames")
    clock = _Clock()
    display = MockDisplay(config, output_dir=out_dir)
    editor = Editor(
        # Start in INSERT so the scripted sentence is typed, not run as commands.
        state=ModalEditor(TextBuffer(), mode=Mode.INSERT),
        controller=RefreshController(
            debounce_ms=config.debounce_ms, full_every=config.full_refresh_every
        ),
        source=_ScriptedKeyboard(clock, _steps_for(text, debounce_ms=config.debounce_ms)),
        display=display,
        now_ms=lambda: clock.now_ms,
        poll_ms=100,
    )

    editor.run()

    print(f'typed: {text!r}')
    print(f"frames written to {out_dir}/ : {len(display.log)}")
    for event in display.log:
        print(f"  {event.kind:7s} {event.duration_ms:6.1f}ms  {event.path}")


if __name__ == "__main__":
    main()
