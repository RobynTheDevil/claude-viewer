import json

import pytest


def _records():
    meta = {"sessionId": "s1"}
    yield {"type": "mode", "mode": "normal", **meta}
    yield {"type": "ai-title", "aiTitle": "Fix the widget", **meta}
    yield {"parentUuid": None, "isSidechain": False, "type": "user", "uuid": "u1",
           "message": {"role": "user", "content": "<command-message>startup</command-message>\n<command-name>/startup</command-name>\n<command-args>bobbins</command-args>"},
           "origin": {"kind": "human"}}
    yield {"parentUuid": "u1", "isSidechain": False, "type": "user", "uuid": "u2", "isMeta": True,
           "message": {"role": "user", "content": [{"type": "text", "text": "Skill body that stays hidden"}]}}
    yield {"parentUuid": "u2", "isSidechain": False, "type": "user", "uuid": "u3",
           "message": {"role": "user", "content": "<system-reminder>secret</system-reminder>\nPlease fix the widget"}}
    yield {"parentUuid": "u3", "isSidechain": False, "type": "assistant", "uuid": "a1",
           "message": {"id": "m1", "model": "claude-opus-5-5", "role": "assistant",
                       "content": [{"type": "thinking", "thinking": "Look at widget.py", "signature": "x"}],
                       "usage": {"input_tokens": 10, "output_tokens": 5}}}
    yield {"parentUuid": "a1", "isSidechain": False, "type": "assistant", "uuid": "a2",
           "message": {"id": "m1", "model": "claude-opus-5-5", "role": "assistant",
                       "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls -la", "description": "List"}}],
                       "usage": {"input_tokens": 10, "output_tokens": 40}}}
    yield {"parentUuid": "a2", "isSidechain": False, "type": "user", "uuid": "u4",
           "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "a\nb\nc\nd\ne"}]}}
    yield {"parentUuid": "u4", "isSidechain": False, "type": "assistant", "uuid": "a3",
           "message": {"id": "m2", "model": "claude-opus-5-5", "role": "assistant",
                       "content": [{"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "/w/widget.py", "old_string": "x = 1", "new_string": "x = 2"}}],
                       "usage": {"input_tokens": 3, "output_tokens": 7}}}
    yield {"parentUuid": "a3", "isSidechain": False, "type": "user", "uuid": "u5",
           "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "The file has been updated."}]},
           "toolUseResult": {"filePath": "/w/widget.py", "structuredPatch": [
               {"oldStart": 4, "oldLines": 3, "newStart": 4, "newLines": 3, "lines": [" a", "-x = 1", "+x = 2", " b"]}]}}
    yield {"parentUuid": "u5", "isSidechain": False, "type": "assistant", "uuid": "a3",
           "message": {"id": "m2", "role": "assistant", "content": [{"type": "text", "text": "duplicate record"}]}}
    yield {"parentUuid": "u5", "isSidechain": True, "type": "assistant", "uuid": "side",
           "message": {"id": "m9", "role": "assistant", "content": [{"type": "text", "text": "sidechain text"}]}}
    yield {"parentUuid": "u5", "isSidechain": False, "type": "assistant", "uuid": "a4",
           "message": {"id": "m3", "model": "claude-opus-5-5", "role": "assistant",
                       "content": [{"type": "text", "text": "Fixed **the widget**."}],
                       "usage": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 2048}}}
    yield {"type": "api-request-blob", "message": {"role": "user", "content": "ignored"}}


@pytest.fixture
def transcript(tmp_path):
    path = tmp_path / "11111111-2222-3333-4444-555555555555.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in _records():
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        fh.write("not json\n")
    return path
