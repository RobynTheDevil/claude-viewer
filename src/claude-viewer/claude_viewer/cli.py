from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from claude_viewer.transcript import all_project_dirs, find_session, list_sessions, parse, project_dir_for


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claude-viewer",
        description="View Claude Code session transcripts. With no session, pick one from the current directory's project.",
    )
    parser.add_argument("session", nargs="?", help="session ID, ID prefix, or path to a .jsonl transcript")
    parser.add_argument("-a", "--all", action="store_true", help="pick from every project, not only the current directory's")
    parser.add_argument("-p", "--print", dest="print_", action="store_true", help="print the default view to stdout and exit")
    parser.add_argument("-o", "--export", metavar="FILE", help="write the session as Markdown to FILE, or - for stdout")
    parser.add_argument("--no-usage", dest="usage", action="store_false", help="hide per-message token usage")
    args = parser.parse_args(argv)

    path = None
    if args.session:
        try:
            path = find_session(args.session)
        except LookupError as err:
            print(f"claude-viewer: {err}", file=sys.stderr)
            return 2
    elif args.print_ or args.export:
        print("claude-viewer: --print and --export need a session", file=sys.stderr)
        return 1

    if args.export:
        from claude_viewer.export import to_markdown

        text = to_markdown(parse(path), usage=args.usage)
        if args.export == "-":
            sys.stdout.write(text)
        else:
            Path(args.export).write_text(text, encoding="utf-8")
        return 0

    if args.print_:
        from claude_viewer.render import print_session

        print_session(parse(path), usage=args.usage)
        return 0

    from claude_viewer.app import ViewerApp

    if path is not None:
        ViewerApp(session=parse(path), show_usage=args.usage).run()
        return 0

    directories = all_project_dirs() if args.all else [project_dir_for(os.getcwd())]
    sessions = list_sessions(directories)
    if not sessions:
        where = "any project" if args.all else os.getcwd()
        print(f"claude-viewer: no sessions for {where}; try --all", file=sys.stderr)
        return 2
    ViewerApp(sessions=sessions, show_project=args.all, show_usage=args.usage).run()
    return 0
