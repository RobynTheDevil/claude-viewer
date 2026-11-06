from __future__ import annotations

import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import PurePath

from pygments.lexer import Lexer
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.util import ClassNotFound
from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.markdown import Markdown
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from claude_viewer.access import HEREDOC, is_write
from claude_viewer.shell import STRING, highlight_shell
from claude_viewer.transcript import Block, Session

LABELS = {"Edit": "Update", "MultiEdit": "Update", "Grep": "Search", "Glob": "Search", "Task": "Agent"}
ARG_KEYS = ("command", "file_path", "notebook_path", "pattern", "url", "query", "description", "skill", "prompt")
PREVIEW_LINES = 3

DOT = "• "
TOOL_DOT = "• "
SHELL_PROMPT = "$ "
ELBOW = " ⎿ "
PROMPT_STYLE = "on grey15"
ADD_STYLE = "on #16351f"
DEL_STYLE = "on #3d1a1d"
SYNTAX_THEME = "monokai"
SHELL_LEXERS = {"Bash": "bash", "PowerShell": "powershell"}
INTERPRETERS = {
    "python": "python", "python3": "python", "py": "python", "node": "javascript",
    "deno": "javascript", "bun": "javascript", "ruby": "ruby", "perl": "perl", "php": "php",
    "bash": "bash", "sh": "bash", "zsh": "bash", "pwsh": "powershell",
    "powershell": "powershell", "powershell.exe": "powershell", "psql": "sql",
    "sqlite3": "sql", "mysql": "sql", "lua": "lua",
}
REDIRECT_TARGET = re.compile(r"(?:^|[^0-9&>])>>?\s*(['\"]?)([^\s'\";|&<>]+)\1")
GAP_SHOWN = 5.0


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
    if width and len(first) > width:
        first = first[: width - 1] + "…"
    elif len(lines) > 1:
        first += " …"
    return first


def command_lines(block: Block) -> list[str] | None:
    command = block.input.get("command")
    if not isinstance(command, str):
        return None
    return command.strip().splitlines() or [""]


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


def wrap_cuts(plain: str, width: int) -> list[int]:
    cuts = []
    used = cell_len(plain) - cell_len(plain.lstrip(" "))
    for token in re.finditer(r"(\S+)(\s*)", plain):
        word = cell_len(token.group(1))
        if used + word > width:
            if word <= width:
                cuts.append(token.start())
                used = 0
            else:
                for i in range(token.start(), token.end(1)):
                    w = cell_len(plain[i])
                    if used + w > width:
                        cuts.append(i)
                        used = 0
                    used += w
                used += cell_len(token.group(2))
                continue
        used += word + cell_len(token.group(2))
    return cuts


class Folded:
    def __init__(self, text: Text) -> None:
        self.text = text

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        width = max(1, options.max_width)
        for line in self.text.split("\n", allow_blank=True):
            cuts = wrap_cuts(line.plain, width)
            for piece in line.divide(cuts) if cuts else [line]:
                piece.no_wrap = True
                piece.overflow = "crop"
                piece.end = "\n"
                yield piece


def marked(marker: str, marker_style: str, body: RenderableType) -> Table:
    grid = Table.grid()
    grid.add_column(width=len(marker), no_wrap=True)
    grid.add_column(ratio=1, overflow="fold")
    grid.add_row(Text(marker, style=marker_style), body)
    return grid


@lru_cache(maxsize=None)
def _lexer_for_name(name: str) -> Lexer | None:
    try:
        lexer = get_lexer_for_filename(name, stripnl=False, ensurenl=True)
    except ClassNotFound:
        return None
    return None if isinstance(lexer, TextLexer) else lexer


@lru_cache(maxsize=None)
def lexer_named(name: str) -> Lexer:
    return get_lexer_by_name(name, stripnl=False, ensurenl=True)


def heredoc_lexer(opener: str) -> Lexer | None:
    before = opener[: HEREDOC.search(opener).start()]
    target = REDIRECT_TARGET.search(before)
    if target and target.group(2) != "/dev/null":
        return lexer_for(target.group(2))
    for word in re.split(r"[\s;|&()]+", before):
        name = INTERPRETERS.get(os.path.basename(word))
        if name:
            return lexer_named(name)
    return None


def highlight_command(lines: list[str], tool: str) -> list[Text]:
    if tool in SHELL_LEXERS and tool != "Bash":
        return highlight_lines(lines, lexer_named(SHELL_LEXERS[tool]))
    out: list[Text] = []
    shell: list[str] = []
    body: list[str] = []
    lexer = None
    ending = None
    for line in lines:
        if ending is None:
            shell.append(line)
            match = HEREDOC.search(line)
            if match:
                ending = match.group(2)
                lexer = heredoc_lexer(line)
                out.extend(highlight_shell(shell))
                shell = []
        elif line.strip() == ending:
            out.extend(highlight_lines(body, lexer))
            out.append(Text(line, STRING))
            body = []
            ending = None
        else:
            body.append(line)
    out.extend(highlight_lines(body, lexer) if ending is not None else highlight_shell(shell))
    return out


def lexer_for(path: str) -> Lexer | None:
    if not path:
        return None
    name = PurePath(path.replace("\\", "/")).name
    suffix = PurePath(name).suffix.lower()
    return _lexer_for_name(f"x{suffix}" if suffix else name)


@lru_cache(maxsize=None)
def _token_style(token_type) -> Style | None:
    style = Syntax.get_theme(SYNTAX_THEME).get_style_for_token(token_type)
    if style.color is None and not style.bold and not style.italic:
        return None
    return Style(color=style.color, bold=style.bold or None, italic=style.italic or None)


def highlight_lines(lines: list[str], lexer: Lexer | None) -> list[Text]:
    if lexer is None:
        return [Text(line) for line in lines]
    out = [Text()]
    for token_type, value in lexer.get_tokens("\n".join(lines)):
        style = _token_style(token_type)
        for k, part in enumerate(value.split("\n")):
            if k:
                out.append(Text())
            if part:
                out[-1].append(part, style)
    if len(out) < len(lines) or any(t.plain != line for t, line in zip(out, lines)):
        return [Text(line) for line in lines]
    return out[: len(lines)]


def diff_line(prefix: str, body: Text, style: str = "") -> Text:
    line = Text(prefix)
    line.append_text(body)
    if style:
        line.stylize(style, 0, len(line))
    return line


def diff(patch: list, path: str = "") -> Text:
    out = Text()
    for n, hunk in enumerate(patch):
        if n:
            out.append("     ⋮\n", style="dim")
        lines = hunk.get("lines", [])
        old_code = [line[1:] for line in lines if line[:1] != "+"]
        new_code = [line[1:] for line in lines if line[:1] != "-"]
        lexer = lexer_for(path)
        old_hl = iter(highlight_lines(old_code, lexer))
        new_hl = iter(highlight_lines(new_code, lexer))
        old = hunk.get("oldStart", 0)
        new = hunk.get("newStart", 0)
        for line in lines:
            sign = line[:1]
            if sign == "+":
                out.append_text(diff_line(f"{new:>5} +", next(new_hl), ADD_STYLE))
                new += 1
            elif sign == "-":
                out.append_text(diff_line(f"{old:>5} -", next(old_hl), DEL_STYLE))
                old += 1
            else:
                next(old_hl)
                out.append_text(diff_line(f"{new:>5}  ", next(new_hl)))
                old += 1
                new += 1
            out.append("\n")
    out.rstrip()
    return out


def read_body(block: Block) -> Text | None:
    file = block.file or {}
    content = file.get("content")
    if not isinstance(content, str) or block.is_error:
        return None
    path = file.get("filePath") or block.input.get("file_path", "")
    lexer = lexer_for(path)
    if lexer is None:
        return None
    start = file.get("startLine") if isinstance(file.get("startLine"), int) else 1
    lines = content.rstrip("\n").split("\n")
    out = Text()
    for n, line in enumerate(highlight_lines(lines, lexer)):
        if n:
            out.append("\n")
        out.append(f"{start + n:>5}  ", style="dim")
        out.append_text(line)
    return out


def header_plain(block: Block) -> str:
    lines = command_lines(block)
    arg = "\n".join(lines) if lines is not None else tool_arg(block)
    return tool_label(block) + (f"({arg})" if arg else "")


def tool_header(block: Block, suffix: str = "") -> Table:
    if block.is_error:
        style = "red"
    elif block.result is None:
        style = "dim"
    else:
        style = "yellow" if is_write(block) else "cyan"
    lines = command_lines(block)
    if lines is not None and block.tool == "Bash":
        return marked(SHELL_PROMPT, "bold " + style, Folded(command_text(block, lines, suffix)))
    text = Text()
    text.append(tool_label(block), "bold " + ("yellow" if is_write(block) else "cyan"))
    if lines is None:
        arg = tool_arg(block, width=0)
        if arg:
            text.append(f"({arg})")
        text.append(suffix, style="dim")
        return marked(TOOL_DOT, style, text)
    text.append(suffix, style="dim")
    text.append("\n")
    text.append_text(command_text(block, lines))
    return marked(TOOL_DOT, style, Folded(text))


def command_text(block: Block, lines: list[str], suffix: str = "") -> Text:
    shown = lines if not block.collapsed else lines[:PREVIEW_LINES]
    text = Text()
    for n, line in enumerate(highlight_command(lines, block.tool)[: len(shown)]):
        if n:
            text.append("\n")
        text.append_text(line)
        if n == 0:
            text.append(suffix, style="dim")
    if len(lines) > len(shown):
        text.append(f"\n… +{len(lines) - len(shown)} lines", style="dim")
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
        return marked(ELBOW, "dim", Group(summary, diff(block.patch, path)))
    lines = block.result.rstrip().splitlines()
    if not block.collapsed and block.tool == "Read":
        code = read_body(block)
        if code is not None:
            return marked(ELBOW, "dim", code)
    if not block.collapsed:
        return marked(ELBOW, "dim", output("\n".join(lines) or "(no output)", style))
    if block.tool == "Read" and not block.is_error:
        return marked(ELBOW, "dim", Text(f"Read {len(lines)} lines", style="dim"))
    count = f"> {len(lines)} line{'s' * (len(lines) != 1)}" if lines else "> no output"
    return Text(count, style=style or "dim")


def span_label(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 10:
        return f"{seconds:.1f}s"
    total = round(seconds)
    if total < 60:
        return f"{total}s"
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m{secs:02d}s" if secs else f"{minutes}m"


def time_suffix(block: Block) -> str:
    parts = []
    if block.kind == "prompt" and block.time is not None:
        parts.append(datetime.fromtimestamp(block.time).strftime("%H:%M:%S"))
    if block.kind == "tool" and block.duration is not None:
        parts.append(span_label(block.duration))
    if block.gap is not None and block.gap > GAP_SHOWN:
        parts.append("+" + span_label(block.gap))
    return "  " + " ".join(parts) if parts else ""


def spaced(block: Block) -> bool:
    return not (block.collapsible and block.collapsed)


def render_block(block: Block, show_times: bool = False) -> RenderableType:
    suffix = time_suffix(block) if show_times and block.kind in ("prompt", "tool") else ""
    if block.kind == "prompt":
        first, newline, rest = block.text.partition("\n")
        text = Text("> " + first, style=PROMPT_STYLE)
        if suffix:
            text.append(suffix, style="dim")
        if newline:
            text.append("\n" + rest)
        return text
    if block.kind == "text":
        return marked(DOT, "white", Markdown(block.text))
    if block.kind == "tool":
        return Group(tool_header(block, suffix), tool_body(block))
    if block.kind == "thinking":
        head = Text("Thinking…", style="dim italic")
        if block.collapsed:
            return marked(TOOL_DOT, "white", head)
        return marked(TOOL_DOT, "white", Group(head, Text(block.text, style="dim italic")))
    if block.kind == "usage":
        head = Text(usage_summary(block), style="dim")
        if block.collapsed:
            return marked(TOOL_DOT, "dim", head)
        rows = Text("\n".join(f"{k}: {v}" for k, v in (block.usage or {}).items() if isinstance(v, (int, str))), style="dim")
        return marked(TOOL_DOT, "dim", Group(head, rows))
    if block.kind == "image":
        return marked(ELBOW, "dim", Text(block.text, style="dim"))
    if block.kind == "note":
        lines = block.text.splitlines() or [""]
        head = Text("※ " + lines[0], style="dim")
        if block.collapsed or len(lines) == 1:
            return head
        return Group(head, marked(" ", "", Text("\n".join(lines[1:]), style="dim")))
    return Text(block.text)


def print_session(session: Session, console: Console | None = None, usage: bool = False) -> None:
    console = console or Console()
    console.print(Text(session.title, style="bold"))
    console.print(Text(session.session_id, style="dim"))
    previous = None
    for block in session.blocks:
        if block.kind == "usage" and not usage:
            continue
        if previous is None or spaced(previous):
            console.print()
        console.print(render_block(block))
        previous = block
