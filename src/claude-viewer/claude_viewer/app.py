from __future__ import annotations

import re
import subprocess
from bisect import bisect_left, bisect_right
from pathlib import Path

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.geometry import Size
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from claude_viewer.editor import editor_command, file_target, local_path
from claude_viewer.render import render_block, tool_header
from claude_viewer.selection import (
    cell_to_index,
    first_nonblank,
    index_to_cell,
    marker_len,
    next_word,
    overlay,
    prev_word,
    to_windows_clipboard,
)
from claude_viewer.transcript import Block, Session, SessionInfo, parse

GUTTER = 2
CURSOR = Segment("▌ ", Style(color="cyan", bold=True))
PLAIN = Segment("  ")
FILTERS = ("all", "read-only", "changes")
MATCH = Style(bgcolor="#5f4b00")
CURRENT_MATCH = Style(bgcolor="#d7af00", color="black")
CARET = Style(reverse=True)
SELECTED = Style(bgcolor="#264f78")


def searchable(block: Block) -> str:
    parts = [block.text, tool_header(block).plain if block.kind == "tool" else "", block.result or ""]
    parts.extend(v for v in block.input.values() if isinstance(v, str))
    return "\n".join(parts)


def compile_query(query: str) -> re.Pattern:
    return re.compile(query, 0 if any(c.isupper() for c in query) else re.I)


def highlight(strip: Strip, pattern: re.Pattern, style: Style) -> Strip:
    text = strip.text
    spans = [(index_to_cell(text, m.start()), index_to_cell(text, m.end())) for m in pattern.finditer(text) if m.end() > m.start()]
    if not spans:
        return strip
    cuts = sorted({c for span in spans for c in span} | {strip.cell_length})
    out = []
    pos = 0
    for piece in strip.divide(cuts):
        if any(start <= pos < end for start, end in spans):
            piece = Strip(Segment.apply_style(list(piece), None, style), piece.cell_length)
        out.append(piece)
        pos += piece.cell_length
    return Strip.join(out)


class TranscriptView(ScrollView, can_focus=True):
    DEFAULT_CSS = """
    TranscriptView {
        overflow-x: hidden;
        scrollbar-gutter: stable;
    }
    """

    BINDINGS = [
        Binding("j,down", "caret(1)", "Line down", show=False),
        Binding("k,up", "caret(-1)", "Line up", show=False),
        Binding("h,left", "column(-1)", "Left", show=False),
        Binding("l,right", "column(1)", "Right", show=False),
        Binding("w", "word(1)", "Next word", show=False),
        Binding("b", "word(-1)", "Previous word", show=False),
        Binding("0", "line_start", "Line start", show=False),
        Binding("circumflex_accent", "first_nonblank", "First non-blank", show=False),
        Binding("dollar_sign", "line_end", "Line end", show=False),
        Binding("ctrl+e,e", "scroll_rows(1)", "Scroll down", show=False),
        Binding("ctrl+y", "scroll_rows(-1)", "Scroll up", show=False),
        Binding("v", "visual('visual')", "Visual", show=False),
        Binding("V", "visual('line')", "Visual line", show=False),
        Binding("y", "yank", "Yank", show=False),
        Binding("ctrl+d,d", "page(0.5)", "Half page down", show=False),
        Binding("ctrl+u,u", "page(-0.5)", "Half page up", show=False),
        Binding("pagedown,space,ctrl+f", "page(1)", "Page down", show=False),
        Binding("pageup,ctrl+b", "page(-1)", "Page up", show=False),
        Binding("right_curly_bracket", "move(1)", "Next block", show=False),
        Binding("left_curly_bracket", "move(-1)", "Previous block", show=False),
        Binding("home,less_than_sign", "jump(0)", "Top", show=False),
        Binding("G,end,greater_than_sign", "jump(-1)", "Bottom", show=False),
        Binding("enter", "toggle", "Toggle"),
        Binding("o", "block(False)", "Expand"),
        Binding("x", "block(True)", "Collapse"),
        Binding("O", "group(False)", "Expand tool"),
        Binding("X", "group(True)", "Collapse tool"),
        Binding("E", "every(False)", "Expand all"),
        Binding("C", "every(True)", "Collapse all"),
        Binding("f", "cycle_filter", "Filter"),
        Binding("U", "toggle_usage", "Usage"),
        Binding("t", "toggle_times", "Times"),
    ]

    PREFIXES = {
        "g": {"g": "jump(0)", "f": "open_file"},
        "left_square_bracket": {"left_square_bracket": "prompt(-1)"},
        "right_square_bracket": {"right_square_bracket": "prompt(1)"},
    }
    PREFIX_TIMEOUT = 1.0

    cursor = reactive(0)
    mode = reactive("normal")

    class Notice(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, blocks: list[Block], show_usage: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self.blocks = blocks
        self.show_usage = show_usage
        self.filter = "all"
        self.show_times = False
        self.shown: list[bool] = []
        self._compute_visible()
        self.prompts = [i for i, b in enumerate(blocks) if b.kind == "prompt"]
        self._cache: dict[int, list[Strip]] = {}
        self._width = 0
        self._offsets: list[int] = []
        self._total = 0
        self._pending: str | None = None
        self._pending_timer = None
        self._scrolling = False
        self._search_text: dict[int, str] = {}
        self.pattern: re.Pattern | None = None
        self.caret_line = 0
        self.caret_col = 0
        self._want_col = 0
        self.anchor = (0, 0)

    def _passes_filter(self, block: Block) -> bool:
        if self.filter == "all" or block.kind in ("prompt", "text"):
            return True
        if block.kind != "tool":
            return False
        return bool(block.patch) == (self.filter == "changes")

    def _compute_visible(self) -> None:
        shown = [b.kind != "usage" and self._passes_filter(b) for b in self.blocks]
        messages = {b.msg_id for b, on in zip(self.blocks, shown) if on and b.msg_id}
        for i, b in enumerate(self.blocks):
            if b.kind == "usage":
                shown[i] = self.show_usage and (self.filter == "all" or b.msg_id in messages)
        self.shown = shown

    def _next_visible(self, i: int, step: int) -> int | None:
        i += step
        while 0 <= i < len(self.blocks):
            if self.shown[i]:
                return i
            i += step
        return None

    def _strips(self, i: int) -> list[Strip]:
        strips = self._cache.get(i)
        if strips is None:
            if not self.shown[i]:
                strips = []
            else:
                console = self.app.console
                options = console.options.update_width(self._width)
                lines = console.render_lines(render_block(self.blocks[i], self.show_times), options, pad=False)
                strips = [Strip(line) for line in lines]
                following = self._next_visible(i, 1)
                if following is None or self.blocks[following].kind != "usage":
                    strips.append(Strip.blank(0))
            self._cache[i] = strips
        return strips

    def _layout(self) -> None:
        width = max(10, self.scrollable_content_region.width - GUTTER)
        if width != self._width:
            self._width = width
            self._cache.clear()
        offsets = []
        total = 0
        for i in range(len(self.blocks)):
            offsets.append(total)
            total += len(self._strips(i))
        self._offsets = offsets
        self._total = total
        self.virtual_size = Size(width + GUTTER, total)
        self.refresh()

    def on_resize(self, event: events.Resize) -> None:
        if self.blocks:
            anchor = self.cursor
            row = self._offsets[anchor] - self.scroll_offset.y if self._offsets else 0
            width = self._width
            self._layout()
            self._scroll(self._offsets[anchor] - row)
            if width != self._width:
                self._caret_to_block()

    def render_line(self, y: int) -> Strip:
        width = self.scrollable_content_region.width
        line = self.scroll_offset.y + y
        if not self._offsets or line >= self._total:
            return Strip.blank(width)
        i = bisect_right(self._offsets, line) - 1
        strip = self._strips(i)[line - self._offsets[i]]
        if self.pattern is not None:
            strip = highlight(strip, self.pattern, CURRENT_MATCH if i == self.cursor else MATCH)
        if self.mode != "normal":
            span = self._selected_span(line, strip.text)
            if span is not None:
                start, end = index_to_cell(strip.text, span[0]), index_to_cell(strip.text, span[1])
                strip = overlay(strip, start, max(end, start + 1), SELECTED)
        if line == self.caret_line:
            start = index_to_cell(strip.text, self.caret_col)
            strip = overlay(strip, start, start + 1, CARET)
        gutter = CURSOR if i == self.cursor else PLAIN
        return Strip([gutter, *strip], GUTTER + strip.cell_length).crop_extend(0, width, None)

    def watch_cursor(self) -> None:
        self.refresh()

    def watch_mode(self) -> None:
        self.refresh()

    def _line_text(self, line: int) -> str:
        i = self._block_at(line)
        strips = self._strips(i)
        return strips[line - self._offsets[i]].text if strips else ""

    def _scroll_to_caret(self) -> None:
        view = self.scrollable_content_region.height
        sy = round(self.scroll_offset.y)
        if self.caret_line < sy:
            self._scroll(self.caret_line)
        elif self.caret_line >= sy + view:
            self._scroll(self.caret_line - view + 1)

    def _put_caret(self, line: int, col: int | None = None, follow: bool = True) -> None:
        if self._total == 0:
            return
        line = max(0, min(line, self._total - 1))
        text = self._line_text(line)
        if col is None:
            col = self._want_col
        self.caret_line = line
        self.caret_col = max(0, min(col, len(text) - 1))
        self.cursor = self._block_at(line)
        if follow:
            self._scroll_to_caret()
        self.refresh()

    def _caret_to_block(self) -> None:
        if self._offsets:
            self._want_col = 0
            self.caret_line = self._offsets[self.cursor]
            self.caret_col = 0
            self.refresh()

    def action_caret(self, rows: int) -> None:
        self._put_caret(self.caret_line + rows)

    def action_column(self, step: int) -> None:
        self._want_col = max(0, self.caret_col + step)
        self._put_caret(self.caret_line, self._want_col)
        self._want_col = self.caret_col

    def action_line_start(self) -> None:
        self._want_col = 0
        self._put_caret(self.caret_line, 0)

    def action_first_nonblank(self) -> None:
        self._want_col = first_nonblank(self._line_text(self.caret_line))
        self._put_caret(self.caret_line, self._want_col)

    def action_line_end(self) -> None:
        self._want_col = 1 << 30
        self._put_caret(self.caret_line)

    def action_word(self, step: int) -> None:
        line, col = self.caret_line, self.caret_col
        text = self._line_text(line)
        found = next_word(text, col) if step > 0 else prev_word(text, col)
        while found is None:
            line += step
            if not 0 <= line < self._total:
                return
            text = self._line_text(line)
            if not text.strip():
                continue
            found = first_nonblank(text) if step > 0 else prev_word(text, len(text))
        self._want_col = found
        self._put_caret(line, found)

    def action_visual(self, mode: str) -> None:
        if self.mode == mode:
            self.mode = "normal"
        else:
            if self.mode == "normal":
                self.anchor = (self.caret_line, self.caret_col)
            self.mode = mode

    def _selection(self) -> tuple[tuple[int, int], tuple[int, int]]:
        a, b = sorted([self.anchor, (self.caret_line, self.caret_col)])
        return a, b

    def _selected_span(self, line: int, text: str) -> tuple[int, int] | None:
        (l1, c1), (l2, c2) = self._selection()
        if not l1 <= line <= l2:
            return None
        if self.mode == "line":
            return 0, len(text)
        start = c1 if line == l1 else 0
        end = c2 + 1 if line == l2 else len(text)
        return start, min(end, len(text)) if text else start

    def selected_text(self) -> str:
        (l1, c1), (l2, c2) = self._selection()
        out = []
        for line in range(l1, l2 + 1):
            text = self._line_text(line)
            kind = self.blocks[self._block_at(line)].kind
            start, end = 0, len(text)
            if self.mode == "visual":
                if line == l1:
                    start = c1
                if line == l2:
                    end = c2 + 1
            start = max(start, marker_len(kind, text))
            out.append(text[start:end].rstrip())
        return "\n".join(out)

    def action_yank(self) -> None:
        if self.mode == "normal":
            return
        text = self.selected_text()
        (l1, c1), _ = self._selection()
        self.app.copy_to_clipboard(text)
        to_windows_clipboard(text)
        lines = text.count("\n") + 1
        col = c1 if self.mode == "visual" else self.caret_col
        self.mode = "normal"
        self._put_caret(l1, col)
        self.post_message(self.Notice(f"{lines} line{'s' * (lines != 1)} copied"))

    def _scroll(self, y: int) -> None:
        self._scrolling = True
        try:
            self.scroll_to(y=max(0, y), animate=False, immediate=True)
        finally:
            self._scrolling = False

    def _block_at(self, line: int) -> int:
        if self._total == 0:
            return self.cursor
        line = max(0, min(line, self._total - 1))
        return bisect_right(self._offsets, line) - 1

    def _show_cursor(self) -> None:
        top = self._offsets[self.cursor]
        height = len(self._strips(self.cursor))
        view = self.scrollable_content_region.height
        sy = self.scroll_offset.y
        if top < sy:
            self._scroll(top)
        elif top + min(height, view) > sy + view:
            self._scroll(top + min(height, view) - view)

    def _clamp_cursor(self) -> None:
        if not self._offsets:
            return
        sy = round(self.scroll_offset.y)
        view = self.scrollable_content_region.height
        if self.caret_line < sy:
            self._put_caret(sy, follow=False)
        elif self.caret_line >= sy + view:
            self._put_caret(sy + view - 1, follow=False)

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        if not self._scrolling:
            self._clamp_cursor()

    def action_scroll_rows(self, rows: int) -> None:
        if self.blocks:
            self._scroll(self.scroll_offset.y + rows)
            self._clamp_cursor()

    def action_page(self, fraction: float) -> None:
        if not self.blocks:
            return
        view = self.scrollable_content_region.height
        sy = self.scroll_offset.y
        rows = int(view * fraction) or (1 if fraction > 0 else -1)
        self._scroll(sy + rows)
        moved = self.scroll_offset.y - sy
        self._put_caret(self.caret_line + (moved or rows))

    def action_prompt(self, step: int) -> None:
        if not self.prompts:
            self.post_message(self.Notice("no prompts"))
            return
        if step > 0:
            k = bisect_right(self.prompts, self.cursor)
        else:
            k = bisect_left(self.prompts, self.cursor) - 1
        if not 0 <= k < len(self.prompts):
            self.post_message(self.Notice("last prompt" if step > 0 else "first prompt"))
            return
        self.go_prompt(k)

    def go_prompt(self, k: int) -> None:
        self.cursor = self.prompts[k]
        self._scroll(self._offsets[self.cursor])
        self._caret_to_block()

    @property
    def current_prompt(self) -> int:
        return max(0, bisect_right(self.prompts, self.cursor) - 1)

    def action_open_file(self) -> None:
        if not self.blocks:
            return
        target = file_target(self.blocks[self.cursor])
        if target is None:
            return
        path = local_path(target[0])
        if not Path(path).is_file():
            self.post_message(self.Notice(f"no such file: {path}"))
            return
        command = editor_command(path, target[1])
        try:
            with self.app.suspend():
                subprocess.run(command)
        except SuspendNotSupported:
            self.post_message(self.Notice("cannot suspend here: " + " ".join(command)))
        except OSError as err:
            self.post_message(self.Notice(f"{command[0]}: {err.strerror}"))
        self.refresh()

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_timer = None

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("escape", "q") and self.mode != "normal":
            self.mode = "normal"
            event.stop()
            event.prevent_default()
            return
        if self._pending is not None:
            first = self._pending
            if self._pending_timer is not None:
                self._pending_timer.stop()
            self._clear_pending()
            event.stop()
            event.prevent_default()
            action = self.PREFIXES[first].get(event.key)
            if action:
                await self.run_action(action)
        elif event.key in self.PREFIXES:
            self._pending = event.key
            self._pending_timer = self.set_timer(self.PREFIX_TIMEOUT, self._clear_pending)
            event.stop()
            event.prevent_default()

    def _refresh_blocks(self, changed: list[int]) -> None:
        anchor = self.cursor
        row = self._offsets[anchor] - self.scroll_offset.y
        for i in changed:
            self._cache.pop(i, None)
        self._layout()
        self._scroll(self._offsets[anchor] - row)
        self._show_cursor()
        self._caret_to_block()

    def _set_collapsed(self, indexes, collapsed: bool) -> None:
        changed = []
        for i in indexes:
            block = self.blocks[i]
            if block.collapsible and block.collapsed != collapsed:
                block.collapsed = collapsed
                changed.append(i)
        if changed:
            self._refresh_blocks(changed)

    def action_move(self, step: int) -> None:
        if self.blocks:
            i = self._next_visible(self.cursor, step)
            if i is not None:
                self.cursor = i
            self._show_cursor()
            self._caret_to_block()

    def action_jump(self, index: int) -> None:
        if self.blocks:
            if index < 0:
                i = self._next_visible(len(self.blocks), -1)
            else:
                i = self._next_visible(index - 1, 1)
            if i is not None:
                self.cursor = i
            self._show_cursor()
            self._caret_to_block()

    @property
    def visible_count(self) -> int:
        return sum(self.shown)

    @property
    def position(self) -> int:
        return sum(self.shown[: self.cursor + 1])

    def _relayout(self) -> None:
        anchor = self.cursor
        row = self._offsets[anchor] - self.scroll_offset.y if self._offsets else 0
        self._compute_visible()
        if not self.shown[anchor]:
            after = self._next_visible(anchor, 1)
            anchor = after if after is not None else self._next_visible(anchor, -1)
        self._cache.clear()
        self._layout()
        if anchor is not None:
            self.cursor = anchor
            self._scroll(self._offsets[anchor] - max(0, row))
            self._show_cursor()
            self._caret_to_block()

    def action_cycle_filter(self) -> None:
        self.filter = FILTERS[(FILTERS.index(self.filter) + 1) % len(FILTERS)]
        self._relayout()
        self.post_message(self.Notice(f"filter: {self.filter}"))

    def action_toggle_usage(self) -> None:
        self.show_usage = not self.show_usage
        self._relayout()
        self.post_message(self.Notice("usage shown" if self.show_usage else "usage hidden"))

    def action_toggle_times(self) -> None:
        self.show_times = not self.show_times
        self._relayout()

    def action_toggle(self) -> None:
        if self.blocks:
            block = self.blocks[self.cursor]
            self._set_collapsed([self.cursor], not block.collapsed)

    def action_block(self, collapsed: bool) -> None:
        if self.blocks:
            self._set_collapsed([self.cursor], collapsed)

    def action_group(self, collapsed: bool) -> None:
        if self.blocks:
            group = self.blocks[self.cursor].group
            self._set_collapsed([i for i, b in enumerate(self.blocks) if b.group == group and self.shown[i]], collapsed)

    def action_every(self, collapsed: bool) -> None:
        self._set_collapsed([i for i in range(len(self.blocks)) if self.shown[i]], collapsed)

    def on_click(self, event: events.Click) -> None:
        line = self.scroll_offset.y + event.y
        if self._offsets and line < self._total:
            i = bisect_right(self._offsets, line) - 1
            if i == self.cursor and self.mode == "normal":
                self.action_toggle()
            else:
                col = cell_to_index(self._line_text(line), max(0, event.x - GUTTER))
                self._want_col = col
                self._put_caret(line, col)

    def set_pattern(self, pattern: re.Pattern | None) -> None:
        self.pattern = pattern
        self.refresh()

    def _searchable(self, i: int) -> str:
        text = self._search_text.get(i)
        if text is None:
            text = self._search_text[i] = searchable(self.blocks[i])
        return text

    def find(self, pattern: re.Pattern, step: int = 1) -> int | None:
        if not self.blocks:
            return None
        n = len(self.blocks)
        for k in range(1, n + 1):
            i = (self.cursor + step * k) % n
            if self.shown[i] and pattern.search(self._searchable(i)):
                self.cursor = i
                self._set_collapsed([i], False)
                self._show_cursor()
                self._caret_to_block()
                return i
        return None


class SessionScreen(Screen):
    DEFAULT_CSS = """
    SessionScreen #title {
        height: 1;
        background: $boost;
        padding: 0 1;
    }
    SessionScreen #status {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    SessionScreen #outline {
        display: none;
        max-height: 10;
        border: none;
        padding: 0;
    }
    SessionScreen #find {
        display: none;
        height: 1;
        border: none;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("slash", "search", "Find"),
        Binding("minus", "outline", "Outline"),
        Binding("n", "next_match(1)", "Next match", show=False),
        Binding("N", "next_match(-1)", "Previous match", show=False),
        Binding("q", "close", "Back"),
        Binding("escape", "escape", "Back", show=False),
    ]

    def __init__(self, session: Session, standalone: bool, show_usage: bool = True) -> None:
        super().__init__()
        self.session = session
        self.standalone = standalone
        self.show_usage = show_usage
        self.query_text = ""
        self.message = ""

    def compose(self) -> ComposeResult:
        title = Text(self.session.title, style="bold")
        title.append(f"  {self.session.session_id}", style="dim")
        yield Static(title, id="title")
        yield TranscriptView(self.session.blocks, show_usage=self.show_usage, id="view")
        yield SessionList(id="outline")
        yield Static("", id="status")
        yield Input(placeholder="find", id="find")

    @property
    def view(self) -> TranscriptView:
        return self.query_one(TranscriptView)

    def on_mount(self) -> None:
        self.watch(self.view, "cursor", self._cursor_moved)
        self.watch(self.view, "mode", self._update_status)
        self.view.focus()

    def _cursor_moved(self, *_) -> None:
        self.message = ""
        self._update_status()

    def on_transcript_view_notice(self, event: TranscriptView.Notice) -> None:
        self.message = event.text
        self._update_status()

    def _update_status(self, *_) -> None:
        view = self.view
        if not view.blocks:
            text = "empty session"
        else:
            group = view.blocks[view.cursor].group
            text = f"{view.position}/{view.visible_count} [{group}]"
            if view.mode != "normal":
                text = ("-- VISUAL LINE --  " if view.mode == "line" else "-- VISUAL --  ") + text
            if view.filter != "all":
                text += f" {view.filter}"
            if self.message:
                text += f"  {self.message}"
            text += f"  ·  enter toggle  o/x block  O/X {group}  f filter  U usage  - outline  / find"
            text += "  q back" if not self.standalone else "  ctrl+c quit"
        self.query_one("#status", Static).update(Text(text))

    def action_search(self) -> None:
        find = self.query_one("#find", Input)
        find.display = True
        find.value = self.query_text
        find.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.input.display = False
        self.query_text = event.value
        self.view.focus()
        if not self.query_text:
            self._clear_search()
            return
        try:
            pattern = compile_query(self.query_text)
        except re.error as err:
            self.message = f"/{self.query_text}: {err}"
            self._update_status()
            return
        self.view.set_pattern(pattern)
        self._search(1)

    def _clear_search(self) -> None:
        self.view.set_pattern(None)
        self.message = ""
        self._update_status()

    def _search(self, step: int) -> None:
        pattern = self.view.pattern
        if pattern is None:
            return
        found = self.view.find(pattern, step)
        self.message = f"/{self.query_text}" if found is not None else f"/{self.query_text}: not found"
        self._update_status()

    def action_next_match(self, step: int) -> None:
        self._search(step)

    @property
    def outline(self) -> SessionList:
        return self.query_one("#outline", SessionList)

    def action_outline(self) -> None:
        outline = self.outline
        if outline.display:
            self._close_outline()
            return
        view = self.view
        if not view.prompts:
            self.message = "no prompts"
            self._update_status()
            return
        outline.clear_options()
        outline.add_options([Option(Text(view.blocks[i].text.splitlines()[0] if view.blocks[i].text else "")) for i in view.prompts])
        outline.display = True
        outline.highlighted = view.current_prompt
        outline.focus()

    def _close_outline(self) -> None:
        self.outline.display = False
        self.view.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "outline":
            event.stop()
            self._close_outline()
            self.view.go_prompt(event.option_index)

    def action_escape(self) -> None:
        if self.outline.display:
            self._close_outline()
            return
        if self.view.pattern is not None and not self.query_one("#find", Input).display:
            self._clear_search()
        else:
            self.action_close()

    def action_close(self) -> None:
        find = self.query_one("#find", Input)
        if self.outline.display:
            self._close_outline()
        elif find.display:
            find.display = False
            self.view.focus()
        elif not self.standalone:
            self.app.pop_screen()


class SessionList(OptionList):
    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g,home", "first", show=False),
        Binding("G", "last", show=False),
    ]


def size_label(size: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.0f}T"


class PickerScreen(Screen):
    DEFAULT_CSS = """
    PickerScreen #heading {
        height: 1;
        background: $boost;
        padding: 0 1;
    }
    PickerScreen SessionList {
        height: 1fr;
        border: none;
    }
    """

    def __init__(self, sessions: list[SessionInfo], show_project: bool) -> None:
        super().__init__()
        self.sessions = sessions
        self.show_project = show_project

    def compose(self) -> ComposeResult:
        yield Static(Text(f"{len(self.sessions)} sessions  ·  enter open  ctrl+c quit", style="bold"), id="heading")
        options = []
        for info in self.sessions:
            line = Text.assemble((info.when, "dim"), "  ", (f"{size_label(info.size):>5}", "dim"), "  ")
            if self.show_project:
                line.append(info.project, style="cyan")
                line.append("  ")
            line.append(info.title)
            options.append(Option(line))
        yield SessionList(*options)

    def on_mount(self) -> None:
        self.query_one(SessionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        info = self.sessions[event.option_index]
        self.app.push_screen(SessionScreen(parse(info.path), standalone=False, show_usage=self.app.show_usage))


class ViewerApp(App):
    TITLE = "claude-viewer"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+q", "ignore", show=False, priority=True),
    ]

    def __init__(
        self,
        session: Session | None = None,
        sessions: list[SessionInfo] | None = None,
        show_project: bool = False,
        show_usage: bool = True,
    ) -> None:
        super().__init__()
        self.session = session
        self.sessions = sessions or []
        self.show_project = show_project
        self.show_usage = show_usage

    def action_ignore(self) -> None:
        pass

    def on_mount(self) -> None:
        if self.session is not None:
            self.push_screen(SessionScreen(self.session, standalone=True, show_usage=self.show_usage))
        else:
            self.push_screen(PickerScreen(self.sessions, self.show_project))
