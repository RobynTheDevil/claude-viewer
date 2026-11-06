from __future__ import annotations

import os
import re
import shlex

from claude_viewer.transcript import Block

WRITE_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

READ_COMMANDS = {
    "ls", "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "ag", "wc",
    "file", "stat", "du", "df", "pwd", "echo", "printf", "which", "whereis", "type", "diff",
    "cmp", "tree", "jq", "sort", "uniq", "cut", "tr", "column", "nl", "basename", "dirname",
    "realpath", "readlink", "date", "printenv", "id", "whoami", "uname", "hostname", "ps",
    "test", "[", "[[", "true", "false", "sleep", "md5sum", "sha1sum", "sha256sum", "xxd",
    "hexdump", "od", "strings", "cd", "pushd", "popd", "man", "lsof", "nproc", "free",
    "uptime", "seq", "export", "local", "set", "unset", "fd", "bat", "tac", "rev", "fold",
    "comm", "join", "paste", "expand", "look", "zcat", "base64", "cksum", "read", "pgrep",
    "wslpath", "getconf", "locale",
}
WRAPPERS = {"sudo", "time", "nohup", "nice", "builtin", "exec"}
KEYWORDS_DROPPED = {"then", "do", "else", "elif", "while", "until", "if", "!", "{"}
KEYWORDS_READ = {"for", "select", "done", "fi", "esac", "}", "function"}
SEPARATORS = {";", "|", "||", "&&", "&", "|&", ";;", "(", ")"}
REDIRECTS = {">", ">>", "&>", "&>>", ">|"}
SAFE_TARGETS = {"/dev/null", "/dev/stdout", "/dev/stderr"}

GIT_READ = {
    "status", "log", "show", "diff", "blame", "grep", "ls-files", "ls-tree", "rev-parse",
    "rev-list", "describe", "for-each-ref", "show-ref", "cat-file", "shortlog", "merge-base",
    "name-rev", "whatchanged", "count-objects", "check-ignore", "var", "help", "version",
}
GIT_LIST_FLAGS = {"-a", "-v", "-vv", "-r", "--list", "-l", "--all", "--show-current", "--contains", "--merged"}
GH_READ = {"view", "list", "status", "diff", "checks"}

HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def is_write(block: Block) -> bool:
    if block.patch or block.tool in WRITE_TOOLS:
        return True
    if block.tool in SHELL_TOOLS:
        command = block.input.get("command")
        return not isinstance(command, str) or command_writes(command)
    return False


def command_writes(command: str) -> bool:
    for line in logical_lines(command):
        try:
            tokens = tokenize(line)
        except ValueError:
            return True
        for segment in segments(tokens):
            if segment_writes(segment):
                return True
    return False


def logical_lines(command: str) -> list[str]:
    lines = []
    pending = ""
    ending = None
    for raw in command.replace("\\\n", " ").splitlines():
        if ending is not None:
            if raw.strip() == ending:
                ending = None
            continue
        match = HEREDOC.search(raw)
        if match:
            ending = match.group(2)
        pending = f"{pending}\n{raw}" if pending else raw
        try:
            tokenize(pending)
        except ValueError:
            continue
        lines.append(pending)
        pending = ""
    if pending:
        lines.append(pending)
    return lines


def tokenize(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=";|&()<>")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    return list(lexer)


def segments(tokens: list[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for token in tokens:
        if token in SEPARATORS or token == "\n":
            out.append([])
        else:
            out[-1].append(token)
    return [s for s in out if s]


def segment_writes(tokens: list[str]) -> bool:
    words = []
    skip = False
    for n, token in enumerate(tokens):
        if skip:
            skip = False
            continue
        if token in REDIRECTS:
            target = tokens[n + 1] if n + 1 < len(tokens) else ""
            if target not in SAFE_TARGETS:
                return True
            skip = True
        elif token in (">&", "<", "<<", "<<<", "<&"):
            skip = True
        else:
            words.append(token)
    return words_write(words)


def words_write(words: list[str]) -> bool:
    while words:
        head = words[0]
        if head in KEYWORDS_READ:
            return False
        if head in KEYWORDS_DROPPED or head in WRAPPERS or re.match(r"^\w+=", head):
            words = words[1:]
            continue
        if head in ("env", "xargs", "timeout", "watch"):
            words = words[1:]
            while words and (words[0].startswith("-") or re.match(r"^\w+=", words[0]) or (head == "timeout" and words[0][:1].isdigit())):
                words = words[1:]
            continue
        break
    if not words:
        return False
    name = os.path.basename(words[0])
    args = words[1:]
    if name == "command":
        return bool(args) and args[0] not in ("-v", "-V") and words_write(args)
    if name == "git":
        return git_writes(args)
    if name == "gh":
        return not any(a in GH_READ for a in args[1:2])
    if name == "find":
        return any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf", "-fls") for a in args)
    if name == "sed":
        return any(a.startswith("-i") or a == "--in-place" or a.startswith("--in-place=") for a in args)
    if name in ("awk", "gawk"):
        return "inplace" in " ".join(args)
    if name == "tee":
        return any(not a.startswith("-") and a not in SAFE_TARGETS for a in args)
    if name == "sort":
        return any(a == "-o" or a.startswith("--output") for a in args)
    return name not in READ_COMMANDS


def git_writes(args: list[str]) -> bool:
    while args and args[0].startswith("-"):
        args = args[2:] if args[0] in ("-C", "-c") else args[1:]
    if not args:
        return False
    sub, rest = args[0], args[1:]
    if sub in GIT_READ:
        return False
    if sub in ("branch", "tag"):
        return any(a not in GIT_LIST_FLAGS for a in rest)
    if sub == "remote":
        return bool(rest) and rest[0] not in ("-v", "--verbose", "show", "get-url")
    if sub == "config":
        reads = ("--get", "--get-all", "--list", "-l", "--get-regexp", "--show-origin")
        return not any(a in reads for a in rest) and len([a for a in rest if not a.startswith("-")]) != 1
    if sub in ("stash", "worktree", "notes", "reflog"):
        return bool(rest) and rest[0] not in ("list", "show")
    return True
