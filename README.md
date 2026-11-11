# Game Shelf

A personal PlayStation dashboard you can open from your phone. It shows your games, playtime, trophies (earned and remaining), and Metacritic scores. The data refreshes only when you ask for it.

- **Dashboard** (`docs/`, hosted free on GitHub Pages): Library, Play next, Stats and Review pages.
- **Data:**
  - `fetch.py` pulls from PSN (unofficial PSNAWP library), RAWG, Wikidata/Wikipedia and HowLongToBeat into `docs/data.json`.
  - `recommend.py` makes the weekly picks.
  - `discover.py` builds Coming soon.
  - `difficulty.py` reads trophy guides.
  - `notify.py` sends the Monday push.
  - `flag.py` saves what you change on the dashboard.
- **Runs on GitHub Actions:** refresh on demand, the weekly job every Monday. Nothing runs on your PC.

---

## One-time setup (about 15 minutes, easiest on a computer)

### 1. Create your copy
1. Sign in at github.com. Create a free account if you don't have one.
2. Open the Game Shelf repository you were given and click **Use this template → Create a new repository**.
3. Give it a name, for example `game-shelf`, and set it to **Public**, because free GitHub Pages needs a public repo. Then click **Create repository**.

Your copy starts with the previous owner's data. **Your first refresh replaces it with yours automatically**: when the project signs in to a different PSN account, it clears their library, trophies, ratings, flags, goals, wishlist, Up next and weekly picks. It keeps the shared game information (RAWG, HowLongToBeat, Wikipedia, trophy guides), so your first refresh is faster.

### 2. Get your two keys
- **NPSSO token (PSN login):**
  1. Sign in at https://www.playstation.com.
  2. In the same browser, open https://ca.account.sony.com/api/v1/ssocookie.
  3. Copy the 64-character value of `npsso`.
  4. Treat it like a password: never paste it into a file or share it.
- **RAWG API key (for Metacritic scores):** create a free account at https://rawg.io/apidocs and copy your API key.

### 3. Store the keys as secrets
In the repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Name | Value |
|---|---|
| `PSN_NPSSO` | your NPSSO token |
| `RAWG_API_KEY` | your RAWG key |
| `NTFY_TOPIC` | optional: your ntfy topic for the Monday push (see "Every Monday" below) |

Secrets are encrypted. Nobody who views the repo or the dashboard can see them.

### 4. Turn on the website
Go to **Settings → Pages**. Under *Build and deployment*, choose **Deploy from a branch**, then select branch **main** and folder **/docs**. Click **Save**.

After a minute your dashboard is live at `https://<your-username>.github.io/game-shelf/`.

### 5. Load your data for the first time
If the **Actions** tab asks you to enable workflows, enable them. Then go to **Actions → Refresh game data → Run workflow**. The run takes about 3–8 minutes: PSN requests are deliberately slowed to avoid getting blocked, and the first run looks up every game on RAWG. When it finishes, reload the dashboard.

**On your phone:** open the dashboard in Safari or Chrome, then choose **Share → Add to Home Screen**. It then opens like an app, with its own icon, a tab bar at the bottom, and your last data still available offline (a yellow note says when you're offline). Tap the tab you're on to jump back to the top. Light or dark follows your phone.

---

## Everyday use

### Saving changes
Ratings, Beaten / Dropped flags, Up next, wishlist, 👍 / 👎 on picks, goals and "Wrong info?" fixes all work the same way. Each one goes into a bar at the bottom of the page ("3 changes pending"). Tap **Send all**: one pre-filled GitHub page opens with everything, tap **Create** once, and the dashboard updates in about a minute.
- Changing the same thing twice (rating a game 85, then 88) keeps only the latest.
- The list stays in this browser until you send it. If you closed GitHub without tapping Create, tap **Restore**.
- Only issues you open yourself are processed, so nobody else can change your data.

### Refreshing data
Tap **Refresh data** at the top of the Library. It opens the workflow on GitHub: tap **Run workflow** and wait a few minutes. The weekly job (below) also refreshes everything every Monday.

### Library
- **Each row:** status, hours played, "Beat ~N h" (HowLongToBeat Main + Extras), the platinum estimate from trophy guides (🏆 3/10 · 120 h, green/amber/red), trophy progress, your rating (outlined badge) and the Metacritic score (filled badge).
- **Filters:** Backlog, In progress, Beaten, Completed, Dropped, **🏆 Easy platinum** (rated 3.5/10 or less, not finished) and **To rate** (finished games without your rating). Sort by recent activity, Metacritic, hours, progress, trophies left, time to beat, **easiest** or **shortest platinum**, or name.
- **Game panel** (tap a game):
  - trophies by grade;
  - the platinum line ("Platinum 3/10 · ~110 h · 2 playthroughs · 11 missable", with links to the guides);
  - HowLongToBeat times and a **finish forecast** for games in progress ("at your recent pace, ~7 h/week, you'd finish around 28 Nov");
  - facts and links;
  - the **You** box: your rating (0–100 slider), **+ Up next**, **Beaten**, **Dropped** (tap again to undo);
  - **Wrong info?**;
  - the full **Trophy list** (folded): filter missing/earned, sort by rarity or date, DLC split out, guide links.
- **Beaten / Dropped rules:** earning the platinum or 100% later turns a Beaten game into Completed; a Dropped game you play again goes back to its normal status.
- **Select** (next to the sort menu) flags several games at once.

### Play next
- **Now:**
  - **Up next:** up to 5 games in your order, with time left and the finish forecast. A game leaves the list by itself at the first refresh after you start it (games you add while already playing them stay).
  - **On this day:** a platinum, a rare trophy or a game you started on this date in past years (or later this week).
  - **What to play:** **Best games** (by Metacritic, filters by length and genre, **Surprise me**) or **My ranking** (from the tournament).
  - **Backlog tournament:** 10 random backlog games, two at a time; the one you'd rather play stays on and faces the next, until one is left. The winner joins **My ranking** (one pending change per tournament).
  - **PS Plus** (shown when there's something to say): games you only have through PS Plus that leave the catalogue within 45 days (play or buy them before), and wishlist games that are included with PS Plus (no need to buy). The Library's game panel also says "Through PS Plus · leaves …".
  - **Backlog tidy-up** (suggested every 3 months): up to 15 backlog games you'll probably never play (owned for years, not your usual genres, low Metacritic, a series you've moved on from, very long), one at a time with the reasons. **Keep** (not suggested again for a year) or **Drop** (marked Dropped, out of the backlog, picks and tournament; undo it in the Library). The whole tidy-up is one pending change. In the Library, the **🧹 Tidy-up** filter lists every game you went through, marked "Dropped in tidy-up" or "Kept in tidy-up".
  - **📅 Add to calendar** (next to Up next): subscribe once to `gameshelf.ics`. Your phone's calendar then shows finish forecasts for games in progress, release dates of wishlist and coming-soon games, and a reminder one month before your goals deadline. It updates by itself (after refreshes, Monday runs and saves).
- **Discover:**
  - **This week's picks:** 3 games you don't own, matched to your taste and usual length, with 👍 / 👎 and + Wishlist.
  - **Wishlist** (dashboard only, not your PSN wishlist): search any game by name and tap **+** to add it (the save fills in cover, release date, genres and Metacritic from RAWG). Not found, or not announced yet? Add it by name: it's looked up again every Monday and filled in once RAWG knows it (the Monday push tells you); sort it (also **Cheapest first**), filter Out now / Not out yet, ✕ to remove.
    - **Prices:** each Monday the Swiss PS Store price (CHF) of every wishlist game is checked: discount and end date, "PS Plus" when it's included with your subscription, and the lowest price seen. Tap a game and **Set alert** at a price: the Monday push (and your calendar, on the sale's last day) tells you when it's at or below it. Prices come from public store pages; nothing is bought.
  - **Coming soon:** unreleased PS4/PS5 games by category: Your series, Your studios, Your taste, Big releases, Indie (often empty: RAWG rarely lists consoles for unreleased indies), plus Out soon (next 60 days). Tap **+** to wishlist one.
- **Trophy hunting:**
  - **Closest to platinum:** with the easiest trophies left.
  - **Next platinum: how hard?** Guide rating where there is one, otherwise an estimate from PSN rarity.
  - **DLC to finish.**
- Tap any game for its panel. Games you don't own show a description, studios and release date instead.

### Stats
Pick a year or all time, then a tab:
- **Overview:** totals, top games, trophies by year.
  - **Your history, visualized** (`visuals.html`, `tunnel.html`):
    - **Time tunnel:** scroll to fly through your years. Each year is a chamber of the covers you played (bigger = more hours, a halo for that year's platinums) with its story: "2015 · The year of Assassin's Creed Unity", hours, games, trophies. Covers go through the weserv.nl image proxy, because PlayStation's image server doesn't allow 3D textures from other sites.
    - **Your ocean:** a living 3D sea where every game you've played is a fish. Size = hours played, colour and body shape = genre, and depth = how long since you last played it (what you're playing swims in the light, forgotten games sink). Platinums glow, dropped games turn grey, same-genre fish school together, and the backlog lies on the seabed as eggs. Replay it to watch 15 years hatch and grow; tap a fish to follow it, tap an egg to see what it is, tap open water to feed them.
    - **Your planet** (`viz-planet.js`): a small living world grown by your games. Each kind of game grows its own land, sized by your hours there (fantasy = Dragon woods, sci-fi = Neon frontier, horror = Haunted marsh, shooters and post-apocalypse = The wasteland, historical and stealth = Old world, sports and racing = The arena, cute and platformers = Wonderland, story and mystery = Story coast), with its own trees, towers, crystals or ruins. Every played game is a creature of its land (dragons, drones, ghosts, scrap beetles, eagles, hares, hoppers, stags): bigger = more hours, a golden halo for a platinum, turned to stone if dropped. Day and night pass (walkers sleep in the dark, ghosts come out, lanterns light up) and the moon is the backlog. Lands are picked from each game's RAWG tags (`realmOf`), so a game can land somewhere surprising; the creatures are generic archetypes, not characters from the games. The planet itself is rendered per pixel: procedural terrain with relief, rock and snow, natural ragged borders between lands, a sea with depth, surf and sun glint, polar ice, a drifting cloud layer that casts shadows, a thin atmosphere that reddens at dusk, town lights on the night side where your lands are alive, a cratered moon and a starry band. It lowers its own resolution on a slow device. Replay to watch the bare rock come alive; tap a creature to follow it, tap a land or the moon to read it.
    - **Pixel quest** (`viz-quest.js`): your history as a side-scrolling pixel-art adventure. A little wanderer walks from your first game to today; every game is a monument on the road (signpost, banner, stone or tower, by hours), its trophies are coins, a platinum puts a golden cup on top, a dropped game is a grey ruin. Each year starts at a gate and takes the scenery of the land you played most that year (the planet's eight lands); one year on the road is one day in the sky. ▶ plays and pauses, 1×/2×/4× sets the pace (about 2½ minutes at 1×), tap a monument to read it, tap elsewhere to jump. All sprites are drawn in code; no game art is used.
    - **Gamer fingerprint:** a generative print of your whole history. Time runs along a spiral like a record's groove (one turn per year, the angle is the day of the year); each game is a thread (colour = genre, width = how intensely you played), each trophy a dot, each platinum a star. **Night** or **Paper** style, and **Save poster** makes a 2480×3508 PNG (A4 at 300 dpi, prints well up to A2).
    - **Hours race:** your top 10 games by total hours, year after year.
    Uses three.js (jsDelivr); the fingerprint reads `galaxy.json` (built by `extras.py`).
    - **Last week** (top of Overview, whatever year is selected): trophies, platinums, hours played, new games, goal progress.
- **Trophies:** rarest trophies, a daily calendar, milestones, level history, rarity profile.
- **Habits:** when you play, **your play sessions** (rebuilt from trophy times: typical length, when they start, longest session, biggest weekend, marathon and short-burst games), your pace against HowLongToBeat, finish rate, new releases versus catching up.
- **Taste:** hall of fame, you against the critics, rating patterns, taste map, hours against Metacritic.
- **Collection:** where your hours went, genres, backlog (with its trend over time), series, studios.

Explanations are folded behind **How this works**.

### Review
**Your Wrapped** (top of the page): the year as a full-screen story, card by card (time played, game of the year, top 5, trophies and platinums, rarest trophy, your rhythm, genres, how you play, Gamer DNA, games finished, goals), ending with a 1080×1920 image to share. Tap the right side to go on, the left to go back. It's announced in the Monday push and your calendar in mid-December, and works for past years too.

A yearly summary: the headline numbers, your game of the year, highlights and that year's platinums. **Share as image** makes a 1080×1350 card for your phone's share sheet. **Your gamer DNA** scores nine traits (Story seeker, Explorer, Completionist, Trophy hunter, Night owl, Marathoner, Day-one player, Sampler, Indie spirit) for the year, compared with all time, with your top trait year by year and **Share my DNA**. **Goals** (platinums, games finished, trophies, hours) show progress against an even pace.

### Every Monday (Weekly recommendations workflow)
Around 06:00 Swiss time it:
1. refreshes your data;
2. takes the weekly playtime snapshot (for "Last week" and the forecasts);
3. picks 3 new games;
4. updates Coming soon;
5. looks up platinum difficulty for new games (PowerPyx and TrueTrophies; games without a guide are retried after 30 days);
6. checks the PS Plus catalogue and the Swiss PS Store prices of your wishlist (`store.py`);
7. rebuilds sessions, "On this day" and the calendar feed (`extras.py`, also after every refresh and save);
8. sends the **Monday push**.

To run one part by hand: **Actions → Weekly recommendations → Run workflow** and choose *What to run*:
- `full`: everything (it also replaces this week's picks);
- `coming-soon`;
- `difficulty` (with *minutes*; *retry* / *reparse* `powerpyx` re-check games not found / re-read saved guides);
- `store` (PS Plus and wishlist prices);
- `push-test`.

**Monday push to your phone:** install the free **ntfy** app, subscribe to a topic with a long random name, and add that name as the repo secret `NTFY_TOPIC`. Anyone who knows the name can read the messages. It sends last week's recap, the new picks, games out in the next 30 days, PS Plus games leaving soon and wishlist games newly in PS Plus, price alerts reached, when the backlog tidy-up is due, your Wrapped in mid-December, a memory from this week in past years, and a warning two weeks before the PSN login expires.

### Fixing wrong info
Open the game's panel and tap **Wrong info?**. You can correct:
- the **trophy guide** (paste the PowerPyx address): read straight away;
- the **HowLongToBeat match**;
- the **game match** (a rawg.io address: genres, Metacritic, release date);
- the **Metacritic score**;
- the **name shown**.

Type `none` when there is no match, or tap **Back to automatic** to undo. Fixes are saved in `overrides.json` and apply at the next data refresh.

## Going back to an earlier look

The version before the November 2026 UX review is kept as a working copy at `/v1/` (for example `https://<you>.github.io/gameshelf/v1/`), with an orange "Backup" banner. To restore it for good, ask for the files in `docs/v1/` to be copied back over `docs/`, or revert the commit "UX review" in GitHub's history.

## Renewing the PSN login (about every two months)
The NPSSO token can't be renewed automatically: getting a new one requires signing in to Sony, which is protected by captchas and two-step verification. To keep this painless, the dashboard:
- Shows **"PSN login expires in about N days"** next to the update time. The count turns amber in the last two weeks. The date is an estimate: two months from when a new token was first used, because Sony doesn't reveal the real expiry date.
- Shows a red **"PSN login expired"** banner with the renewal steps if a refresh couldn't sign in. Your last good data stays visible.

To renew: sign in at playstation.com, open https://ca.account.sony.com/api/v1/ssocookie, copy the `npsso` value, and paste it into the `PSN_NPSSO` secret. If you're on a phone, use the browser in desktop mode, because the GitHub app can't edit secrets. Then refresh.

The token itself is never written to the dashboard or the repo. Only a short one-way fingerprint is stored, so the dashboard can tell when you've swapped in a new token.

## When something goes wrong
- **"PSN login expired" banner:** follow the renewal steps above.
- **"Last refresh failed" banner:** Sony's servers returned an error. Try again later. If it keeps happening, see the next point.
- **Wrong HowLongToBeat time, Metacritic score, genres, trophy guide or name:** use **Wrong info?** in the game's panel (see above).
- **The workflow fails with 403 or connection errors from Sony.** Sony sometimes blocks cloud servers. Fallback: run it once from any computer with Python installed.
  ```bash
  pip install -r requirements.txt
  PSN_NPSSO=yourtoken RAWG_API_KEY=yourkey python fetch.py
  ```
  Then upload the new `docs/data.json` and `rawg_cache.json` to the repo.

## What the data covers, and its limits
- **Game names:** your store list comes from the Swiss PlayStation Store, which translates some titles into French. When a store name looks translated, the dashboard shows the name from your playtime or trophy list instead, or the one in the `"names"` list in `overrides.json`. Add a line there if a translated name ever shows up. Flags follow a game when its name changes.
- **Playtime:** PS4 and PS5 games only. Sony doesn't track playtime for PS3 or Vita.
- **Owned games:** PS4 and PS5 **digital** purchases, including claimed PS Plus games. Disc-only games show up only after you've earned a trophy or played them.
- **Trophies:** every game with a trophy list, including PS3 and Vita.
- **Merging versions:** PS4 and PS5 versions of the same game are shown as one row, with their playtime added together. Occasionally a remaster or a game with a regional title shows up as a separate row.
- **Metacritic:** scores come from RAWG first. RAWG stopped updating its Metacritic data, so newer games are filled from Wikidata (exact match on the RAWG ID), then from the Metacritic line in the game's Wikipedia review box. Editors keep those current. The PS5 score is preferred, then PS4. Games without a score on Wikipedia are checked again every 30 days. Hover or long-press a score to see its source. Some indie games still have none; you can type in a score yourself under `"metacritic"` in `overrides.json`.
- **HowLongToBeat:** there is no official API. The script uses an unofficial library that reads the website, so it can break when HowLongToBeat changes its site. If it fails, the refresh still completes and times just stay empty. Updating `howlongtobeatpy` in `requirements.txt` usually fixes it.
- **Yearly trophies:** exact, from the date each trophy was earned. The first refresh that loads trophy dates takes up to about 40 minutes (two requests per game, deliberately slowed). If it runs out of time, the next refresh picks up where it stopped. After that, only games with new trophies are re-read.
- **Yearly hours are estimates.** PSN only reports each game's total playtime. The script spreads it across the years between first and last played, weighted by when you earned trophies.
- **Public page:** `data.json` is public, like your PSN trophy profile. It contains no login details.
- **Unofficial API:** PSNAWP uses Sony's unofficial app API, which can change without notice. If it breaks, updating the version pinned in `requirements.txt` usually fixes it.
