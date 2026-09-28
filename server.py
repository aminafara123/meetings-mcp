#!/usr/bin/env python3
"""meetings-mcp: an MCP server over my meeting-transcription-pipeline output.

Exposes the finished transcripts (Whisper text, speaker labeled by
pyannote) as read-only tools any MCP-capable model can call.

Run (stdio):  python server.py
Wire into Claude Code:
  claude mcp add meetings -- /path/to/.venv/bin/python /path/to/server.py
"""

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

DATA_DIR = Path.home() / "aiProjects/transcript/transcripts"

PAGE = 25
HEADER = re.compile(r"^\[(\d\d:\d\d:\d\d)\] (.+):$")
LINE = re.compile(r"^\[(\d\d:\d\d:\d\d)\] (.*)$")

# Contact details, secrets and personal paths never leave this server.
REDACT = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\+?\d(?:[ ()-]{0,2}\d){8,}"), "[number]"),
    (re.compile(r"(?:/home/|/Users/|[A-Za-z]:\\Users\\)\S+"), "[path]"),
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "[token]"),
]

server = MCPServer(
    "meetings",
    instructions=(
        "Read-only tools over local meeting transcripts (mixed English and "
        "Arabic, speaker labeled). Speakers are shown as Speaker N, numbered "
        "by first appearance in each meeting."
    ),
)

# Every tool only reads local transcript files, so one shared annotation set.
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def _redact(text: str) -> str:
    for pattern, sub in REDACT:
        text = pattern.sub(sub, text)
    return text


def _meetings() -> dict:
    # Prefer the speaker labeled file, fall back to the raw Whisper .txt.
    found = {}
    for p in sorted(DATA_DIR.glob("*.txt")):
        stem = p.name.removesuffix(".speakers.txt").removesuffix(".txt")
        if p.name.endswith(".speakers.txt") or stem not in found:
            found[stem] = p
    return found


def _blocks(path: Path) -> list:
    """(timestamp, speaker, text) per turn, speakers pseudonymized."""
    text = path.read_text(encoding="utf-8")
    out = []
    if path.name.endswith(".speakers.txt"):
        names = {}
        for block in text.split("\n\n"):
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            m = HEADER.match(lines[0]) if lines else None
            if not m:
                continue
            speaker = names.setdefault(m.group(2), f"Speaker {len(names) + 1}")
            out.append((m.group(1), speaker, _redact(" ".join(lines[1:]))))
    else:
        for line in text.splitlines():
            m = LINE.match(line.strip())
            if m:
                out.append((m.group(1), "", _redact(m.group(2))))
    return out


def _fmt(ts: str, speaker: str, body: str) -> str:
    return f"[{ts}] {speaker}: {body}" if speaker else f"[{ts}] {body}"


@server.tool(annotations=READ_ONLY)
def list_meetings() -> str:
    """Every transcribed meeting with its id, length, turn count and number
    of distinct speakers. Use the id with get_transcript."""
    meetings = _meetings()
    if not meetings:
        return "No transcripts found."
    rows = []
    for stem, path in meetings.items():
        blocks = _blocks(path)
        length = blocks[-1][0] if blocks else "00:00:00"
        speakers = len({b[1] for b in blocks if b[1]})
        who = f"{speakers} speaker(s)" if speakers else "no speaker labels"
        rows.append(f"- {stem}: {length}, {len(blocks)} turns, {who}")
    extra = (f"\n...and {len(rows) - PAGE} more" if len(rows) > PAGE else "")
    return f"{len(rows)} meeting(s):\n" + "\n".join(rows[:PAGE]) + extra


@server.tool(annotations=READ_ONLY)
def get_transcript(meeting: str, start: int = 0) -> str:
    """One page of a meeting transcript, 25 turns from turn number start.
    Call again with the start value it suggests to read on."""
    path = _meetings().get(meeting)
    if not path:
        return f"No meeting with id {meeting!r}. Call list_meetings for ids."
    blocks = _blocks(path)
    start = max(start, 0)
    page = blocks[start:start + PAGE]
    if not page:
        return f"{meeting} has {len(blocks)} turns, nothing at start={start}."
    head = f"{meeting}: turns {start + 1} to {start + len(page)} of {len(blocks)}\n\n"
    rest = len(blocks) - start - len(page)
    tail = (f"\n\n...and {rest} more turns, call again with start={start + PAGE}"
            if rest > 0 else "")
    return head + "\n".join(_fmt(*b) for b in page) + tail


@server.tool(annotations=READ_ONLY)
def search_transcripts(query: str) -> str:
    """Case-insensitive substring search across every transcript. Returns
    each matching turn with its meeting id and timestamp, text capped."""
    q = query.strip().lower()
    if not q:
        return "Empty query."
    hits = []
    for stem, path in _meetings().items():
        for i, (ts, speaker, body) in enumerate(_blocks(path)):
            if q in body.lower():
                snippet = body if len(body) <= 200 else body[:200] + "..."
                hits.append(f"[{stem} @ {ts}, turn {i}] "
                            + _fmt(ts, speaker, snippet).split("] ", 1)[1])
    if not hits:
        return f"No turns matching {query!r}."
    extra = (f"\n...and {len(hits) - PAGE} more" if len(hits) > PAGE else "")
    return (f"{len(hits)} match(es) for {query!r}:\n\n"
            + "\n".join(hits[:PAGE]) + extra)


if __name__ == "__main__":
    server.run()
