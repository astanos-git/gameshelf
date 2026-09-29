# Game Shelf

A personal PlayStation dashboard you can open from your phone. It shows your games, playtime, trophies (earned and remaining), and Metacritic scores. The data refreshes only when you ask for it.

- **Dashboard:** `docs/index.html` (your library) and `docs/stats.html` (yearly stats and genres), hosted free on GitHub Pages
- **Data:** `fetch.py` pulls from PSN (via the unofficial PSNAWP library) , RAWG (Metacritic scores and genres) and HowLongToBeat (time to beat), then writes `docs/data.json`
- **Refresh:** a GitHub Action you start with one tap. Nothing runs on your PC.

---

## One-time setup (about 15 minutes, easiest on a computer)

### 1. Create the repository
1. Sign in at github.com. Create a free account if you don't have one.
2. Click **New repository** and name it, for example `game-shelf`. Set it to **Public**, because free GitHub Pages needs a public repo. Then click **Create**.
3. Click **uploading an existing file** and drag in everything from this folder.
   - On a Mac, the `.github` folder is hidden in Finder. If it doesn't upload, go to **Add file → Create new file**, name it `.github/workflows/refresh.yml`, and paste in the contents of that file.
4. Click **Commit changes**.

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

Secrets are encrypted. Nobody who views the repo or the dashboard can see them.

### 4. Turn on the website
Go to **Settings → Pages**. Under *Build and deployment*, choose **Deploy from a branch**, then select branch **main** and folder **/docs**. Click **Save**.

After a minute your dashboard is live at `https://<your-username>.github.io/game-shelf/`.

### 5. Load your data for the first time
Go to **Actions → Refresh game data → Run workflow**. The run takes about 3–8 minutes: PSN requests are deliberately slowed to avoid getting blocked, and the first run looks up every game on RAWG. When it finishes, reload the dashboard.

**On your phone:** open the dashboard in Safari or Chrome, then choose **Share → Add to Home Screen**. It then opens like an app.

---

## Everyday use
- **Refresh:** tap **Refresh data** at the top of the dashboard. It opens the workflow on GitHub; tap **Run workflow** and wait a few minutes. You need to be signed in to GitHub, and the GitHub mobile app works too.
- **Backlog:** the Backlog filter shows owned games you have never started. It sorts by Metacritic score so you can pick the next one to play.
- **Details:** tap a game to see remaining trophies by grade, HowLongToBeat times, genres, and your first and last played dates.
- **Time to beat:** each game shows "Beat in ~N h" (HowLongToBeat main story). Sort by **Time to beat** to find short games in your backlog.
- **Beaten / Dropped:** tap a game, then **Mark as beaten** (finished without the platinum) or **Mark as dropped**. A pre-filled GitHub page opens; tap **Create** and the dashboard updates in about a minute. Flags are saved in `docs/flags.json`, and refreshes never overwrite them. Two automatic rules apply:
  - Earning the platinum or 100% of the trophies later turns a Beaten game into **Completed**.
  - A Dropped game with new playtime or a new trophy after the date you dropped it goes back to its normal status at your next refresh.
  Only issues you open yourself are processed, so nobody else can change your flags.
- **Flag several games at once:** tap **Select** (next to the sort menu), tap the games you want, or use **Select all shown** for the current filter or search, then choose an action in the bar at the bottom. Everything goes into one GitHub page, so it's still just one tap on **Create**. Very large selections (roughly 150+ games) are split into Part 1, Part 2 and so on; open each part and tap Create. Completed games can't be selected.
- **Stats:** the Stats tab shows each year, or all time: trophies, platinums, hours played, your top 3 games by trophies and by hours, trophies by month, and a genre breakdown by hours or number of games.

## Renewing the PSN login (about every two months)
The NPSSO token can't be renewed automatically: getting a new one requires signing in to Sony, which is protected by captchas and two-step verification. To keep this painless, the dashboard:
- Shows **"PSN login expires in about N days"** next to the update time. The count turns amber in the last two weeks. The date is an estimate: two months from when a new token was first used, because Sony doesn't reveal the real expiry date.
- Shows a red **"PSN login expired"** banner with the renewal steps if a refresh couldn't sign in. Your last good data stays visible.

To renew: sign in at playstation.com, open https://ca.account.sony.com/api/v1/ssocookie, copy the `npsso` value, and paste it into the `PSN_NPSSO` secret. If you're on a phone, use the browser in desktop mode, because the GitHub app can't edit secrets. Then refresh.

The token itself is never written to the dashboard or the repo. Only a short one-way fingerprint is stored, so the dashboard can tell when you've swapped in a new token.

## When something goes wrong
- **"PSN login expired" banner:** follow the renewal steps above.
- **"Last refresh failed" banner:** Sony's servers returned an error. Try again later. If it keeps happening, see the next point.
- **Wrong or missing HowLongToBeat time.** In `overrides.json`, under `"hltb"`, map the game name as shown on the dashboard to its title as written on howlongtobeat.com. The fix applies on the next refresh.
- **Wrong or missing Metacritic score.** Find the game on rawg.io and copy the last part of its URL, for example `ghost-of-tsushima`. Add a line to `overrides.json`: `"Game Name As Shown": "ghost-of-tsushima"`. Use `null` instead of a slug to show no score. The fix applies on the next refresh.
- **The workflow fails with 403 or connection errors from Sony.** Sony sometimes blocks cloud servers. Fallback: run it once from any computer with Python installed.
  ```bash
  pip install -r requirements.txt
  PSN_NPSSO=yourtoken RAWG_API_KEY=yourkey python fetch.py
  ```
  Then upload the new `docs/data.json` and `rawg_cache.json` to the repo.

## What the data covers, and its limits
- **Playtime:** PS4 and PS5 games only. Sony doesn't track playtime for PS3 or Vita.
- **Owned games:** PS4 and PS5 **digital** purchases, including claimed PS Plus games. Disc-only games show up only after you've earned a trophy or played them.
- **Trophies:** every game with a trophy list, including PS3 and Vita.
- **Merging versions:** PS4 and PS5 versions of the same game are shown as one row, with their playtime added together. Occasionally a remaster or a game with a regional title shows up as a separate row.
- **Metacritic:** scores come from RAWG's copy of Metacritic data. Very new or niche games may have no score.
- **HowLongToBeat:** there is no official API. The script uses an unofficial library that reads the website, so it can break when HowLongToBeat changes its site. If it fails, the refresh still completes and times just stay empty. Updating `howlongtobeatpy` in `requirements.txt` usually fixes it.
- **Yearly trophies:** exact, from the date each trophy was earned. The first refresh that loads trophy dates takes up to about 40 minutes (two requests per game, deliberately slowed). If it runs out of time, the next refresh picks up where it stopped. After that, only games with new trophies are re-read.
- **Yearly hours are estimates.** PSN only reports each game's total playtime. The script spreads it across the years between first and last played, weighted by when you earned trophies.
- **Public page:** `data.json` is public, like your PSN trophy profile. It contains no login details.
- **Unofficial API:** PSNAWP uses Sony's unofficial app API, which can change without notice. If it breaks, updating the version pinned in `requirements.txt` usually fixes it.
