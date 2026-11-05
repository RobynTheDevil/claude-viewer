# Enhancement: Hide Token Usage

## Goal
Turn the per-message token lines off when they're noise.

## Current Behaviour
The parser adds a `usage` block after every assistant message
(`claude_viewer/transcript.py:223`). It renders as one dim line even when collapsed
(`render.py:151`). The block before it has no trailing blank line, so the usage line sits
under its message (`app.py:69-71`). There is no way to hide it.

## Desired Behaviour
- A key (`u`) toggles usage lines on and off in the viewer.
- `--no-usage` starts with them off. It also leaves them out of `--print` and `--export`.
- With usage hidden, each message keeps its trailing blank line.
- The cursor never lands on a hidden usage block.
- Check: `u` on the 37 MB session removes every `· claude-…` line, and blocks still have one
  blank line between them.

## Design
### 1. Zero-line hidden blocks
Use the hidden-block mechanism from [FilterByTool](done-enh-FilterByTool.md): usage blocks
get no strips while hidden, and the blank-line rule tests the next visible block. Pass the
flag from `cli.py:16-19` through `ViewerApp` to the view, and to `print_session`
(`render.py:172`) and `to_markdown` (`export.py:70`).

### 2. Drop usage blocks at parse time
`parse(path, usage=False)` never creates them. This is simplest for the flag, but the key
toggle would need to parse again.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:62-88` (`_strips`, `_layout`)
- `src/claude-viewer/claude_viewer/cli.py:16-19`
- `src/claude-viewer/claude_viewer/render.py:172`
- `src/claude-viewer/claude_viewer/export.py:70`

## Open Questions
- Should the choice persist between runs? Settled: no. `--no-usage` in an alias carries
  it, and no settings file is added.

## Priority
Medium

## Related Files
- [done-enh-FilterByTool.md](done-enh-FilterByTool.md)
