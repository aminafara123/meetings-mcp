# meetings-mcp

An MCP server over the output of my [meeting-transcription-pipeline](https://github.com/aminafara123/meeting-transcription-pipeline). It takes the finished transcripts (Whisper text, speaker labeled with pyannote) and exposes them as tools any MCP-capable AI client can call.

The pipeline turns a recording into a long text file. Thats useful, but nobody rereads two hours of meeting. With this server a model can list the meetings, page through one, or search all of them for a topic and come back with the exact timestamp.

## Tools

| Tool | What it does |
|---|---|
| `list_meetings()` | Every transcript with its id, length, turn count and speaker count |
| `get_transcript(meeting, start)` | One page of 25 speaker turns, with the start value for the next page |
| `search_transcripts(query)` | Case-insensitive search across all meetings, with meeting id, timestamp and turn number per hit |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install mcp
```

Wire it into Claude Code:

```bash
claude mcp add meetings -- /path/to/meetings-mcp/.venv/bin/python /path/to/meetings-mcp/server.py
```

## Demo

What it looks like from Claude Code:

```
> did we talk about the renewal in any recent meeting?

⏺ meetings · list_meetings()

  2 meeting(s):
  - 2026-09-21-vendor-review: 00:41:09, 4 turns, 3 speaker(s)
  - 2026-09-24-weekly-sync: 00:18:47, 3 turns, 2 speaker(s)

⏺ meetings · search_transcripts("renewal")

  3 match(es) for 'renewal':

  [2026-09-21-vendor-review @ 00:03:12, turn 1] Speaker 2: The renewal quote came in higher, about fifteen percent.
  [2026-09-21-vendor-review @ 00:07:40, turn 2] Speaker 1: Then we push back on the renewal before Friday.
  [2026-09-24-weekly-sync @ 00:12:30, turn 1] Speaker 2: The renewal is signed, same price as last year.

⏺ Yes, twice. In the vendor review the quote came in about 15% higher
  and the plan was to push back. By the weekly sync it was signed at
  last year's price.
```

The meetings above are demo data. The format is exactly what the server returns.

## Design notes

- **Read-only by construction.** Every tool reads text files, nothing writes. The transcripts stay on my machine and the model only sees what a tool returns.
- **Pseudonyms at the boundary.** Speaker labels become Speaker 1, Speaker 2 and so on by first appearance, even when the source file has real names. Emails, phone numbers, home paths and long tokens get replaced before anything crosses the protocol.
- **Paged, not dumped.** A two hour meeting is hundreds of turns. The server hands it over 25 turns at a time so a model reads what it needs instead of flooding its context.

## Honest notes

- It reads the pipeline's `transcripts/` folder, one `.speakers.txt` per meeting, falling back to the raw Whisper `.txt` when diarization hasnt run. You need to run the pipeline first. `DATA_DIR` at the top of `server.py` points at my local copy, change it for yours.
- The redaction is pattern based. It catches speaker labels, emails, phone numbers and paths, but a name spoken inside a sentence still comes through as said.
- Search is a plain substring match, so an Arabic query has to match the spelling Whisper produced.
- The logic is tested against synthetic transcripts in `test_server.py`. Run `python test_server.py`.

## About

Al Amin Bashir Afara, Dubai · [github.com/aminafara123](https://github.com/aminafara123) · [linkedin.com/in/aminafara](https://www.linkedin.com/in/aminafara)
