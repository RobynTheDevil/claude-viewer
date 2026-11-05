from __future__ import annotations

import re
from bisect import bisect_left, bisect_right

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.geometry import Size
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from claude_viewer.render import render_block, tool_header
from claude_viewer.transcript import Block, Session, SessionInfo, parse

GUTTER = 2
CURSOR = Segment("▌ ", Style(color="cyan", bold=True))
PLAIN = Segment("  ")
FILTERS = ("all", "read-only", "changes")
MATCH = Style(bgcolor="#5f4b00")
CURRENT_MATCH = Style(bgcolor="#d7af00", color="black")


def searchable(block: Block) -> str:
    parts = [block.text, tool_header(block).plain if block.kind == "tool" else "", block.result or ""]
    parts.extend(v for v in block.input.values() if isinstance(v, str))
    return "\n".join(parts)


def compile_query(query: str) -> re.Pattern:
    return re.compile(query, 0 if any(c.isupper() for c in query) else re.I)


def highlight(strip: Strip, pattern: re.Pattern, style: Style) -> Strip:
    cell = strip.index_to_cell_position
    spans = [(cell(m.start()), cell(m.end())) for m in pattern.finditer(strip.text) if m.end() > m.start()]
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
        Binding("j,down", "scroll_rows(1)", "Line down", show=False),
        Binding("k,up", "scroll_rows(-1)", "Line up", show=False),
        Binding("ctrl+d", "page(0.5)", "Half page down", show=False),
        Binding("ctrl+u", "page(-0.5)", "Half page up", show=False),
        Binding("pagedown", "page(1)", "Page down", show=False),
        Binding("pageup", "page(-1)", "Page up", show=False),
        Binding("right_curly_bracket", "move(1)", "Next block", show=False),
        Binding("left_curly_bracket", "move(-1)", "Previous block", show=False),
        Binding("home", "jump(0)", "Top", show=False),
        Binding("G,end", "jump(-1)", "Bottom", show=False),
        Binding("enter,space", "toggle", "Toggle"),
        Binding("e", "group(False)", "Expand tool"),
        Binding("c", "group(True)", "Collapse tool"),
        Binding("E", "every(False)", "Expand all"),
        Binding("C", "every(True)", "Collapse all"),
        Binding("f", "cycle_filter", "Filter"),
        Binding("u", "toggle_usage", "Usage"),
    ]

    PREFIXES = {
        "g": {"g": "jump(0)"},
        "left_square_bracket": {"left_square_bracket": "prompt(-1)"},
        "right_square_bracket": {"right_square_bracket": "prompt(1)"},
    }
    PREFIX_TIMEOUT = 1.0

    cursor = reactive(0)

    class Notice(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, blocks: list[Block], show_usage: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self.blocks = blocks
        self.show_usage = show_usage
        self.filter = "all"
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
                lines = console.render_lines(render_block(self.blocks[i]), options, pad=False)
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
            self._layout()
            self._scroll(self._offsets[anchor] - row)

    def render_line(self, y: int) -> Strip:
        width = self.scrollable_content_region.width
        line = self.scroll_offset.y + y
        if not self._offsets or line >= self._total:
            return Strip.blank(width)
        i = bisect_right(self._offsets, line) - 1
        strip = self._strips(i)[line - self._offsets[i]]
        if self.pattern is not None:
            strip = highlight(strip, self.pattern, CURRENT_MATCH if i == self.cursor else MATCH)
        gutter = CURSOR if i == self.cursor else PLAIN
        return Strip([gutter, *strip], GUTTER + strip.cell_length).crop_extend(0, width, None)

    def watch_cursor(self) -> None:
        self.refresh()

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
        top = self._offsets[self.cursor]
        bottom = top + len(self._strips(self.cursor))
        if bottom <= sy:
            self.cursor = self._block_at(sy)
        elif top >= sy + view:
            self.cursor = self._block_at(sy + view - 1)

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
        row = max(0, min(self._offsets[self.cursor] - sy, view - 1))
        rows = int(view * fraction) or (1 if fraction > 0 else -1)
        self._scroll(sy + rows)
        self.cursor = self._block_at(self.scroll_offset.y + row)
        self._clamp_cursor()

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

    @property
    def current_prompt(self) -> int:
        return max(0, bisect_right(self.prompts, self.cursor) - 1)

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_timer = None

    async def on_key(self, event: events.Key) -> None:
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

    def action_jump(self, index: int) -> None:
        if self.blocks:
            if index < 0:
                i = self._next_visible(len(self.blocks), -1)
            else:
                i = self._next_visible(index - 1, 1)
            if i is not None:
                self.cursor = i
            self._show_cursor()

    @property
    def visible_count(self) -> int:
        return sum(self.shown)

    @property
    def position(self) -> int:
        return sum(self.shown[: self.cursor + 1])

    def _apply_visibility(self) -> None:
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

    def action_cycle_filter(self) -> None:
        self.filter = FILTERS[(FILTERS.index(self.filter) + 1) % len(FILTERS)]
        self._apply_visibility()
        self.post_message(self.Notice(f"filter: {self.filter}"))

    def action_toggle_usage(self) -> None:
        self.show_usage = not self.show_usage
        self._apply_visibility()
        self.post_message(self.Notice("usage shown" if self.show_usage else "usage hidden"))

    def action_toggle(self) -> None:
        if self.blocks:
            block = self.blocks[self.cursor]
            self._set_collapsed([self.cursor], not block.collapsed)

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
            if i == self.cursor:
                self.action_toggle()
            else:
                self.cursor = i

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
            if view.filter != "all":
                text += f" {view.filter}"
            if self.message:
                text += f"  {self.message}"
            text += f"  ·  enter toggle  e/c {group}  f filter  u usage  - outline  / find  q back"
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
        elif self.standalone:
            self.app.exit()
        else:
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

    BINDINGS = [Binding("q,escape", "app.quit", "Quit")]

    def __init__(self, sessions: list[SessionInfo], show_project: bool) -> None:
        super().__init__()
        self.sessions = sessions
        self.show_project = show_project

    def compose(self) -> ComposeResult:
        yield Static(Text(f"{len(self.sessions)} sessions  ·  enter open  q quit", style="bold"), id="heading")
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

    def on_mount(self) -> None:
        if self.session is not None:
            self.push_screen(SessionScreen(self.session, standalone=True, show_usage=self.show_usage))
        else:
            self.push_screen(PickerScreen(self.sessions, self.show_project))
