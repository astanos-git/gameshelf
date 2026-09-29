"""Save a Beaten / Dropped flag from a GitHub issue into docs/flags.json.

Run by .github/workflows/flag.yml when you tap a flag button on the dashboard.
Env: ISSUE_BODY (contains "game: <name>" and "flag: beaten|dropped|none"), ISSUE_CREATED (ISO time).
Writes a one-line result to flag_result.txt for the issue comment.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent
FLAGS = ROOT / "docs" / "flags.json"
DATA = ROOT / "docs" / "data.json"
RESULT = ROOT / "flag_result.txt"
LABELS = {"beaten": "Beaten", "dropped": "Dropped"}


def parse(body: str) -> tuple[str | None, str | None]:
    game = re.search(r"^game:\s*(.+?)\s*$", body or "", re.M | re.I)
    flag = re.search(r"^flag:\s*(\w+)\s*$", body or "", re.M | re.I)
    return (game.group(1) if game else None), (flag.group(1).lower() if flag else None)


def apply(body: str, created: str) -> str:
    game, flag = parse(body)
    if not game or flag not in ("beaten", "dropped", "none"):
        return "Couldn't read this request. Use the buttons on the dashboard to flag a game."
    names = {g["name"] for g in json.loads(DATA.read_text())["games"]} if DATA.exists() else set()
    if names and game not in names:
        return f"No game called “{game}” on the dashboard, so nothing was changed."

    flags = json.loads(FLAGS.read_text()) if FLAGS.exists() else {}
    if flag == "none":
        flags.pop(game, None)
        msg = f"Removed the flag from {game}."
    else:
        flags[game] = {"flag": flag, "at": created}
        msg = f"{game} is now marked as {LABELS[flag]}."
    FLAGS.write_text(json.dumps(flags, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return msg + " The dashboard updates in about a minute."


if __name__ == "__main__":
    result = apply(os.environ.get("ISSUE_BODY", ""), os.environ.get("ISSUE_CREATED", ""))
    RESULT.write_text(result)
    print(result)
