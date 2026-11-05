from __future__ import annotations

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from claude_viewer.transcript import Block, Session

LABELS = {"Edit": "Update", "MultiEdit": "Update", "Grep": "Search", "Glob": "Search", "Task": "Agent"}
ARG_KEYS = ("command", "file_path", "notebook_path", "pattern", "url", "query", "description", "skill", "prompt")
PREVIEW_LINES = 3

DOT = "⏺ "
ELBOW = "  ⎿  "
PROMPT_STYLE = "on grey15"
ADD_STYLE = "on #16351f"
DEL_STYLE = "on #3d1a1d"


def tool_label(block: Block) -> str:
    return LABELS.get(block.tool, block.tool)


def tool_arg(block: Block, width: int = 100) -> str:
    value = ""
    for key in ARG_KEYS:
        if isinstance(block.input.get(key), str):
            value = block.input[key]
            break
    else:
        for v in block.input.values():
            if isinstance(v, str):
                value = v
                break
    lines = value.strip().splitlines()
    first = lines[0] if lines else ""
    if len(first) > width:
        first = first[: width - 1] + "…"
    elif len(lines) > 1:
        first += " …"
    return first


def patch_counts(patch: list) -> tuple[int, int]:
    added = removed = 0
    for hunk in patch:
        for line in hunk.get("lines", []):
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
    return added, removed


def short_number(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def usage_summary(block: Block) -> str:
    u = block.usage or {}
    parts = [block.model] if block.model else []
    parts.append(f"{short_number(u.get('input_tokens', 0))} in")
    parts.append(f"{short_number(u.get('output_tokens', 0))} out")
    if u.get("cache_read_input_tokens"):
        parts.append(f"{short_number(u['cache_read_input_tokens'])} cache read")
    if u.get("cache_creation_input_tokens"):
        parts.append(f"{short_number(u['cache_creation_input_tokens'])} cache write")
    return " · ".join(parts)


def marked(marker: str, marker_style: str, body: RenderableType) -> Table:
    grid = Table.grid()
    grid.add_column(width=len(marker), no_wrap=True)
    grid.add_column(ratio=1)
    grid.add_row(Text(marker, style=marker_style), body)
    return grid


def diff(patch: list) -> Text:
    out = Text()
    for n, hunk in enumerate(patch):
        if n:
            out.append("     ⋮\n", style="dim")
        old = hunk.get("oldStart", 0)
        new = hunk.get("newStart", 0)
        for line in hunk.get("lines", []):
            sign, body = line[:1], line[1:]
            if sign == "+":
                out.append(f"{new:>5} +{body}\n", style=ADD_STYLE)
                new += 1
            elif sign == "-":
                out.append(f"{old:>5} -{body}\n", style=DEL_STYLE)
                old += 1
            else:
                out.append(f"{new:>5}  {body}\n")
                old += 1
                new += 1
    out.rstrip()
    return out


def tool_header(block: Block) -> Text:
    style = "red" if block.is_error else ("green" if block.result is not None else "dim")
    text = Text(DOT, style=style)
    text.append(tool_label(block), style="bold")
    arg = tool_arg(block)
    if arg:
        text.append(f"({arg})")
    return text


def output(text: str, style: str = "") -> Text:
    return Text.from_ansi(text, style=style)


def tool_body(block: Block) -> RenderableType:
    if block.result is None:
        return marked(ELBOW, "dim", Text("(no result)", style="dim"))
    style = "red" if block.is_error else ""
    if block.patch:
        added, removed = patch_counts(block.patch)
        path = block.input.get("file_path", "")
        summary = Text(f"Updated {path} with {added} addition{'s' * (added != 1)} and {removed} removal{'s' * (removed != 1)}")
        if block.collapsed:
            return marked(ELBOW, "dim", summary)
        return marked(ELBOW, "dim", Group(summary, diff(block.patch)))
    lines = block.result.rstrip().splitlines()
    if not block.collapsed:
        return marked(ELBOW, "dim", output("\n".join(lines) or "(no output)", style))
    if block.tool == "Read" and not block.is_error:
        return marked(ELBOW, "dim", Text(f"Read {len(lines)} lines", style="dim"))
    preview = output("\n".join(lines[:PREVIEW_LINES]) or "(no output)", style)
    if len(lines) > PREVIEW_LINES:
        preview.append(f"\n… +{len(lines) - PREVIEW_LINES} lines", style="dim")
    return marked(ELBOW, "dim", preview)


def render_block(block: Block) -> RenderableType:
    if block.kind == "prompt":
        return Text("> " + block.text, style=PROMPT_STYLE)
    if block.kind == "text":
        return marked(DOT, "white", Markdown(block.text))
    if block.kind == "tool":
        return Group(tool_header(block), tool_body(block))
    if block.kind == "thinking":
        head = Text("✻ Thinking…", style="dim italic")
        if block.collapsed:
            return head
        return Group(head, marked("  ", "", Text(block.text, style="dim italic")))
    if block.kind == "usage":
        head = Text("  · " + usage_summary(block), style="dim")
        if block.collapsed:
            return head
        rows = Text("\n".join(f"{k}: {v}" for k, v in (block.usage or {}).items() if isinstance(v, (int, str))), style="dim")
        return Group(head, marked("    ", "", rows))
    if block.kind == "image":
        return marked(ELBOW, "dim", Text(block.text, style="dim"))
    if block.kind == "note":
        lines = block.text.splitlines() or [""]
        head = Text("※ " + lines[0], style="dim")
        if block.collapsed or len(lines) == 1:
            return head
        return Group(head, marked("  ", "", Text("\n".join(lines[1:]), style="dim")))
    return Text(block.text)


def print_session(session: Session, console: Console | None = None, usage: bool = True) -> None:
    console = console or Console()
    console.print(Text(session.title, style="bold"))
    console.print(Text(session.session_id, style="dim"))
    for block in session.blocks:
        if block.kind == "usage" and not usage:
            continue
        console.print()
        console.print(render_block(block))
