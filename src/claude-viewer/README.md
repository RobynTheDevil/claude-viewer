# claude-viewer

A terminal viewer for [Claude Code](https://claude.com/claude-code) session transcripts. It
shows a session the way Claude Code's `/resume` view does, with colored diffs, syntax-colored
commands, search, and expand or collapse of every call to one tool. It can also print a
session or export it to Markdown.

## Install

Needs Python 3.12 or newer. From a clone of this repository:

```sh
uv tool install ./src/claude-viewer
```

or with pipx:

```sh
pipx install ./src/claude-viewer
```

## Use

```sh
claude-viewer                  # pick a session from the current directory's project
claude-viewer --all            # pick from every project
claude-viewer <session>        # open a session by ID, ID prefix or .jsonl path
claude-viewer <session> --print            # print the session to stdout
claude-viewer <session> --export out.md    # write it as Markdown; - for stdout
```

Transcripts are read from `~/.claude/projects`, or from `$CLAUDE_CONFIG_DIR/projects` when
that is set. `--usage` shows per-message token usage, which is hidden by default.

## Keys

Vim style, with less's paging keys too. Press `?` in a session for the full list.

| Key | Action |
|---|---|
| `j`/`k`, arrows | move a line |
| `d`/`u`, Space/`ctrl+b` | half page down/up, page down/up |
| `}`/`{`, `]]`/`[[` | next or previous block, prompt |
| `gg`/`G` | top, bottom |
| Enter, `o`/`x` | toggle, open or close a block |
| `O`/`X` | open or close every block like this one |
| `E`/`C` | open or close everything |
| `f` | filter: all, read-only, changes |
| `U`, `t` | show token usage, times |
| `-` | outline of prompts |
| `/`, `n`/`N` | search, next and previous match |
| `v`/`V`, `y` | select, copy |
| `gf` | open the file a call touched in your editor |
| `ctrl+s` | show the scrollbar |
| `q`, Esc | back to the session list |
| `ctrl+c` | quit |

`gf` uses `$VISUAL`, then `$EDITOR`, then `nvim`, then `less`.

## License

MIT. See [LICENSE](LICENSE).
