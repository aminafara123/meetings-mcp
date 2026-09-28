"""Smoke test over synthetic transcripts. Run: python test_server.py (or pytest)."""

import tempfile
from pathlib import Path

import server


def test_tools():
    with tempfile.TemporaryDirectory() as d:
        server.DATA_DIR = Path(d)
        turns = "\n\n".join(
            f"[00:{i // 60:02d}:{i % 60:02d}] {'Dana Example' if i % 2 else 'Omar Sample'}:\n"
            f"line {i} about the budget"
            for i in range(30)
        )
        (server.DATA_DIR / "demo-standup.speakers.txt").write_text(
            turns + "\n\n[00:00:59] Dana Example:\nmail me at dana@example.com "
            "or call +971 50 123 4567, file in /home/someone/notes.txt\n",
            encoding="utf-8",
        )
        (server.DATA_DIR / "demo-standup.txt").write_text(
            "[00:00:00] raw line\n", encoding="utf-8")
        (server.DATA_DIR / "demo-sync.txt").write_text(
            "[00:00:05] kickoff for the roadmap on 2026-10-01\n[00:01:10] wrap up\n",
            encoding="utf-8")

        listing = server.list_meetings()
        assert listing.startswith("2 meeting(s):")
        assert "- demo-standup: 00:00:59, 31 turns, 2 speaker(s)" in listing
        assert "- demo-sync: 00:01:10, 2 turns, no speaker labels" in listing

        page = server.get_transcript("demo-standup")
        assert "turns 1 to 25 of 31" in page
        assert "[00:00:00] Speaker 1: line 0 about the budget" in page
        assert "[00:00:01] Speaker 2: line 1" in page
        assert "Omar" not in page and "Dana" not in page
        assert "call again with start=25" in page

        last = server.get_transcript("demo-standup", 25)
        assert "[email]" in last and "[number]" in last and "[path]" in last
        assert "example.com" not in last and "/home/" not in last
        assert "more turns" not in last

        sync = server.get_transcript("demo-sync")
        assert sync.endswith("[00:01:10] wrap up") and "2026-10-01" in sync
        assert server.get_transcript("nope").startswith("No meeting with id")

        hits = server.search_transcripts("BUDGET")
        assert hits.startswith("30 match(es)") and "...and 5 more" in hits
        assert "[demo-standup @ 00:00:03, turn 3] Speaker 2: line 3" in hits
        assert "[demo-sync @ 00:00:05, turn 0] kickoff" in server.search_transcripts("roadmap")
        assert server.search_transcripts("zebra").startswith("No turns")
        assert server.search_transcripts("  ") == "Empty query."

        server.DATA_DIR = Path(d) / "missing"
        assert server.list_meetings() == "No transcripts found."


if __name__ == "__main__":
    test_tools()
    print("ok")
