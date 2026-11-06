# claude-viewer: changelog

## 0.1.1 (2026-11-06)

### Changed

- Commands show in full: `…` only past 3 lines, none once expanded.
- Commands drawn under `• Bash`, syntax-colored, heredoc bodies in their own language.
- Read and write indicators: cyan tool name for a read, yellow for a write; `f` changes
- Less paging keys. `d`/`u` half page, Space page down, `e` line down, `<`/`>` top and
- Only `ctrl+c` quits. `q` and Esc leave visual mode or go back to the list.
- Open and close keys. `o`/`x` expand and collapse the block, `O`/`X` its tool or kind.
- Timestamps. t shows prompt times, call durations and gaps over 5 s.
- Syntax-highlight output. Diffs and expanded Reads are colored by a lexer picked by file
- Open file at line. gf opens a Read, Edit or Write's file in $EDITOR at its line.
- Outline panel. - lists every prompt and jumps to the one picked.
- Visual mode yank. v/V select and y copies to the Windows clipboard through clip.exe.
- Filter by tool. f cycles all, read-only and changes.
- Hide token usage. u toggles usage lines; --no-usage applies to the view, --print and
- Highlight matches. Every match on screen is highlighted, brighter in the cursor block; Esc
- Regex search. / takes a smart-case regex and searches the drawn tool header too.
- Jump between prompts. ]]/[[ step prompts and put each at the top; gg goes to the top.
- Half-page scroll. ctrl+d/ctrl+u move half the view, pgdn/pgup a full one.
- Line, block and screen motions. j/k move a caret, ctrl+e/ctrl+y scroll, }/{ step blocks.
