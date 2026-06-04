"""writerdeck entry point.

Wires the editor together and runs the loop. The display backend is chosen by
flag or auto-detected (the real epd4in26 panel on a Pi, the PNG mock elsewhere).
Input always comes from an evdev keyboard -- never the terminal -- so this is
meant to run on the Pi (or any Linux box with python3-evdev and a keyboard). To
preview rendering on a laptop without hardware, use tools/preview.py instead.
"""

import argparse
import logging
import time
from datetime import datetime

from app import Editor, run_picker
from config import Config
from drafts import DraftStore
from editor.buffer import TextBuffer
from editor.modal import ModalEditor
from editor.refresh import GhostingCounter, RefreshPolicy
from picker import FilePicker


def is_raspberry_pi() -> bool:
    try:
        with open("/proc/cpuinfo") as cpuinfo:
            return "Raspberry" in cpuinfo.read()
    except OSError:
        return False


def build_display(backend: str, config: Config):
    if backend == "mock":
        from display.mock import MockDisplay

        return MockDisplay(config, output_dir="mock_frames")
    from display.epd4in26 import Epd4in26Display

    return Epd4in26Display(config)


def monotonic_ms() -> int:
    return time.monotonic_ns() // 1_000_000


def open_or_create(store: DraftStore, keyboard, display):
    """Run the launch picker; return (path, buffer) for the chosen/new draft.

    Returns (None, None) if the picker is dismissed without a choice.
    """
    picker = FilePicker(store.list(), label=lambda p: p.name)
    choice = run_picker(picker, keyboard, display, poll_ms=100)
    if choice is None:
        return None, None
    if choice is FilePicker.NEW:
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        return store.new_path(stamp), TextBuffer()
    return choice, TextBuffer.from_text(store.load(choice))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="writerdeck e-ink modal text editor")
    parser.add_argument(
        "--backend",
        choices=["auto", "mock", "epd"],
        default="auto",
        help="display backend (auto: epd on a Pi, mock otherwise)",
    )
    parser.add_argument("--device", help="evdev keyboard path (default: auto-discover)")
    parser.add_argument("-v", "--verbose", action="store_true", help="log refreshes/input")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s: %(message)s",
    )

    config = Config()
    backend = args.backend
    if backend == "auto":
        backend = "epd" if is_raspberry_pi() else "mock"

    display = build_display(backend, config)

    from input.evdev_source import EvdevKeyboard

    keyboard = EvdevKeyboard(device_path=args.device)
    store = DraftStore(config.drafts_dir, extension=config.draft_extension)

    try:
        path, buffer = open_or_create(store, keyboard, display)
        if path is None:
            return  # picker dismissed; nothing to edit

        editor = Editor(
            state=ModalEditor(buffer),  # launches in NORMAL
            policy=RefreshPolicy(debounce_ms=config.debounce_ms),
            source=keyboard,
            display=display,
            now_ms=monotonic_ms,
            poll_ms=100,  # 10Hz idle poll: fine enough to honour the debounce
            ghosting=GhostingCounter(full_every=config.full_refresh_every),
            autosave=lambda text: store.save(path, text),
        )
        editor.show()  # draw the opened draft immediately
        try:
            editor.run()
        except KeyboardInterrupt:
            pass
        finally:
            editor.flush()  # persist anything typed within the last debounce window
    finally:
        keyboard.close()
        display.sleep()


if __name__ == "__main__":
    main()
