# Enhancement: Timestamps

## Goal
See when each prompt and tool call happened and how long the gaps and calls took, to find
where a session spent its time.

## Current Behaviour
`Block` (`claude_viewer/transcript.py:25`) has no time. Every `user` and `assistant` record
has a top-level ISO `timestamp` with milliseconds, and so does every `tool_result` record.
The parser ignores them.

## Desired Behaviour
- A key (`t`) toggles a dim time suffix on each prompt and tool header.
- A prompt shows its local time, `HH:MM:SS`.
- A tool call shows its duration, from call to result, and the gap since the previous
  block ended, when that gap is over 5 s.
- With timestamps off, the view is as it is now.
- Check: a Bash call that ran a 30 s build shows about `30s`. A prompt typed 10 minutes after
  the previous reply shows `+10m`.

## Design
### 1. Times on the block, rendered in the header
- **Parser.** Add `time` and `end` to `Block`. Set `time` in `assistant()` and `user()` from
  the record, and set `end` in `tool_result()`.
- **Values.** Duration is `end - time`. The gap is `time` minus the previous block's
  `end or time`.
- **Rendering.** `render_block` takes a `show_times` flag and adds the suffix. Toggling
  clears the cache and lays the view out again.

### 2. A time column in the gutter
Draw the times in a wider gutter in `render_line`. This needs no re-render, but it costs
width on every line.

## Affected Code
- `src/claude-viewer/claude_viewer/transcript.py:25-40, 160-210` (`Block`, record handlers)
- `src/claude-viewer/claude_viewer/render.py:103-170` (headers)
- `src/claude-viewer/claude_viewer/app.py:40-50` (binding)

## Priority
Low

## Related Files
- `docs/architecture.md`
