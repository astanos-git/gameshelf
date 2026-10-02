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
QUEUE = ROOT / "docs" / "queue.json"
WISHLIST = ROOT / "docs" / "wishlist.json"
FEEDBACK = ROOT / "docs" / "pick_feedback.json"
RECS = ROOT / "docs" / "recommendations.json"
QUEUE_MAX = 5


def _load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def _save(p: Path, value) -> None:
    p.write_text(json.dumps(value, indent=1, sort_keys=isinstance(value, dict), ensure_ascii=False) + "\n")


def apply_queue(body: str) -> str | None:
    """Up next: "queue: add|remove|set" and one or more "game:" lines (set = the full list in order)."""
    m = re.search(r"^queue:\s*(add|remove|set)\s*$", body or "", re.M | re.I)
    if not m:
        return None
    action = m.group(1).lower()
    data = _load(DATA, {}).get("games", [])
    current = {a: g["name"] for g in data for a in g.get("aliases", [])}
    names = {g["name"] for g in data}
    games = [current.get(g, g) for g in parse(body)[0]]
    unknown = [g for g in games if names and g not in names]
    games = [g for g in games if g not in unknown]
    queue = [current.get(g, g) for g in _load(QUEUE, [])]
    if action == "set":
        queue = games
    elif action == "add":
        queue += [g for g in games if g not in queue]
    else:
        queue = [g for g in queue if g not in games]
    dropped = queue[QUEUE_MAX:]
    queue = list(dict.fromkeys(queue))[:QUEUE_MAX]
    _save(QUEUE, queue)
    msg = "Up next: " + (", ".join(f"{i + 1}. {g}" for i, g in enumerate(queue)) if queue else "empty") + "."
    if dropped:
        msg += f" Up next holds {QUEUE_MAX} games, so {', '.join(dropped)} didn't fit."
    if unknown:
        msg += f" Not on the dashboard: {', '.join(unknown)}."
    return msg + " The dashboard updates in about a minute."


def apply_wish(body: str, created: str) -> str | None:
    """Wishlist (dashboard only): "wish: add|remove", "slug:" and, when adding, "name:"."""
    m = re.search(r"^wish:\s*(add|remove)\s*$", body or "", re.M | re.I)
    if not m:
        return None
    slug = re.search(r"^slug:\s*([a-z0-9-]+)\s*$", body, re.M)
    if not slug:
        return "Couldn't read this request. Use the wishlist buttons on the dashboard."
    slug = slug.group(1)
    wl = _load(WISHLIST, {})
    if m.group(1).lower() == "remove":
        gone = wl.pop(slug, None)
        _save(WISHLIST, wl)
        return (f"Removed {gone['name']} from your wishlist." if gone else "That game wasn't on your wishlist.") + " The dashboard updates in about a minute."
    pick = next((p for p in _load(RECS, {}).get("picks", []) if p["slug"] == slug), None)
    name = re.search(r"^name:\s*(.+?)\s*$", body, re.M)
    info = {k: pick.get(k) for k in ("name", "image", "metacritic", "released", "genres", "platforms", "length", "url")} if pick else \
        {"name": name.group(1) if name else slug, "url": f"https://rawg.io/games/{slug}"}
    wl[slug] = {**info, "added": created}
    _save(WISHLIST, wl)
    return f"Added {wl[slug]['name']} to your wishlist. The dashboard updates in about a minute."


def apply_feedback(body: str, created: str) -> str | None:
    """👍 / 👎 on a weekly pick: "feedback: up|down|none" and "slug:"."""
    m = re.search(r"^feedback:\s*(up|down|none)\s*$", body or "", re.M | re.I)
    if not m:
        return None
    slug = re.search(r"^slug:\s*([a-z0-9-]+)\s*$", body, re.M)
    if not slug:
        return "Couldn't read this request. Use the buttons under this week's picks."
    slug, fb = slug.group(1), m.group(1).lower()
    store = _load(FEEDBACK, {})
    if fb == "none":
        gone = store.pop(slug, None)
        _save(FEEDBACK, store)
        return (f"Removed your feedback on {gone['name']}." if gone else "No feedback to remove.") + " The dashboard updates in about a minute."
    pick = next((p for p in _load(RECS, {}).get("picks", []) if p["slug"] == slug), None) or store.get(slug) or {"name": slug}
    store[slug] = {"feedback": fb, "at": created, "name": pick.get("name"), "genres": pick.get("genres", []), "tags": pick.get("tags", [])}
    _save(FEEDBACK, store)
    return (f"Noted: you like the look of {store[slug]['name']}. Future picks will lean towards games like it."
            if fb == "up" else f"Noted: {store[slug]['name']} isn't for you. It won't be suggested again, and similar games will rank lower.") \
        + " The dashboard updates in about a minute."


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
    for handler in (lambda: apply_goals(body, created), lambda: apply_queue(body),
                    lambda: apply_wish(body, created), lambda: apply_feedback(body, created)):
        msg = handler()
        if msg:
            return msg
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


def apply_batch(body: str, created: str) -> str:
    """Several changes in one request, separated by "---" lines (sent from the dashboard's pending changes)."""
    blocks = [b for b in re.split(r"^\s*---\s*$", body or "", flags=re.M) if re.search(r"^\s*[a-z]+:\s*\S", b, re.M | re.I)]
    if len(blocks) <= 1:
        return apply(body, created)
    lines = [f"Saved {len(blocks)} changes:"]
    for n, block in enumerate(blocks, start=1):
        msg = apply(block, created).replace(" The dashboard updates in about a minute.", "").replace("\n\nThe dashboard updates in about a minute.", "")
        lines.append(f"{n}. " + msg.replace("\n\n", " ").strip())
    return "\n".join(lines) + "\n\nThe dashboard updates in about a minute."


if __name__ == "__main__":
    result = apply_batch(os.environ.get("ISSUE_BODY", ""), os.environ.get("ISSUE_CREATED", ""))
    RESULT.write_text(result)
    print(result)
