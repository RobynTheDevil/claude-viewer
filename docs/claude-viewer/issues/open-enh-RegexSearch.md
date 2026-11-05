# Enhancement: Regex Search

## Goal
Find blocks with a regular expression, not only a fixed string.

## Current Behaviour
`searchable()` (`claude_viewer/app.py:27-30`) joins a block's text, tool name, result and
string inputs, and lowercases them. `TranscriptView.find()` (`app.py:171-183`) looks for the
lowercased query as a substring. It steps from the cursor with wrap-around, then expands and
selects the match. `SessionScreen._search` (`app.py:260-265`) writes `/query` or
`/query: not found` to the status line. `searchable()` is rebuilt for every block on every
`n` and `N`.

## Desired Behaviour
- The `/` query is a Python regular expression.
- Smart case: the search ignores case unless the query has an uppercase letter.
- An invalid pattern shows `/query: <re error message>` in the status line and moves
  nothing.
- `n` and `N` step forward and back with wrap-around, as now.
- A plain word still matches the way it does today.
- Check: `/Bash\(git` finds a Bash call starting with `git`. `/(` reports an error.
  `/widget` and `/Widget` match differently when the text has only `widget`.

## Design
### 1. Compile on submit, cache the search text
In `on_input_submitted` (`app.py:254`), compile the query with
`re.compile(q, 0 if any(c.isupper() for c in q) else re.I)` and catch `re.error`. Pass the
compiled pattern to `find()`. Stop lowercasing in `searchable()`, and cache its result per
block index, since blocks don't change after parsing.

### 2. A separate regex prompt
Keep `/` as a substring search and add another key for regex. That means two keys for one job,
and the substring case is already a valid regex for plain words. Not recommended.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:27-30` (`searchable`)
- `src/claude-viewer/claude_viewer/app.py:171-183` (`find`)
- `src/claude-viewer/claude_viewer/app.py:254-265` (submit and status)
- `src/claude-viewer/tests/test_viewer.py`

## Priority
Medium

## Related Files
- `docs/claude-viewer/project.md` (Keys)
- Match highlighting is a separate item, HighlightMatches.
