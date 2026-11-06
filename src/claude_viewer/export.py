from __future__ import annotations

import html
import re

from claude_viewer.render import command_lines, patch_counts, tool_arg, tool_label, usage_summary
from claude_viewer.transcript import Block, Session


ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def fence(body: str, lang: str = "") -> str:
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{body.rstrip()}\n{ticks}"


def details(summary: str, body: str) -> str:
    return f"<details><summary>{html.escape(summary)}</summary>\n\n{body}\n\n</details>"


def diff_text(patch: list) -> str:
    hunks = []
    for hunk in patch:
        head = f"@@ -{hunk.get('oldStart', 0)},{hunk.get('oldLines', 0)} +{hunk.get('newStart', 0)},{hunk.get('newLines', 0)} @@"
        hunks.append("\n".join([head, *hunk.get("lines", [])]))
    return "\n".join(hunks)


def tool_markdown(block: Block) -> str:
    lines = command_lines(block)
    if lines is not None and len(lines) > 1:
        head = f"**{tool_label(block)}**\n\n" + fence("\n".join(lines), "sh")
    else:
        arg = lines[0] if lines else tool_arg(block, width=200)
        head = f"**{tool_label(block)}**" + (f" `{arg}`" if arg else "")
    if block.is_error:
        head += " *(error)*"
    if block.result is None:
        return head + "\n\n*(no result)*"
    if block.patch:
        added, removed = patch_counts(block.patch)
        return f"{head}\n\n+{added} −{removed}\n\n" + fence(diff_text(block.patch), "diff")
    lines = ANSI.sub("", block.result).rstrip().splitlines()
    if not lines:
        return head + "\n\n*(no output)*"
    return head + "\n\n" + details(f"Output ({len(lines)} lines)", fence("\n".join(lines)))


def block_markdown(block: Block) -> str:
    if block.kind == "prompt":
        return "\n".join("> " + line if line else ">" for line in block.text.splitlines())
    if block.kind == "text":
        return block.text
    if block.kind == "tool":
        return tool_markdown(block)
    if block.kind == "thinking":
        return details("Thinking", block.text)
    if block.kind == "usage":
        return f"<sub>{html.escape(usage_summary(block))}</sub>"
    if block.kind == "attachment":
        return f"*{block.text}*"
    if block.kind == "note":
        lines = block.text.splitlines() or [""]
        if len(lines) == 1:
            return f"*{lines[0]}*"
        return details(lines[0], fence("\n".join(lines[1:])))
    return block.text


def to_markdown(session: Session, usage: bool = False) -> str:
    parts = [f"# {session.title}", f"`{session.session_id}`"]
    parts.extend(block_markdown(block) for block in session.blocks if usage or block.kind != "usage")
    return "\n\n".join(parts) + "\n"
