from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>\s*", re.S)
COMMAND_NAME = re.compile(r"<command-name>(.*?)</command-name>", re.S)
COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
LOCAL_STDOUT = re.compile(r"<local-command-std(?:out|err)>(.*?)</local-command-std(?:out|err)>", re.S)
ATTACHMENT_KINDS = {"file", "image", "pdf", "directory"}


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def projects_root() -> Path:
    return claude_home() / "projects"


def project_dir_for(cwd: str) -> Path:
    return projects_root() / re.sub(r"[^A-Za-z0-9]", "-", cwd)


@dataclass
class Block:
    kind: str
    text: str = ""
    tool: str = ""
    tool_id: str = ""
    input: dict = field(default_factory=dict)
    result: str | None = None
    is_error: bool = False
    patch: list | None = None
    usage: dict | None = None
    model: str = ""
    msg_id: str = ""
    collapsed: bool = True

    @property
    def group(self) -> str:
        return self.tool if self.kind == "tool" else self.kind

    @property
    def collapsible(self) -> bool:
        return self.kind in {"tool", "thinking", "usage", "note"}


@dataclass
class Session:
    path: Path
    title: str
    blocks: list[Block]

    @property
    def session_id(self) -> str:
        return self.path.stem


@dataclass
class SessionInfo:
    path: Path
    title: str
    mtime: float
    size: int

    @property
    def session_id(self) -> str:
        return self.path.stem

    @property
    def project(self) -> str:
        return self.path.parent.name

    @property
    def when(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "image":
                parts.append("[Image]")
        return "\n".join(parts)
    return ""


def _prompt_text(text: str) -> str:
    name = COMMAND_NAME.search(text)
    if name:
        args = COMMAND_ARGS.search(text)
        command = name.group(1).strip()
        return f"{command} {args.group(1).strip()}".strip() if args else command
    return REMINDER.sub("", text).strip()


class _Parser:
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self.tools: dict[str, Block] = {}
        self.usage: dict[str, tuple[str, dict]] = {}
        self.seen: set[str] = set()
        self.title = ""
        self.first_prompt = ""

    def record(self, rec: dict) -> None:
        kind = rec.get("type")
        if kind == "attachment":
            self.attachment(rec.get("attachment") or {})
            return
        if kind not in ("user", "assistant") or rec.get("isSidechain"):
            return
        uid = rec.get("uuid")
        if uid in self.seen:
            return
        self.seen.add(uid)
        if kind == "assistant":
            self.assistant(rec)
        else:
            self.user(rec)

    def attachment(self, att: dict) -> None:
        if att.get("type") not in ATTACHMENT_KINDS:
            return
        name = att.get("filename") or att.get("path") or att.get("displayPath") or att.get("type")
        self.blocks.append(Block("image", text=f"Attached {name}"))

    def assistant(self, rec: dict) -> None:
        msg = rec.get("message") or {}
        msg_id = msg.get("id", "")
        model = msg.get("model", "")
        if msg.get("usage") and msg_id:
            self.usage[msg_id] = (model, msg["usage"])
        content = msg.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for item in content or []:
            t = item.get("type")
            if t == "text" and item.get("text", "").strip():
                self.blocks.append(Block("text", text=item["text"].strip(), msg_id=msg_id, collapsed=False))
            elif t == "thinking" and item.get("thinking", "").strip():
                self.blocks.append(Block("thinking", text=item["thinking"].strip(), msg_id=msg_id))
            elif t in ("tool_use", "server_tool_use"):
                block = Block(
                    "tool",
                    tool=item.get("name", "?"),
                    tool_id=item.get("id", ""),
                    input=item.get("input") or {},
                    msg_id=msg_id,
                )
                self.tools[block.tool_id] = block
                self.blocks.append(block)

    def user(self, rec: dict) -> None:
        if rec.get("isMeta"):
            return
        msg = rec.get("message") or {}
        content = msg.get("content")
        origin = rec.get("origin")
        origin_kind = origin.get("kind") if isinstance(origin, dict) else origin
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        texts = []
        for item in content or []:
            t = item.get("type")
            if t == "tool_result":
                self.tool_result(item, rec.get("toolUseResult"))
            elif t == "text":
                texts.append(item.get("text", ""))
            elif t == "image":
                self.blocks.append(Block("image", text="[Image]"))
        if not texts:
            return
        raw = "\n".join(texts)
        stdout = LOCAL_STDOUT.search(raw)
        if stdout:
            body = stdout.group(1).strip()
            if body:
                self.blocks.append(Block("note", text=body))
            return
        text = _prompt_text(raw)
        if not text:
            return
        if origin_kind not in (None, "human"):
            self.blocks.append(Block("note", text=text))
            return
        if not self.first_prompt:
            self.first_prompt = text
        self.blocks.append(Block("prompt", text=text, collapsed=False))

    def tool_result(self, item: dict, extra) -> None:
        block = self.tools.get(item.get("tool_use_id", ""))
        if block is None:
            return
        block.result = _result_text(item.get("content"))
        block.is_error = bool(item.get("is_error"))
        if isinstance(extra, dict) and extra.get("structuredPatch"):
            block.patch = extra["structuredPatch"]
            block.collapsed = False

    def finish(self) -> list[Block]:
        last: dict[str, int] = {}
        for i, block in enumerate(self.blocks):
            if block.msg_id:
                last[block.msg_id] = i
        after = {i: msg_id for msg_id, i in last.items()}
        out = []
        for i, block in enumerate(self.blocks):
            out.append(block)
            msg_id = after.get(i)
            if msg_id and msg_id in self.usage:
                model, usage = self.usage[msg_id]
                out.append(Block("usage", model=model, usage=usage, msg_id=msg_id))
        return out


def _lines(path: Path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        yield from fh


def parse(path: Path) -> Session:
    parser = _Parser()
    for line in _lines(path):
        if line.startswith('{"type":'):
            if line.startswith('{"type":"ai-title"'):
                parser.title = json.loads(line).get("aiTitle") or parser.title
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        parser.record(rec)
    text = parser.title or parser.first_prompt
    title = text.splitlines()[0][:100] if text else path.stem
    return Session(path=path, title=title, blocks=parser.finish())


def session_title(path: Path) -> str:
    title = ""
    first = ""
    for line in _lines(path):
        if line.startswith('{"type":"ai-title"'):
            try:
                title = json.loads(line).get("aiTitle") or title
            except ValueError:
                pass
        elif not first and not title and line.startswith('{"parentUuid"') and '"type":"user"' in line and '"tool_result"' not in line:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            content = (rec.get("message") or {}).get("content")
            if rec.get("isMeta"):
                continue
            if isinstance(content, list):
                content = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
            if isinstance(content, str):
                first = _prompt_text(content)
    text = title or first or "(no prompt)"
    return text.splitlines()[0][:100] if text else text


def list_sessions(directories: list[Path]) -> list[SessionInfo]:
    found = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in directory.glob("*.jsonl"):
            st = path.stat()
            if st.st_size == 0:
                continue
            found.append(SessionInfo(path=path, title=session_title(path), mtime=st.st_mtime, size=st.st_size))
    found.sort(key=lambda s: s.mtime, reverse=True)
    return found


def all_project_dirs() -> list[Path]:
    root = projects_root()
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def find_session(arg: str) -> Path:
    path = Path(arg).expanduser()
    if path.is_file():
        return path
    matches = sorted(projects_root().glob(f"*/{arg}*.jsonl"))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise LookupError(f"no session matches {arg!r}")
    raise LookupError(f"{len(matches)} sessions match {arg!r}; give more of the ID")
