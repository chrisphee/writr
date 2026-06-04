"""Crash-safe draft storage in a flat directory of plain-text files.

Saves are atomic: write a sibling temp file, fsync it, then rename over the
target (and fsync the directory). A power cut can never leave a half-written
draft -- the reader sees either the old file or the fully-written new one.
"""

import os
from pathlib import Path

TEXT_SUFFIXES = {".txt", ".md"}


class DraftStore:
    def __init__(self, directory, extension: str = ".md"):
        self._dir = Path(directory).expanduser()
        self._extension = extension

    def new_path(self, stamp: str) -> Path:
        return self._dir / f"{stamp}{self._extension}"

    def load(self, path) -> str:
        return Path(path).read_text(encoding="utf-8")

    def save(self, path, text: str) -> None:
        path = Path(path)
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic rename over the target
        self._fsync_dir()

    def list(self) -> list[Path]:
        if not self._dir.exists():
            return []
        drafts = [
            p for p in self._dir.iterdir() if p.is_file() and p.suffix in TEXT_SUFFIXES
        ]
        return sorted(drafts, key=lambda p: p.stat().st_mtime, reverse=True)

    def _fsync_dir(self) -> None:
        fd = os.open(str(self._dir), os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
