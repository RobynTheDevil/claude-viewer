from __future__ import annotations

import os
import subprocess

from rich.cells import cell_len
from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip

CLIP_EXE = "/mnt/c/Windows/system32/clip.exe"
MARKERS = ("⏺ ", "• ", "  ⎿  ")
MARKER_WIDTH = {"text": 2, "tool": 5, "thinking": 2, "usage": 4, "note": 2, "image": 5}


def cell_to_index(text: str, cell: int) -> int:
    pos = 0
    for i, ch in enumerate(text):
        pos += cell_len(ch)
        if pos > cell:
            return i
    return len(text)


def index_to_cell(text: str, index: int) -> int:
    return cell_len(text[:index])


def _kind(ch: str) -> int:
    if ch.isspace():
        return 0
    return 1 if ch.isalnum() or ch == "_" else 2


def next_word(text: str, col: int) -> int | None:
    n = len(text)
    if col >= n:
        return None
    kind = _kind(text[col])
    i = col
    while i < n and _kind(text[i]) == kind and kind:
        i += 1
    while i < n and text[i].isspace():
        i += 1
    return i if i < n else None


def prev_word(text: str, col: int) -> int | None:
    i = min(col, len(text)) - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0:
        return None
    kind = _kind(text[i])
    while i > 0 and _kind(text[i - 1]) == kind:
        i -= 1
    return i


def first_nonblank(text: str) -> int:
    stripped = len(text) - len(text.lstrip())
    return stripped if stripped < len(text) else 0


def marker_len(kind: str, text: str) -> int:
    for marker in MARKERS:
        if text.startswith(marker):
            return len(marker)
    width = MARKER_WIDTH.get(kind, 0)
    lead = len(text) - len(text.lstrip(" "))
    return min(width, lead)


def overlay(strip: Strip, start: int, end: int, style: Style) -> Strip:
    if end <= start:
        return strip
    if strip.cell_length < end:
        strip = strip.extend_cell_length(end)
    cuts = sorted({start, end, strip.cell_length})
    out = []
    pos = 0
    for piece in strip.divide(cuts):
        if start <= pos < end:
            piece = Strip(Segment.apply_style(list(piece), None, style), piece.cell_length)
        out.append(piece)
        pos += piece.cell_length
    return Strip.join(out)


def to_windows_clipboard(text: str) -> bool:
    if not os.environ.get("WSL_DISTRO_NAME") or not os.path.exists(CLIP_EXE):
        return False
    try:
        subprocess.run([CLIP_EXE], input=text.replace("\n", "\r\n").encode("utf-16-le"), timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return True
