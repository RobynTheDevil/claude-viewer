# Enhancement: Usage Shown By Default

## Goal
Token usage lines are noise most of the time. Start with them hidden and show them on request.

## Current Behaviour
`--no-usage` (`cli.py:20`, `store_false`) is the only way to hide them, so usage shows by
default in the view, `--print` and `--export`. Every signature down the chain defaults to
`True`: `TranscriptView.__init__` (`app.py:132`), `SessionScreen.__init__` (`app.py:650`),
`ViewerApp.__init__` (`app.py:856`), `print_session` (`render.py:381`), `to_markdown`
(`export.py:72`). `U` toggles them in the view (`app.py:553`).

## Desired Behaviour
- No flag: no usage lines in the view, `--print` or `--export`.
- `--usage` shows them everywhere; `--no-usage` still parses and hides them.
- `U` shows them, and a second `U` hides them again.

## Design
### 1. Flip the default
`--usage`/`--no-usage` as one `BooleanOptionalAction` with `default=False`, and every
signature default set to `False`. Parsing still makes usage blocks, so `U` needs nothing new.

## Affected Code
- `src/claude-viewer/claude_viewer/cli.py:20`
- `src/claude-viewer/claude_viewer/app.py:132`, `:650`, `:856`
- `src/claude-viewer/claude_viewer/render.py:381`
- `src/claude-viewer/claude_viewer/export.py:72`
- `src/claude-viewer/tests/test_viewer.py:237-274`: the usage toggle and filter tests assume shown

## Priority
Medium

## Related Files
- `docs/claude-viewer/issues/done/done-enh-HideTokenUsage.md`
