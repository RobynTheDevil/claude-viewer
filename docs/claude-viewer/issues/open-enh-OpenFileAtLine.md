# Enhancement: Open File At Line

## Goal
Go from a Read, Edit or Write in a session straight to that file in the editor, at the line
it touched.

## Current Behaviour
Tool blocks show the path (`claude_viewer/render.py:103-110`), but nothing opens it.
`g` is bound to "top" (`claude_viewer/app.py:43`), so `gf` can't be bound as it stands.

## Desired Behaviour
- `gf` on a Read, Edit or Write block suspends the viewer, opens the file in the editor,
  and resumes the viewer when the editor exits.
- The line is:
  - Edit: the first changed line, which is the first hunk's `newStart` plus its leading
    context lines.
  - Read: the call's `offset`, or 1.
  - Write: 1.
- The editor is `$VISUAL`, then `$EDITOR`, split with `shlex`, then `nvim`, then `less`.
  Here `$EDITOR` is `nvr --remote-wait`.
- A missing file shows `no such file: <path>` and opens nothing.
- `gf` on any other block does nothing.
- `g` alone no longer goes to the top. `gg` does, as in vim.
- Check: `gf` on an Edit block opens nvim at its first `+` line. After `:q` the viewer is
  where it was.

## Design
### 1. Suspend and run
Run the editor inside `with self.app.suspend(): subprocess.run(...)`
(`textual/app.py:4718`). Catch `SuspendNotSupported` and show it in the status line. Pass
`+N file` for vim, nvim, nano, less and nvr, and `-g file:N` for `code`. Turn a `C:\...`
path into a WSL path with `wslpath`. `gf` and `gg` go through the prefix-key handler from
[JumpBetweenPrompts](open-enh-JumpBetweenPrompts.md).

### 2. Print the command
Show `nvim +N path` in the status line, or copy it, and let Robyn run it. This needs no
suspend and has no editor-argument rules, but it's a step slower.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:40-50` (bindings, `g`)
- `src/claude-viewer/claude_viewer/transcript.py:201-209` (keep `toolUseResult.file.startLine`
  for Read)
- `docs/claude-viewer/project.md` (Keys)

## Open Questions
- Does `nvr --remote-wait` accept `+N`? This is believed but not tested. Settled by one
  run.

## Priority
Medium

## Related Files
- `docs/architecture.md` (the `structuredPatch` shape)
