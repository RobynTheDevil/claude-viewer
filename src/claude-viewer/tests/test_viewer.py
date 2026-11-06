import asyncio
import io
import json
import re

from rich.console import Console

from claude_viewer.app import TranscriptView, ViewerApp
from claude_viewer.cli import main
from claude_viewer.export import to_markdown
from claude_viewer.render import print_session, spaced
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
    assert re.search(r"^\$ ls -la *$", text, re.M)
    assert "• Thinking…" in text
    assert re.search(r"^> 5 lines *$", text, re.M)
    assert "• Update(/w/widget.py)" in text
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
        app = ViewerApp(session=parse(transcript), show_usage=True)
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
            await pilot.press("right_curly_bracket", "right_curly_bracket", "O")
            assert not blocks[5].collapsed and blocks[3].collapsed
            await pilot.press("slash", *"widget", "enter")
            assert "widget" in (blocks[view.cursor].text + str(blocks[view.cursor].input)).lower()
            await pilot.press("q")
    asyncio.run(run())


def test_ansi_output_is_styled_not_raw(transcript):
    session = parse(transcript)
    bash = session.blocks[3]
    bash.result = "\x1b[33mc88c155\x1b[m first commit"
    bash.collapsed = False
    out = io.StringIO()
    print_session(session, Console(file=out, width=100, color_system=None))
    assert "c88c155 first commit" in out.getvalue() and "[33m" not in out.getvalue()
    assert "\x1b" not in to_markdown(session)


def run_view(path, script, size=(80, 12), show_usage=False):
    async def run():
        app = ViewerApp(session=parse(path), show_usage=show_usage)
        async with app.run_test(size=size) as pilot:
            view = app.screen.query_one(TranscriptView)
            await script(app, view, pilot)
    asyncio.run(run())


def test_caret_lines_and_scroll_keep_cursor_on_screen(long_transcript):
    async def script(app, view, pilot):
        await pilot.press("E")
        tall = next(i for i, b in enumerate(view.blocks) if b.kind == "tool")
        view.action_jump(tall)
        start, line = view.scroll_offset.y, view.caret_line
        height = view.scrollable_content_region.height
        await pilot.press("j", "j")
        assert view.caret_line == line + 2 and view.cursor == tall
        for _ in range(height):
            await pilot.press("j")
        assert view.caret_line == line + height + 2
        assert view.scroll_offset.y + height - 1 == view.caret_line and view.scroll_offset.y > start
        assert view.cursor == tall
        await pilot.press("right_curly_bracket")
        assert view.cursor > tall and view.caret_line == view._offsets[view.cursor]
        before = view.cursor
        for _ in range(height + 5):
            await pilot.press("ctrl+e")
        assert view.cursor != before
        assert view.scroll_offset.y <= view.caret_line < view.scroll_offset.y + height
    run_view(long_transcript, script)


def test_caret_columns_and_words():
    from claude_viewer.selection import first_nonblank, marker_len, next_word, prev_word
    text = "• Bash(git status)"
    assert next_word(text, 0) == 2 and next_word(text, 2) == 6 and next_word(text, 6) == 7
    assert prev_word(text, 7) == 6 and prev_word(text, 6) == 2
    assert first_nonblank("     line 3") == 5
    assert marker_len("tool", " ⎿ out") == 3 and marker_len("tool", "   more") == 3
    assert marker_len("tool", "     more") == 3
    assert marker_len("text", "• Fixed") == 2 and marker_len("prompt", "> hi") == 0


def test_visual_line_yank(long_transcript, monkeypatch):
    import claude_viewer.app as app_module
    copied = []
    monkeypatch.setattr(app_module, "to_windows_clipboard", lambda text: copied.append(text))

    async def script(app, view, pilot):
        bash = next(i for i, b in enumerate(view.blocks) if b.kind == "tool")
        view.action_jump(bash)
        await pilot.press("enter", "j", "V", "j", "j")
        assert view.mode == "line"
        assert "VISUAL LINE" in str(app.screen.query_one("#status").render())
        await pilot.press("y")
        assert view.mode == "normal"
        assert copied == ["line 0\nline 1\nline 2"]
        assert "3 lines copied" in str(app.screen.query_one("#status").render())
        await pilot.press("v", "w", "escape")
        assert view.mode == "normal" and app.is_running
        await pilot.press("v", "dollar_sign", "y")
        assert copied[-1] == "line 0"
        view.action_jump(bash)
        await pilot.press("w", "v", "w", "y")
        assert copied[-1] == "echo 0"
    run_view(long_transcript, script, size=(80, 30))


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
    run_view(long_transcript, script, size=(80, 30), show_usage=True)


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
        assert not any(view.shown[i] for i in usage)
        await pilot.press("U")
        assert all(view.shown)
        before = view.virtual_size.height
        await pilot.press("U")
        assert not any(view.shown[i] for i in usage)
        assert all(view._strips(i) == [] for i in usage)
        assert view.virtual_size.height == sum(len(view._strips(i)) for i in range(len(view.blocks))) < before
        for i in range(len(view.blocks)):
            if view.shown[i] and spaced(view.blocks[i]):
                assert view._strips(i)[-1].cell_length == 0
        for _ in range(12):
            await pilot.press("right_curly_bracket")
            assert view.shown[view.cursor]
        await pilot.press("U")
        assert all(view.shown)
    run_view(transcript, script, size=(100, 30))
    assert main([str(transcript), "--export", "-"]) == 0
    assert "<sub>" not in capsys.readouterr().out
    assert main([str(transcript), "--export", "-", "--usage"]) == 0
    assert "<sub>" in capsys.readouterr().out
    assert main([str(transcript), "--print"]) == 0
    assert "• claude-opus" not in capsys.readouterr().out
    assert main([str(transcript), "--print", "--usage"]) == 0
    assert "• claude-opus" in capsys.readouterr().out


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
    run_view(transcript, script, size=(100, 30), show_usage=True)


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


def test_caret_through_multiline_prompt(tmp_path):
    path = tmp_path / "33333333-2222-3333-4444-555555555555.jsonl"
    rec = {"parentUuid": None, "isSidechain": False, "type": "user", "uuid": "u1",
           "message": {"role": "user", "content": "first line\n\nthird line\n"}}
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    async def script(app, view, pilot):
        for _ in range(4):
            await pilot.press("l", "j")
        await pilot.pause()
        assert view.caret_line == view._total - 1
        await pilot.press("g", "g", "v")
        for _ in range(4):
            await pilot.press("j")
        await pilot.pause()
        assert view.mode == "visual"

    run_view(path, script)


def test_less_keys_match_their_ctrl_forms(long_transcript):
    async def script(app, view, pilot):
        await pilot.press("E")
        for plain, ctrl in (("d", "ctrl+d"), ("space", "ctrl+f"), ("e", "ctrl+e")):
            await pilot.press(plain)
            once = (view.scroll_offset.y, view.caret_line)
            await pilot.press("home", ctrl)
            assert (view.scroll_offset.y, view.caret_line) == once and once[0] > 0
            await pilot.press("home")
        await pilot.press("G", "u")
        once = (view.scroll_offset.y, view.caret_line)
        await pilot.press("G", "ctrl+u")
        assert (view.scroll_offset.y, view.caret_line) == once
        await pilot.press("less_than_sign")
        assert view.cursor == 0
        await pilot.press("greater_than_sign")
        assert view.cursor == len(view.blocks) - 1
    run_view(long_transcript, script, size=(80, 20), show_usage=True)


def test_only_ctrl_c_quits(transcript):
    async def script(app, view, pilot):
        await pilot.press("v")
        await pilot.press("q")
        assert view.mode == "normal" and app.is_running
        await pilot.press("V", "escape")
        assert view.mode == "normal"
        await pilot.press("q", "escape", "ctrl+q")
        await pilot.pause()
        assert app.is_running
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert not app.is_running
    run_view(transcript, script)


def test_open_and_close_blocks(transcript):
    async def script(app, view, pilot):
        blocks = view.blocks
        bash = [i for i, b in enumerate(blocks) if b.tool == "Bash"][0]
        view.action_jump(bash)
        await pilot.press("o")
        assert not blocks[bash].collapsed
        await pilot.press("o")
        assert not blocks[bash].collapsed
        await pilot.press("x")
        assert blocks[bash].collapsed
        await pilot.press("x")
        assert blocks[bash].collapsed
        thinking = [i for i, b in enumerate(blocks) if b.kind == "thinking"][0]
        view.action_jump(thinking)
        await pilot.press("O")
        assert not blocks[thinking].collapsed and blocks[bash].collapsed
        await pilot.press("X")
        assert blocks[thinking].collapsed
    run_view(transcript, script, size=(100, 30))


def test_command_writes():
    from claude_viewer.access import command_writes
    reads = [
        "ls -la",
        "git status --short && git log --oneline -5",
        "grep -rn foo src | head -20",
        "cat a.txt 2>/dev/null; echo done",
        "cd /x && sed -n 1,20p f.py",
        "find . -name '*.py' | xargs grep -n def",
        "git -C repo diff HEAD~1",
        "for f in *.md; do\n  head -3 \"$f\"\ndone",
        "cat <<EOF\nrm -rf /\nEOF",
        "git branch -vv",
        "FOO=1 env BAR=2 wc -l x",
        "git config user.name",
        "command -v cargo",
    ]
    writes = [
        "rm -rf build",
        "echo x > out.txt",
        "git commit -m 'x'",
        "sed -i 's/a/b/' f",
        "find . -name '*.pyc' -delete",
        "python3 script.py",
        "ls | tee list.txt",
        "cat > f <<'EOF'\nhello\nEOF",
        "git branch new-topic",
        "git config user.name Robyn",
        "echo 'unterminated",
    ]
    assert [c for c in reads if command_writes(c)] == []
    assert [c for c in writes if not command_writes(c)] == []


def test_long_tool_header_wraps():
    from claude_viewer.render import render_block
    from claude_viewer.transcript import Block
    prompt = "investigate " + "word " * 60 + "end"
    block = Block("tool", tool="Agent", input={"prompt": prompt}, result="ok")
    console = Console(width=80, file=io.StringIO(), color_system=None)
    with console.capture() as cap:
        console.print(render_block(block))
    assert "…" not in cap.get() and "end)" in cap.get()


def test_command_header_full_when_expanded():
    from claude_viewer.render import render_block
    from claude_viewer.transcript import Block
    command = "echo " + "x" * 150 + "\n" + "\n".join(f"echo {n}" for n in range(6))
    block = Block("tool", tool="Bash", input={"command": command}, result="ok")
    console = Console(width=200, file=io.StringIO(), color_system=None)

    def shown(collapsed):
        block.collapsed = collapsed
        with console.capture() as cap:
            console.print(render_block(block))
        return cap.get()

    collapsed = shown(True)
    assert "x" * 150 in collapsed and "echo 1" in collapsed and "echo 2" not in collapsed
    assert "… +4 lines" in collapsed
    expanded = shown(False)
    assert expanded.splitlines()[0].startswith("$ echo xxx")
    assert "echo 5" in expanded and "… +" not in expanded
    short = Block("tool", tool="Bash", input={"command": "ls\npwd"}, result="ok")
    with console.capture() as cap:
        console.print(render_block(short))
    assert "…" not in cap.get() and re.search(r"^> 1 line *$", cap.get(), re.M)


def test_command_languages():
    from claude_viewer.render import highlight_command
    lines = ["python3 - <<'EOF'", "def f():", "    return 1", "EOF", "cat > a.rs <<EOF", "fn main() {}", "EOF", "ls"]
    out = highlight_command(lines, "Bash")
    assert [t.plain for t in out] == lines
    assert any(span.style for span in out[1].spans)
    assert any(span.style for span in out[5].spans)


def test_shell_highlight():
    from claude_viewer.shell import COMMAND, FLAG, STRING, highlight_shell
    [text] = highlight_shell(["cd /x && git log -5 'a b' | grep done 2>&1 > out.md#a"])

    def style_of(word):
        start = text.plain.index(word)
        return [s.style for s in text.spans if s.start <= start < s.end]

    assert style_of("cd") == [COMMAND] and style_of("git") == [COMMAND] and style_of("grep") == [COMMAND]
    assert style_of("log") == [] and style_of("done") == [] and style_of("out.md#a") == []
    assert style_of("-5") == [FLAG] and style_of("'a b'") == [STRING]


def test_status_line_and_help(transcript):
    async def script(app, view, pilot):
        await pilot.press("right_curly_bracket", "right_curly_bracket", "right_curly_bracket")
        status = str(app.screen.query_one("#status").render())
        assert status.startswith(f"{view.position}/{view.visible_count} · enter toggle")
        assert status.endswith("O/X all[Bash read]  - outline  / find  ctrl+c quit  ? help")
        help = app.screen.query_one("#help")
        assert not help.display
        await pilot.press("question_mark")
        text = str(help.render())
        assert help.display and "filter all" in text and "usage hidden" in text and "cycle the filter" in text
        await pilot.press("question_mark")
        assert not help.display
        await pilot.press("question_mark", "escape")
        assert not help.display and app.is_running
        width = view._width
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert view.has_class("scrollbar") and view._width == width - 1
        await pilot.press("question_mark")
        assert "scrollbar shown" in str(help.render())
        await pilot.press("escape")
        await pilot.press("slash", "a", "question_mark")
        assert app.screen.query_one("#find").value == "a?" and not help.display
    run_view(transcript, script, size=(120, 40))


def test_long_command_folds_by_character():
    from claude_viewer.render import render_block
    from claude_viewer.transcript import Block
    command = 'grep -n "' + "a\\|" * 40 + 'z" src/x.rs'
    block = Block("tool", tool="Bash", input={"command": command}, result="ok")
    console = Console(width=60, file=io.StringIO(), color_system=None)
    with console.capture() as cap:
        console.print(render_block(block))
    lines = cap.get().splitlines()
    assert lines[0].startswith('$ grep -n "a\\|') and len(lines[0]) == 60
    assert "…" not in cap.get()
    assert "".join(line[2:] for line in lines[:-1]).rstrip() == command


def test_wrap_cuts_prefer_word_boundaries():
    from claude_viewer.render import wrap_cuts
    assert wrap_cuts("aaa bbb ccc", 8) == [8]
    assert wrap_cuts("ab " + "x" * 12, 8) == [8]
    assert wrap_cuts("ab " + "x" * 6, 8) == [3]
    assert wrap_cuts("  " + "x" * 10, 8) == [8]


def test_shell_groups_split_by_access():
    from claude_viewer.transcript import Block
    read = Block("tool", tool="Bash", input={"command": "git status"})
    write = Block("tool", tool="Bash", input={"command": "rm x"})
    edit = Block("tool", tool="Edit", input={"file_path": "a"})
    assert (read.group, write.group, edit.group) == ("Bash read", "Bash write", "Edit")
