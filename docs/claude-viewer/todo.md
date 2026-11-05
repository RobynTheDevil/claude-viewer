How these are worked: [workflow.md](../workflow.md#items).

Key:
Items are plain `- ` lines. Their status is not written here: the worktree working one claims
it with the `workflow` skill, and the startup survey reads the claims from every tree. No
marker is open, `~` in progress, `+` has update note, `x` confirmed and ready for `wf close`.

Reasoning is recorded here only while a fix is unconfirmed. Once confirmed it moves to
[project.md](project.md) and the line moves to [done.md](done.md), reduced to one entry.

Robyn will update with **note** or similar when an item is tested. Only they confirm
an item, and the claim moves to `x` on their word.

## defects:

Each open defect has a report in [issues/](issues/) carrying the reproduction, the root
cause and the candidate fixes. This list is the status; the report is the record.

None open.

## enhancements:

- [Line Scroll Block Motions](issues/open-enh-LineScrollBlockMotions.md)
    - `j`/`k` move the caret a line, `ctrl+e`/`ctrl+y` scroll, `}`/`{` step blocks. Test: `j` through a block taller than the screen, then `}`.
- [Half Page Scroll](issues/open-enh-HalfPageScroll.md)
    - Test: on the 37 MB session, `ctrl+d` five times then `ctrl+u` five times returns to the same place.
- [Jump Between Prompts](issues/open-enh-JumpBetweenPrompts.md)
    - Test: `]]` and `[[` step prompts and scroll each to the top. `gg` replaces `g`.
- [Regex Search](issues/open-enh-RegexSearch.md)
    - Test: `/Bash\(git` finds a git call, `/(` reports the error, `/Widget` is case-sensitive.
- [Highlight Matches](issues/open-enh-HighlightMatches.md)
    - Test: `/git` highlights every match on screen, brighter in the cursor block. Esc clears.
- [Hide Token Usage](issues/open-enh-HideTokenUsage.md)
    - Test: `u` hides every usage line. `--no-usage` also applies to `--print` and `--export`.
- [Filter By Tool](issues/open-enh-FilterByTool.md)
    - Test: `f` cycles all, read-only, changes. The status line names it.
- [Visual Mode Yank](issues/open-enh-VisualModeYank.md)
    - Test: `V` `j` `j` `y` on Bash output, then paste into Notepad.
- [Outline Panel](issues/open-enh-OutlinePanel.md)
    - Test: `-`, pick the third prompt, reopen and it is highlighted.
- [Open File At Line](issues/open-enh-OpenFileAtLine.md)
    - Test: `gf` on an Edit opens nvim at its first changed line. `:q` returns.
- [Syntax Highlight Output](issues/open-enh-SyntaxHighlightOutput.md)
    - Test: expand a `.rs` Read and a `.py` Edit. Both show colors, and `+` lines keep green.
- [Timestamps](issues/open-enh-Timestamps.md)
    - Test: `t` shows prompt times, call durations and gaps over 5 s.

## back-burner:

Items that are real and not being worked: too large to scope yet, cosmetic and waiting on a
feature that would absorb them, or blocked on someone else. Each still says what it is and
why it is waiting, so it does not get rediscovered as a new item.
