# claude-viewer: done

Closed and confirmed, newest first, one entry each. The reasoning lives in
[project.md](project.md); this is the record that they happened. Open work is in
[todo.md](todo.md).

An entry is one item: the line from the todo, compacted, with a link to its report and one
sentence on what the change was. Not the investigation, not the alternatives, not the rounds
it took. This file is history and is not read as reference.

- [x] Timestamps. t shows prompt times, call durations and gaps over 5 s.
  ([report](issues/done/done-enh-Timestamps.md))

- [x] Syntax-highlight output. Diffs and expanded Reads are colored by a lexer picked by file
  suffix. ([report](issues/done/done-enh-SyntaxHighlightOutput.md))

- [x] Open file at line. gf opens a Read, Edit or Write's file in $EDITOR at its line.
  ([report](issues/done/done-enh-OpenFileAtLine.md))

- [x] Outline panel. - lists every prompt and jumps to the one picked.
  ([report](issues/done/done-enh-OutlinePanel.md))

- [x] Visual mode yank. v/V select and y copies to the Windows clipboard through clip.exe.
  ([report](issues/done/done-enh-VisualModeYank.md))

- [x] Filter by tool. f cycles all, read-only and changes.
  ([report](issues/done/done-enh-FilterByTool.md))

- [x] Hide token usage. u toggles usage lines; --no-usage applies to the view, --print and
  --export. ([report](issues/done/done-enh-HideTokenUsage.md))

- [x] Highlight matches. Every match on screen is highlighted, brighter in the cursor block; Esc
  clears. ([report](issues/done/done-enh-HighlightMatches.md))

- [x] Regex search. / takes a smart-case regex and searches the drawn tool header too.
  ([report](issues/done/done-enh-RegexSearch.md))

- [x] Jump between prompts. ]]/[[ step prompts and put each at the top; gg goes to the top.
  ([report](issues/done/done-enh-JumpBetweenPrompts.md))

- [x] Half-page scroll. ctrl+d/ctrl+u move half the view, pgdn/pgup a full one.
  ([report](issues/done/done-enh-HalfPageScroll.md))

- [x] Line, block and screen motions. j/k move a caret, ctrl+e/ctrl+y scroll, }/{ step blocks.
  ([report](issues/done/done-enh-LineScrollBlockMotions.md))

  - [x] <what was wrong, in a few words>
      ([report](issues/done/done-bug-<Name>.md)). <One or two sentences: what changed and what
      confirmed it.>
