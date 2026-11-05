# Enhancement: Syntax Highlight Output

## Goal
Color code in Read output and in diffs by the file's language, as Claude Code does.

## Current Behaviour
- **Read output.** Expanded Read output is plain text (`claude_viewer/render.py:127-131`).
  In transcripts, Read results are `N\t` plus the code line (287 of 287 numbered results).
  `toolUseResult.file` holds the raw `content`, `startLine`, `numLines`, `totalLines` and
  `filePath`. The parser drops it (`transcript.py:201-209`).
- **Diffs.** These get only add and remove backgrounds (`render.py:80-100`).
- **File types.** Local Reads by extension: md 140, rs 109, none 39, txt 20, sh 12.

## Desired Behaviour
- An expanded Read shows the code with syntax colors and its real line numbers, picked by
  the file's extension.
- Diff lines keep their add and remove backgrounds and also get syntax colors.
- A file type with no lexer, or no extension, renders as it does now.
- The Markdown export is unchanged.
- Check: expand a Read of a `.rs` file and an Edit of a `.py` file. Both show keyword colors,
  and the diff's `+` lines keep the green background.

## Design
### 1. Rich Syntax from the structured result
- **Read.** Store `toolUseResult.file` on the block. Render it with
  `Syntax(content, Syntax.guess_lexer(path, content), line_numbers=True, start_line=startLine)`.
  It is only rendered when the block is expanded, since a collapsed Read shows `Read N lines`.
- **Diffs.** Highlight each hunk's code once with `Syntax.highlight`, then stylize each line
  with the add or remove background.

Reads run up to about 1000 lines (median 33). A resize re-renders every expanded block, so
measure with several large Reads expanded.

### 2. Strip the `N\t` prefix from the result text
Highlight the text result after removing the prefixes. This needs no parser change, but it
breaks if the prefix format changes.

## Affected Code
- `src/claude-viewer/claude_viewer/transcript.py:201-209` (`tool_result`)
- `src/claude-viewer/claude_viewer/render.py:80-133` (`diff`, `tool_body`)

## Open Questions
- Does a Syntax theme background cover the diff backgrounds? Settled: yes. Monokai's
  token styles each carry `on #272822`, so only the foreground of each token is kept.

## Priority
Low

## Related Files
- `docs/architecture.md`
