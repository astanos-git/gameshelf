"""Save Beaten / Dropped flags from a GitHub issue into docs/flags.json.

Run by .github/workflows/flag.yml when you use the flag buttons on the dashboard.
The issue body holds one "flag: beaten|dropped|none" line and one or more "game: <name>" lines.
Env: ISSUE_BODY, ISSUE_CREATED (ISO time). Writes the reply to flag_result.txt.
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


def parse(body: str) -> tuple[list[str], str | None]:
    games = [g.strip() for g in re.findall(r"^game:[ \t]*(.+?)[ \t]*$", body or "", re.M | re.I)]
    flag = re.search(r"^flag:\s*(\w+)\s*$", body or "", re.M | re.I)
    return list(dict.fromkeys(g for g in games if g)), (flag.group(1).lower() if flag else None)


def apply(body: str, created: str) -> str:
    games, flag = parse(body)
    if not games or flag not in ("beaten", "dropped", "none"):
        return "Couldn't read this request. Use the buttons on the dashboard to flag games."

    status = {g["name"]: g.get("status") for g in json.loads(DATA.read_text())["games"]} if DATA.exists() else {}
    flags = json.loads(FLAGS.read_text()) if FLAGS.exists() else {}
    done, skipped = [], []
    for game in games:
        if status and game not in status:
            skipped.append(f"{game} (not on the dashboard)")
        elif flag == "none":
            if flags.pop(game, None):
                done.append(game)
            else:
                skipped.append(f"{game} (had no flag)")
        elif status.get(game) == "completed":
            skipped.append(f"{game} (already completed)")
        else:
            flags[game] = {"flag": flag, "at": created}
            done.append(game)
    FLAGS.write_text(json.dumps(flags, indent=1, sort_keys=True, ensure_ascii=False) + "\n")

    n = f"{len(done)} game{'s' if len(done) != 1 else ''}"
    lines = []
    if done:
        lead = f"Removed the flag from {n}" if flag == "none" else f"Marked {n} as {LABELS[flag]}"
        lines.append(f"{lead}: " + ", ".join(done) + ".")
    if skipped:
        lines.append("Skipped: " + ", ".join(skipped) + ".")
    if done:
        lines.append("The dashboard updates in about a minute.")
    return "\n\n".join(lines)


if __name__ == "__main__":
    result = apply(os.environ.get("ISSUE_BODY", ""), os.environ.get("ISSUE_CREATED", ""))
    RESULT.write_text(result)
    print(result)
