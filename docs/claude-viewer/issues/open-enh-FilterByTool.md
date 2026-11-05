# Enhancement: Filter By Tool

## Goal
Show only part of a session: the calls that only read, or the calls that changed files, so
a session's changes can be reviewed without the rest.

## Current Behaviour
Every block is always laid out (`claude_viewer/app.py:79-88`). `e`/`c` act on one tool's
calls (`app.py:154`), but they only collapse them, never hide them.

Tool calls across 97 local transcripts: Bash 7377, Edit 808, Write 359, Read 331, Skill 192,
Agent 83, ToolSearch 71, EnterWorktree 69, AskUserQuestion 66, ExitWorktree 50, others under
20 each. No Grep, Glob, LS, MultiEdit or NotebookEdit calls appear locally.

## Desired Behaviour
- A key (`f`) cycles through: all, read-only, changes. The status line names the filter.
- The category comes from the file diff, not the tool name. A call is a change when its
  result has a `structuredPatch`, so `block.patch` is set. That covers Edit and Write, and
  any other tool that records a diff.
- **Changes** shows prompts, replies and every call with a diff.
- **Read-only** shows prompts, replies and every call without a diff, Bash included.
- Hidden blocks take no lines. The cursor, `{`/`}`, search and `e`/`c` skip them.
- Usage lines hide along with their message's blocks.
- Changing the filter keeps the cursor block on screen, or the nearest visible block.
- Check: **changes** on the 37 MB session shows only prompts, replies and Updates, and
  `}` steps from one Update to the next.

## Design
### 1. Zero-line hidden blocks
A hidden block gets no strips in `_layout`. Offsets stay one per block, and
`bisect_right(...) - 1` in `render_line` and `on_click` (`app.py:102,165`) still lands on the
visible block that follows a run of hidden ones. Then:
- `action_move` and `find` step over hidden blocks.
- The blank-line rule in `_strips` (`app.py:69-71`) tests the next visible block.
- The whole cache is cleared when the filter changes.
- The status line counts visible blocks.

This mechanism is shared with [HideTokenUsage](open-enh-HideTokenUsage.md).

### 2. Rebuild the block list
Filter `blocks` into a new list and lay it out again. It's simpler, but the cursor index
and the collapse states have to be mapped between the two lists.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:62-88` (`_strips`, `_layout`)
- `src/claude-viewer/claude_viewer/app.py:139-183` (motions, `find`)
- `src/claude-viewer/claude_viewer/app.py:236-246` (status)

A Bash command that changes files (`sed -i`, `git commit`) records no diff, so it counts as
read-only. Robyn chose this over sorting Bash by its first word.

## Priority
Medium

## Related Files
- [open-enh-HideTokenUsage.md](open-enh-HideTokenUsage.md)
