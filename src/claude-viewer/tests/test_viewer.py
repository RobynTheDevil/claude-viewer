import asyncio
import io

from rich.console import Console

from claude_viewer.app import TranscriptView, ViewerApp
from claude_viewer.cli import main
from claude_viewer.export import to_markdown
from claude_viewer.render import print_session
from claude_viewer.transcript import list_sessions, parse, project_dir_for, session_title


def kinds(session):
    return [b.kind if b.kind != "tool" else b.tool for b in session.blocks]


def test_parse_orders_blocks_and_pairs_results(transcript):
    session = parse(transcript)
    assert session.title == "Fix the widget"
    assert kinds(session) == ["prompt", "prompt", "thinking", "Bash", "usage", "Edit", "usage", "text", "usage"]
    prompts = [b.text for b in session.blocks if b.kind == "prompt"]
    assert prompts == ["/startup bobbins", "Please fix the widget"]
    bash = session.blocks[3]
    assert bash.result == "a\nb\nc\nd\ne" and bash.collapsed
    edit = session.blocks[5]
    assert edit.patch and not edit.collapsed
    assert session.blocks[4].usage["output_tokens"] == 40


def test_title_scan_matches_parse(transcript):
    assert session_title(transcript) == "Fix the widget"
    infos = list_sessions([transcript.parent])
    assert [i.session_id for i in infos] == [transcript.stem]


def test_project_dir_naming(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert project_dir_for("/mnt/c/p/x.y/.worktrees/z").name == "-mnt-c-p-x-y--worktrees-z"


def test_print_shows_default_view(transcript):
    out = io.StringIO()
    print_session(parse(transcript), Console(file=out, width=100, color_system=None))
    text = out.getvalue()
    assert "> Please fix the widget" in text
    assert "⏺ Bash(ls -la)" in text
    assert "… +2 lines" in text
    assert "⏺ Update(/w/widget.py)" in text
    assert "+x = 2" in text
    assert "secret" not in text and "Skill body" not in text and "sidechain" not in text


def test_markdown_export(transcript):
    md = to_markdown(parse(transcript))
    assert md.startswith("# Fix the widget")
    assert "```diff\n@@ -4,3 +4,3 @@\n a\n-x = 1\n+x = 2\n b\n```" in md
    assert "<summary>Output (5 lines)</summary>" in md
    assert "<summary>Thinking</summary>" in md


def test_cli_export_stdout(transcript, capsys):
    assert main([str(transcript), "--export", "-"]) == 0
    assert "# Fix the widget" in capsys.readouterr().out


def test_view_toggles_and_groups(transcript):
    async def run():
        app = ViewerApp(session=parse(transcript))
        async with app.run_test(size=(100, 30)) as pilot:
            view = app.screen.query_one(TranscriptView)
            blocks = view.blocks
            await pilot.press("right_curly_bracket", "right_curly_bracket", "right_curly_bracket")
            assert blocks[view.cursor].tool == "Bash"
            before = view.virtual_size.height
            await pilot.press("enter")
            assert not blocks[3].collapsed
            assert view.virtual_size.height > before
            await pilot.press("C")
            assert all(b.collapsed for b in blocks if b.collapsible)
            await pilot.press("right_curly_bracket", "right_curly_bracket", "e")
            assert not blocks[5].collapsed and blocks[3].collapsed
            await pilot.press("slash", *"widget", "enter")
            assert "widget" in (blocks[view.cursor].text + str(blocks[view.cursor].input)).lower()
            await pilot.press("q")
    asyncio.run(run())


def test_ansi_output_is_styled_not_raw(transcript):
    session = parse(transcript)
    bash = session.blocks[3]
    bash.result = "\x1b[33mc88c155\x1b[m first commit"
    out = io.StringIO()
    print_session(session, Console(file=out, width=100, color_system=None))
    assert "c88c155 first commit" in out.getvalue() and "[33m" not in out.getvalue()
    assert "\x1b" not in to_markdown(session)


def run_view(path, script, size=(80, 12)):
    async def run():
        app = ViewerApp(session=parse(path))
        async with app.run_test(size=size) as pilot:
            view = app.screen.query_one(TranscriptView)
            await script(app, view, pilot)
    asyncio.run(run())


def test_line_scroll_keeps_cursor_on_screen(long_transcript):
    async def script(app, view, pilot):
        await pilot.press("E")
        tall = next(i for i, b in enumerate(view.blocks) if b.kind == "tool")
        view.action_jump(tall)
        start = view.scroll_offset.y
        await pilot.press("j", "j")
        assert view.scroll_offset.y == start + 2 and view.cursor == tall
        for _ in range(12):
            await pilot.press("j")
        assert view.cursor != tall
        top = view._offsets[view.cursor]
        assert top + len(view._strips(view.cursor)) > view.scroll_offset.y
        await pilot.press("right_curly_bracket")
        assert view.cursor > tall
    run_view(long_transcript, script)


def test_half_page_round_trip(long_transcript):
    async def script(app, view, pilot):
        await pilot.press("ctrl+d")
        await pilot.press("ctrl+d")
        y, cursor = view.scroll_offset.y, view.cursor
        for _ in range(5):
            await pilot.press("ctrl+d")
        for _ in range(5):
            await pilot.press("ctrl+u")
        assert (view.scroll_offset.y, view.cursor) == (y, cursor)
        assert view.scroll_offset.y > 0
    run_view(long_transcript, script)


def test_prompt_jumps(long_transcript):
    async def script(app, view, pilot):
        prompts = [i for i, b in enumerate(view.blocks) if b.kind == "prompt"]
        assert len(prompts) == 5 and view.cursor == 0
        for _ in range(4):
            await pilot.press("right_square_bracket", "right_square_bracket")
        assert view.cursor == prompts[4]
        await pilot.press("right_square_bracket", "right_square_bracket")
        assert view.cursor == prompts[4] and "last prompt" in str(app.screen.query_one("#status").render())
        await pilot.press("left_square_bracket", "left_square_bracket")
        assert view.cursor == prompts[3]
        assert view.scroll_offset.y == view._offsets[prompts[3]]
        await pilot.press("right_square_bracket", "x")
        assert view.cursor == prompts[3]
        await pilot.press("g", "g")
        assert view.cursor == 0
    run_view(long_transcript, script, size=(80, 30))


def test_compile_query_smart_case():
    from claude_viewer.app import compile_query
    assert compile_query("widget").search("Widget")
    assert not compile_query("Widget").search("widget")
    assert compile_query(r"Bash\(git").search("Bash(git status")


def test_highlight_marks_matches():
    from rich.segment import Segment
    from textual.strip import Strip
    from claude_viewer.app import MATCH, compile_query, highlight
    strip = Strip([Segment("⏺ run git and "), Segment("git", None), Segment(" again")])
    out = highlight(strip, compile_query("git"), MATCH)
    assert out.text == strip.text
    styled = "".join(seg.text for seg in out if seg.style and seg.style.bgcolor)
    assert styled == "gitgit"


def test_regex_search_in_view(long_transcript):
    async def script(app, view, pilot):
        await pilot.press("slash", *"echo 3-", "enter")
        assert view.blocks[view.cursor].input["command"].startswith("echo 3-")
        assert view.pattern is not None
        await pilot.press("slash", "ctrl+u", *"Bash\\(echo 2", "enter")
        assert view.blocks[view.cursor].input["command"].startswith("echo 2-")
        await pilot.press("slash", "ctrl+u", "(", "enter")
        status = str(app.screen.query_one("#status").render())
        assert "/(: missing )" in status
        await pilot.press("slash", "ctrl+u", *"PROMPT", "enter")
        assert "not found" in str(app.screen.query_one("#status").render())
        await pilot.press("escape")
        assert view.pattern is None
        assert app.screen is not None and app.is_running
    run_view(long_transcript, script, size=(80, 30))


def test_usage_toggle_and_flag(transcript, capsys):
    async def script(app, view, pilot):
        usage = [i for i, b in enumerate(view.blocks) if b.kind == "usage"]
        before = view.virtual_size.height
        await pilot.press("u")
        assert not any(view.shown[i] for i in usage)
        assert all(view._strips(i) == [] for i in usage)
        assert view.virtual_size.height == before - len(usage)
        for i in range(len(view.blocks)):
            if view.shown[i]:
                assert view._strips(i)[-1].cell_length == 0
        for _ in range(12):
            await pilot.press("right_curly_bracket")
            assert view.shown[view.cursor]
        await pilot.press("u")
        assert all(view.shown)
    run_view(transcript, script, size=(100, 30))
    assert main([str(transcript), "--export", "-", "--no-usage"]) == 0
    assert "<sub>" not in capsys.readouterr().out
    assert main([str(transcript), "--print", "--no-usage"]) == 0
    assert "· claude-opus" not in capsys.readouterr().out


def test_filter_changes_and_read_only(transcript):
    async def script(app, view, pilot):
        await pilot.press("f")
        assert view.filter == "read-only"
        shown = [view.blocks[i] for i in range(len(view.blocks)) if view.shown[i]]
        assert [b.tool or b.kind for b in shown] == ["prompt", "prompt", "Bash", "usage", "text", "usage"]
        await pilot.press("f")
        assert view.filter == "changes"
        shown = [view.blocks[i] for i in range(len(view.blocks)) if view.shown[i]]
        assert [b.tool or b.kind for b in shown] == ["prompt", "prompt", "Edit", "usage", "text", "usage"]
        await pilot.press("home", "right_curly_bracket", "right_curly_bracket")
        assert view.blocks[view.cursor].tool == "Edit"
        assert "changes" in str(app.screen.query_one("#status").render())
        await pilot.press("f")
        assert view.filter == "all" and all(view.shown)
    run_view(transcript, script, size=(100, 30))


def test_outline_menu(long_transcript):
    async def script(app, view, pilot):
        outline = app.screen.query_one("#outline")
        await pilot.press("minus")
        assert outline.display and outline.has_focus and outline.highlighted == 0
        await pilot.press("j", "j", "enter")
        prompts = view.prompts
        assert not outline.display and view.has_focus
        assert view.cursor == prompts[2] and view.scroll_offset.y == view._offsets[prompts[2]]
        await pilot.press("minus")
        assert outline.highlighted == 2
        await pilot.press("k", "escape")
        assert not outline.display and view.cursor == prompts[2] and app.is_running
        await pilot.press("minus", "q")
        assert not outline.display and app.is_running
        await pilot.press("minus", "minus")
        assert not outline.display
    run_view(long_transcript, script, size=(80, 30))
