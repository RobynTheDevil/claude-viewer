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


def test_file_target_lines(transcript):
    from claude_viewer.editor import file_target
    from claude_viewer.transcript import Block
    session = parse(transcript)
    assert file_target(session.blocks[5]) == ("/w/widget.py", 5)
    assert file_target(session.blocks[3]) is None
    assert file_target(Block("tool", tool="Read", input={"file_path": "/a", "offset": 40})) == ("/a", 40)
    assert file_target(Block("tool", tool="Read", input={"file_path": "/a"}, file={"startLine": 7})) == ("/a", 7)
    assert file_target(Block("tool", tool="Read", input={"file_path": "/a"})) == ("/a", 1)
    write = Block("tool", tool="Write", input={"file_path": "/a"}, patch=[{"newStart": 9, "lines": ["+x"]}])
    assert file_target(write) == ("/a", 1)


def test_editor_command():
    from claude_viewer.editor import editor_command
    assert editor_command("/f", 5, {"EDITOR": "nvr --remote-wait"}) == ["nvr", "--remote-wait", "+5", "/f"]
    assert editor_command("/f", 5, {"VISUAL": "code --wait", "EDITOR": "vim"}) == ["code", "--wait", "-g", "/f:5"]
    assert editor_command("/f", 5, {})[1:] == ["+5", "/f"]


def test_gf_opens_or_reports(transcript, tmp_path, monkeypatch):
    import claude_viewer.app as app_module
    ran = []
    monkeypatch.setattr(app_module.subprocess, "run", lambda cmd, *a, **k: ran.append(cmd))
    monkeypatch.setenv("EDITOR", "vim")
    monkeypatch.delenv("VISUAL", raising=False)
    target = tmp_path / "widget.py"
    target.write_text("a\nb\nc\nd\ne\nx = 2\n")

    async def script(app, view, pilot):
        view.action_jump(5)
        await pilot.press("g", "f")
        await pilot.pause()
        assert "no such file: /w/widget.py" in str(app.screen.query_one("#status").render())
        view.blocks[5].input["file_path"] = str(target)
        await pilot.press("g", "f")
        await pilot.pause()
        status = str(app.screen.query_one("#status").render())
        assert ran == [["vim", "+5", str(target)]] or f"vim +5 {target}" in status
        view.action_jump(3)
        await pilot.press("g", "f")
        assert view.cursor == 3
    run_view(transcript, script, size=(100, 30))


def test_diff_keeps_background_under_syntax_colors():
    from claude_viewer.render import ADD_STYLE, diff
    from rich.style import Style
    text = diff([{"oldStart": 1, "newStart": 1, "lines": ["+import os", " x = 1"]}], "/w/a.py")
    console = Console(width=60, color_system="truecolor")
    segments = [s for s in console.render(text) if s.text.strip()]
    keyword = next(s for s in segments if s.text == "import")
    assert keyword.style.color is not None
    assert keyword.style.bgcolor == Style.parse(ADD_STYLE).bgcolor
    assert text.plain.splitlines() == ["    1 +import os", "    2  x = 1"]


def test_read_body_highlights_with_real_line_numbers():
    from claude_viewer.render import read_body
    from claude_viewer.transcript import Block
    file = {"filePath": "/w/a.rs", "content": "fn main() {\n}\n", "startLine": 160}
    body = read_body(Block("tool", tool="Read", input={"file_path": "/w/a.rs"}, result="x", file=file))
    assert body.plain.splitlines() == ["  160  fn main() {", "  161  }"]
    assert any(span.style and getattr(span.style, "color", None) for span in body.spans)
    plain = dict(file, filePath="/w/notes.unknownext")
    assert read_body(Block("tool", tool="Read", input={}, result="x", file=plain)) is None


def test_parse_keeps_read_file(tmp_path):
    import json
    path = tmp_path / "33333333-2222-3333-4444-555555555555.jsonl"
    records = [
        {"parentUuid": None, "isSidechain": False, "type": "assistant", "uuid": "a1",
         "message": {"id": "m1", "role": "assistant", "content": [
             {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/w/a.py"}}]}},
        {"parentUuid": "a1", "isSidechain": False, "type": "user", "uuid": "u1",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "1\tx = 1"}]},
         "toolUseResult": {"type": "text", "file": {"filePath": "/w/a.py", "content": "x = 1", "startLine": 1}}},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    read = parse(path).blocks[0]
    assert read.file["content"] == "x = 1"


def test_times_parsed_and_labelled(long_transcript):
    from datetime import datetime, timezone
    from claude_viewer.render import span_label, time_suffix
    session = parse(long_transcript)
    prompts = [b for b in session.blocks if b.kind == "prompt"]
    tools = [b for b in session.blocks if b.kind == "tool"]
    assert tools[0].duration == 5.0
    assert prompts[1].gap == 9 * 60 + 25
    local = datetime(2026, 11, 5, 10, 10, tzinfo=timezone.utc).astimezone().strftime("%H:%M:%S")
    assert time_suffix(prompts[1]) == f"  {local} +9m25s"
    assert time_suffix(tools[1]) == "  5.0s"
    assert span_label(30.2) == "30s" and span_label(600) == "10m" and span_label(3725) == "1h02m"


def test_times_toggle_in_view(long_transcript):
    async def script(app, view, pilot):
        first = view._strips(1)[0].text
        assert "5.0s" not in first
        await pilot.press("t")
        assert view._strips(1)[0].text.rstrip().endswith("5.0s")
        await pilot.press("t")
        assert view._strips(1)[0].text == first
    run_view(long_transcript, script, size=(100, 30))
