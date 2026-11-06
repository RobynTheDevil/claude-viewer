from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from claude_viewer.transcript import Block

WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
FILE_TOOLS = {"Read", "Edit", "MultiEdit", "Write"}


def file_target(block: Block) -> tuple[str, int] | None:
    if block.kind != "tool" or block.tool not in FILE_TOOLS:
        return None
    path = block.input.get("file_path")
    if not isinstance(path, str) or not path:
        return None
    line = 1
    if block.tool == "Read":
        offset = block.input.get("offset")
        if isinstance(offset, int) and offset > 0:
            line = offset
        elif block.file and isinstance(block.file.get("startLine"), int):
            line = block.file["startLine"]
    elif block.tool != "Write" and block.patch:
        hunk = block.patch[0]
        lead = 0
        for text in hunk.get("lines", []):
            if text[:1] in ("+", "-"):
                break
            lead += 1
        line = hunk.get("newStart", 1) + lead
    return path, max(1, line)


def local_path(path: str) -> str:
    if WINDOWS_PATH.match(path) and shutil.which("wslpath"):
        result = subprocess.run(["wslpath", "-u", path], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return path


def editor_command(path: str, line: int, env: dict | None = None) -> list[str]:
    env = os.environ if env is None else env
    for key in ("VISUAL", "EDITOR"):
        if env.get(key, "").strip():
            argv = shlex.split(env[key])
            break
    else:
        argv = ["nvim"] if shutil.which("nvim") else ["less"]
    if Path(argv[0]).name in ("code", "code-insiders", "codium"):
        return [*argv, "-g", f"{path}:{line}"]
    return [*argv, f"+{line}", path]
