from __future__ import annotations

from bisect import bisect_right

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.geometry import Size
from textual.reactive import reactive
from textual.screen import Screen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from claude_viewer.render import render_block
from claude_viewer.transcript import Block, Session, SessionInfo, parse

GUTTER = 2
CURSOR = Segment("▌ ", Style(color="cyan", bold=True))
PLAIN = Segment("  ")


def searchable(block: Block) -> str:
    parts = [block.text, block.tool, block.result or ""]
    parts.extend(v for v in block.input.values() if isinstance(v, str))
    return "\n".join(parts).lower()


class TranscriptView(ScrollView, can_focus=True):
    DEFAULT_CSS = """
    TranscriptView {
        overflow-x: hidden;
    }
    """

    BINDINGS = [
        Binding("j,down", "move(1)", "Next block", show=False),
        Binding("k,up", "move(-1)", "Previous block", show=False),
        Binding("g,home", "jump(0)", "Top", show=False),
        Binding("G,end", "jump(-1)", "Bottom", show=False),
        Binding("enter,space", "toggle", "Toggle"),
        Binding("e", "group(False)", "Expand tool"),
        Binding("c", "group(True)", "Collapse tool"),
        Binding("E", "every(False)", "Expand all"),
        Binding("C", "every(True)", "Collapse all"),
    ]

    cursor = reactive(0)

    def __init__(self, blocks: list[Block], **kwargs) -> None:
        super().__init__(**kwargs)
        self.blocks = blocks
        self._cache: dict[int, list[Strip]] = {}
        self._width = 0
        self._offsets: list[int] = []
        self._total = 0

    def _strips(self, i: int) -> list[Strip]:
        strips = self._cache.get(i)
        if strips is None:
            console = self.app.console
            options = console.options.update_width(self._width)
            lines = console.render_lines(render_block(self.blocks[i]), options, pad=False)
            strips = [Strip(line) for line in lines]
            following = self.blocks[i + 1] if i + 1 < len(self.blocks) else None
            if following is None or following.kind != "usage":
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
            self.scroll_to(y=max(0, self._offsets[anchor] - row), animate=False, immediate=True)

    def render_line(self, y: int) -> Strip:
        width = self.scrollable_content_region.width
        line = self.scroll_offset.y + y
        if not self._offsets or line >= self._total:
            return Strip.blank(width)
        i = bisect_right(self._offsets, line) - 1
        strip = self._strips(i)[line - self._offsets[i]]
        gutter = CURSOR if i == self.cursor else PLAIN
        return Strip([gutter, *strip], GUTTER + strip.cell_length).crop_extend(0, width, None)

    def watch_cursor(self) -> None:
        self.refresh()

    def _show_cursor(self) -> None:
        top = self._offsets[self.cursor]
        height = len(self._strips(self.cursor))
        view = self.scrollable_content_region.height
        sy = self.scroll_offset.y
        if top < sy:
            self.scroll_to(y=top, animate=False, immediate=True)
        elif top + min(height, view) > sy + view:
            self.scroll_to(y=top + min(height, view) - view, animate=False, immediate=True)

    def _refresh_blocks(self, changed: list[int]) -> None:
        anchor = self.cursor
        row = self._offsets[anchor] - self.scroll_offset.y
        for i in changed:
            self._cache.pop(i, None)
        self._layout()
        self.scroll_to(y=max(0, self._offsets[anchor] - row), animate=False, immediate=True)
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
            self.cursor = max(0, min(len(self.blocks) - 1, self.cursor + step))
            self._show_cursor()

    def action_jump(self, index: int) -> None:
        if self.blocks:
            self.cursor = index % len(self.blocks)
            self._show_cursor()

    def action_toggle(self) -> None:
        if self.blocks:
            block = self.blocks[self.cursor]
            self._set_collapsed([self.cursor], not block.collapsed)

    def action_group(self, collapsed: bool) -> None:
        if self.blocks:
            group = self.blocks[self.cursor].group
            self._set_collapsed([i for i, b in enumerate(self.blocks) if b.group == group], collapsed)

    def action_every(self, collapsed: bool) -> None:
        self._set_collapsed(range(len(self.blocks)), collapsed)

    def on_click(self, event: events.Click) -> None:
        line = self.scroll_offset.y + event.y
        if self._offsets and line < self._total:
            i = bisect_right(self._offsets, line) - 1
            if i == self.cursor:
                self.action_toggle()
            else:
                self.cursor = i

    def find(self, query: str, step: int = 1) -> int | None:
        if not self.blocks or not query:
            return None
        query = query.lower()
        n = len(self.blocks)
        for k in range(1, n + 1):
            i = (self.cursor + step * k) % n
            if query in searchable(self.blocks[i]):
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
    SessionScreen #find {
        display: none;
        height: 1;
        border: none;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("slash", "search", "Find"),
        Binding("n", "next_match(1)", "Next match", show=False),
        Binding("N", "next_match(-1)", "Previous match", show=False),
        Binding("q,escape", "close", "Back"),
    ]

    def __init__(self, session: Session, standalone: bool) -> None:
        super().__init__()
        self.session = session
        self.standalone = standalone
        self.query_text = ""
        self.message = ""

    def compose(self) -> ComposeResult:
        title = Text(self.session.title, style="bold")
        title.append(f"  {self.session.session_id}", style="dim")
        yield Static(title, id="title")
        yield TranscriptView(self.session.blocks, id="view")
        yield Static("", id="status")
        yield Input(placeholder="find", id="find")

    @property
    def view(self) -> TranscriptView:
        return self.query_one(TranscriptView)

    def on_mount(self) -> None:
        self.watch(self.view, "cursor", self._update_status)
        self.view.focus()

    def _update_status(self, *_) -> None:
        view = self.view
        if not view.blocks:
            text = "empty session"
        else:
            group = view.blocks[view.cursor].group
            text = f"{view.cursor + 1}/{len(view.blocks)} [{group}]"
            if self.message:
                text += f"  {self.message}"
            text += f"  ·  enter toggle  e/c {group}  E/C all  / find  q back"
        self.query_one("#status", Static).update(text)

    def action_search(self) -> None:
        find = self.query_one("#find", Input)
        find.display = True
        find.value = self.query_text
        find.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.input.display = False
        self.query_text = event.value
        self.view.focus()
        self._search(1)

    def _search(self, step: int) -> None:
        if not self.query_text:
            return
        found = self.view.find(self.query_text, step)
        self.message = f"/{self.query_text}" if found is not None else f"/{self.query_text}: not found"
        self._update_status()

    def action_next_match(self, step: int) -> None:
        self._search(step)

    def action_close(self) -> None:
        find = self.query_one("#find", Input)
        if find.display:
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
        Binding("g", "first", show=False),
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
        self.app.push_screen(SessionScreen(parse(info.path), standalone=False))


class ViewerApp(App):
    TITLE = "claude-viewer"

    def __init__(
        self,
        session: Session | None = None,
        sessions: list[SessionInfo] | None = None,
        show_project: bool = False,
    ) -> None:
        super().__init__()
        self.session = session
        self.sessions = sessions or []
        self.show_project = show_project

    def on_mount(self) -> None:
        if self.session is not None:
            self.push_screen(SessionScreen(self.session, standalone=True))
        else:
            self.push_screen(PickerScreen(self.sessions, self.show_project))
