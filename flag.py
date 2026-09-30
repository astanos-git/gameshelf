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
RATINGS = ROOT / "docs" / "ratings.json"
GOALS = ROOT / "docs" / "goals.json"
GOAL_KEYS = {"platinums": "platinums", "finished": "games finished", "trophies": "trophies", "hours": "hours played"}
LABELS = {"beaten": "Beaten", "dropped": "Dropped"}


def parse(body: str) -> tuple[list[str], str | None]:
    games = [g.strip() for g in re.findall(r"^game:[ \t]*(.+?)[ \t]*$", body or "", re.M | re.I)]
    flag = re.search(r"^flag:\s*(\w+)\s*$", body or "", re.M | re.I)
    return list(dict.fromkeys(g for g in games if g)), (flag.group(1).lower() if flag else None)


def apply_rating(games: list[str], value: str, created: str) -> str:
    """Save (or clear) your own 0-100 score for a game."""
    data = json.loads(DATA.read_text())["games"] if DATA.exists() else []
    current = {a: g["name"] for g in data for a in g.get("aliases", [])}
    names = {g["name"] for g in data}
    game = current.get(games[0], games[0])
    if names and game not in names:
        return f"No game called “{game}” on the dashboard, so nothing was changed."
    ratings = json.loads(RATINGS.read_text()) if RATINGS.exists() else {}
    if value == "none":
        msg = f"Removed your rating for {game}." if ratings.pop(game, None) else f"{game} had no rating, so nothing changed."
    else:
        ratings[game] = {"score": int(value), "at": created}
        msg = f"Rated {game} {int(value)}/100."
    RATINGS.write_text(json.dumps(ratings, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return msg + " The dashboard updates in about a minute."


def apply_goals(body: str, created: str) -> str | None:
    """Yearly goals: a "goal: <year>" line, then any of "platinums: 6", "finished: 20", "trophies: 500", "hours: 300"."""
    year = re.search(r"^goal:\s*(\d{4})\s*$", body or "", re.M | re.I)
    if not year:
        return None
    y = year.group(1)
    goals = json.loads(GOALS.read_text()) if GOALS.exists() else {}
    if re.search(r"^clear:\s*yes\s*$", body, re.M | re.I):
        msg = f"Removed your goals for {y}." if goals.pop(y, None) else f"No goals for {y}, so nothing changed."
    else:
        new = {k: int(m.group(1)) for k in GOAL_KEYS if (m := re.search(rf"^{k}:\s*(\d{{1,6}})\s*$", body, re.M | re.I)) and int(m.group(1)) > 0}
        if not new:
            return "Couldn't read any goal. Use the goal form on the Review page."
        goals[y] = {**new, "at": created}
        msg = f"Goals for {y}: " + ", ".join(f"{v} {GOAL_KEYS[k]}" for k, v in new.items()) + "."
    GOALS.write_text(json.dumps(goals, indent=1, sort_keys=True) + "\n")
    return msg + " The dashboard updates in about a minute."


def apply(body: str, created: str) -> str:
    goal_msg = apply_goals(body, created)
    if goal_msg:
        return goal_msg
    games, flag = parse(body)
    rating = re.search(r"^rating:\s*(100|[1-9]?\d|none)\s*$", body or "", re.M | re.I)
    if games and rating:
        return apply_rating(games, rating.group(1).lower(), created)
    if not games or flag not in ("beaten", "dropped", "none"):
        return "Couldn't read this request. Use the buttons on the dashboard to flag games."

    data = json.loads(DATA.read_text())["games"] if DATA.exists() else []
    status = {g["name"]: g.get("status") for g in data}
    current = {a: g["name"] for g in data for a in g.get("aliases", [])}  # older names -> name shown now
    flags = json.loads(FLAGS.read_text()) if FLAGS.exists() else {}
    for old, new in current.items():  # move flags saved under an older name
        if old in flags and new not in flags:
            flags[new] = flags.pop(old)
    done, skipped = [], []
    for game in [current.get(g, g) for g in games]:
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
