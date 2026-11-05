# Core architecture

The Claude Code session transcript: one JSONL file per session at
`~/.claude/projects/<project>/<session-id>.jsonl`, or under `$CLAUDE_CONFIG_DIR` when that is
set. Read from transcripts written by Claude Code 2.1.301. There is no published schema, so
everything here is observed and can change with a Claude Code release.

## The one thing to know first

Most of a transcript is not the conversation. Each line is one record, and only `user` and
`assistant` records with `isSidechain: false` hold the main thread. In the largest local
transcript (37 MB), `api-request-blob` records, which copy whole API requests, make up most
of the bytes.

| Record starts with | Holds |
|---|---|
| `{"type":` | session metadata: `mode`, `ai-title`, `last-prompt`, `cost-state`, `api-request*`, `file-history-*`, `worktree-state`, `queue-operation` |
| `{"parentUuid":` | `user`, `assistant`, `attachment` and `system` records |

To show the conversation, read `user` and `assistant` records. To title a session, read the
last `ai-title`. The parser skips any line starting `{"type":` without parsing it, which is
why a 37 MB session parses in 0.07 s.

## Project directories

`<project>` is the session's working directory with every character outside `[A-Za-z0-9]`
replaced by `-`: `/mnt/c/p/x.y/.worktrees/z` becomes `-mnt-c-p-x-y--worktrees-z`. A worktree
is its own project.

## User and assistant records

An assistant message is split across records: one record per content block, all sharing
`message.id`. Each repeats `message.usage`; the last one holds the final counts.

**A `uuid` can repeat.** The same record is sometimes written twice. Keep the first.

**`user` records are mostly not prompts.** In order of how often they occur:

- `tool_result` blocks, paired to the call by `tool_use_id`. The record's top-level
  `toolUseResult` holds the tool's structured result. For Edit and Write it has
  `structuredPatch`: hunks of `oldStart`, `oldLines`, `newStart`, `newLines` and `lines`, each
  line prefixed `+`, `-` or a space.
- `isMeta: true`: text Claude Code injected, such as a loaded skill's body. Not shown.
- `origin.kind` other than `human`, such as `task-notification` or `peer`: not typed by the
  person.
- A slash command: `<command-name>/x</command-name>` with optional `<command-args>`.
- `<local-command-stdout>`: output of a local command.
- `<system-reminder>` blocks inside prompt text. Not shown.

**Every record has a `timestamp`**, ISO 8601 in UTC with milliseconds, as does each
`tool_result` record, so a call's duration is its result's time minus its own.

**Thinking text is usually empty.** A `thinking` block keeps its `signature`, but `thinking`
is `""` unless the session recorded it. Empty ones carry nothing to show.

**`isSidechain: true` records are subagent turns.** They are not shown in the main thread.

## Gaps

- Subagent transcripts: where a subagent's own records live and how they link to the
  `Agent` call that started it has not been read.
- `attachment` records seen locally are all injected context (`total_tokens_reminder`,
  `task_reminder`, `environment` and others). The kinds the parser treats as user
  attachments (`file`, `image`, `pdf`, `directory`) are assumed, not observed.
