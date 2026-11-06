from __future__ import annotations

import os
import re

from rich.text import Text

COMMAND = "#a6e22e"
FLAG = "#fd971f"
STRING = "#e6db74"
OPERATOR = "#f92672"
VARIABLE = "#ae81ff"
COMMENT = "#75715e"

KEYWORDS = {
    "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac",
    "function", "select", "!", "{", "}", "[[", "]]",
}
COMMAND_AFTER = {"then", "do", "else", "elif", "if", "while", "until", "!", "{"}
WRAPPERS = {"sudo", "time", "nohup", "nice", "env", "xargs", "exec", "command", "builtin", "timeout", "watch"}
SEPARATORS = {"&&", "||", "|", "|&", ";", ";;", "&", "("}

OPERATOR_RE = re.compile(r"&&|\|\||\|&|;;|[|;&()]|\d*(?:&>>?|>>|>&|>\||<<<|<<-?|<&|<>|>|<)(?:\d+-?|-)?")
VARIABLE_RE = re.compile(r"\$(?:\{[^}]*\}|\w+|[?$!#@*\-0-9])")
WORD_RE = re.compile(r"[^\s;|&()<>'\"$`]+")


def string_end(line: str, i: int, quote: str) -> tuple[int, bool]:
    if quote == "'":
        j = line.find("'", i)
        return (j + 1, True) if j >= 0 else (len(line), False)
    j = i
    while j < len(line):
        if line[j] == "\\":
            j += 2
        elif line[j] == '"':
            return j + 1, True
        else:
            j += 1
    return len(line), False


def append_string(text: Text, part: str, quote: str) -> None:
    start = len(text)
    text.append(part, STRING)
    if quote == '"':
        for m in VARIABLE_RE.finditer(part):
            text.stylize(VARIABLE, start + m.start(), start + m.end())


def highlight_shell(lines: list[str]) -> list[Text]:
    out = []
    quote = None
    continued = False
    for line in lines:
        text = Text()
        expect = quote is None and not continued
        continued = False
        wrapper = False
        redirect = False
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if quote:
                end, closed = string_end(line, i, quote)
                append_string(text, line[i:end], quote)
                quote = None if closed else quote
                i = end
                continue
            if c.isspace():
                j = i
                while j < n and line[j].isspace():
                    j += 1
                text.append(line[i:j])
                i = j
                continue
            if c == "#" and (i == 0 or line[i - 1] in " \t;|&("):
                text.append(line[i:], COMMENT)
                break
            if c == "\\" and i == n - 1:
                text.append(c)
                continued = True
                break
            if c in "'\"":
                end, closed = string_end(line, i + 1, c)
                append_string(text, line[i:end], c)
                quote = None if closed else c
                i = end
                expect = wrapper = redirect = False
                continue
            if line.startswith("$(", i):
                text.append("$(", OPERATOR)
                i += 2
                expect, wrapper, redirect = True, False, False
                continue
            if c == "$":
                m = VARIABLE_RE.match(line, i)
                end = m.end() if m else i + 1
                text.append(line[i:end], VARIABLE)
                i = end
                expect = wrapper = redirect = False
                continue
            m = OPERATOR_RE.match(line, i)
            if m:
                token = m.group()
                text.append(token, OPERATOR)
                i = m.end()
                if token in SEPARATORS:
                    expect, wrapper, redirect = True, False, False
                elif token == ")":
                    expect = redirect = False
                else:
                    redirect = True
                continue
            m = WORD_RE.match(line, i)
            if not m:
                text.append(c)
                i += 1
                continue
            word = m.group()
            i = m.end()
            if redirect:
                text.append(word)
                redirect = False
            elif expect and wrapper and (word.startswith("-") or word[:1].isdigit()):
                text.append(word, FLAG if word.startswith("-") else None)
            elif expect and re.match(r"^\w+=", word):
                name, _, value = word.partition("=")
                text.append(name, VARIABLE)
                text.append("=" + value)
            elif expect and word in KEYWORDS:
                text.append(word, OPERATOR)
                expect = word in COMMAND_AFTER
            elif expect:
                text.append(word, COMMAND)
                wrapper = os.path.basename(word) in WRAPPERS
                expect = wrapper
            elif word.startswith("-"):
                text.append(word, FLAG)
            else:
                text.append(word)
        out.append(text)
    return out
