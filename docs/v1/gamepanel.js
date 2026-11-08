/* Game Shelf: the game panel shared by Library and Play next.
   GP.panel(game, { id, extra }) returns the panel HTML: trophies by grade, HowLongToBeat, facts,
   and the "You" box (rating, Up next, Beaten / Dropped). Library adds its trophy list through `extra`.
   Set GP.ratings and GP.queue once the page has loaded ratings.json and queue.json. */
const GP = (() => {
  const TIERS = ["platinum", "gold", "silver", "bronze"];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = s => s ? new Date(s).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—";
  const fmtH = h => h >= 10 ? Math.round(h) + " h" : (Math.round(h * 2) / 2) + " h";
  const mcClass = m => m == null ? "none" : m >= 75 ? "good" : m >= 50 ? "mid" : "bad";
  const api = { ratings: {}, queue: [], difficulty: {} };
  const SRC = { powerpyx: "PowerPyx", truetrophies: "TrueTrophies" };
  // Platinum difficulty from trophy guides (difficulty.json, weekly): "Platinum 3/10 · ~120 h · 10 missable · 2 playthroughs"
  /* Your pace on a game: hours per week over the last ~4 weeks, from the Monday snapshots (plus hours since the
     last one). Finish forecast = time left (HowLongToBeat Main + Extras minus your hours) at that pace. */
  api.snaps = [];
  api.pace = x => {
    const S = api.snaps; if (!S.length) return null;
    const names = [x.name, ...(x.aliases || [])], hoursIn = s => { const k = names.find(n => s.hours[n] != null); return k ? s.hours[k] : 0; };
    const now = Date.now(), old = [...S].reverse().find(s => now - Date.parse(s.date) >= 21 * 864e5) || S[0];
    const days = (now - Date.parse(old.date)) / 864e5;
    if (days < 6) return null;                                   // not enough history yet
    return Math.max(0, ((x.hours || 0) - hoursIn(old)) / (days / 7));
  };
  api.forecast = x => {
    if (x.base_status === "completed" || ["beaten", "dropped"].includes(x.flag?.flag) || !(x.hours > 0)) return null;
    const beat = x.hltb?.extra || x.hltb?.main; if (!beat) return null;
    const left = beat - x.hours, rate = api.pace(x);
    if (rate == null) return null;
    if (left <= 0) return { text: "Past the usual length (HowLongToBeat Main + Extras)", short: "past usual length" };
    if (rate < 0.5) return { text: "Not played in the last few weeks, so no finish date", short: "" };
    const d = new Date(Date.now() + (left / rate) * 7 * 864e5);
    const when = d.toLocaleDateString(undefined, { day: "numeric", month: "short", ...(d.getFullYear() !== new Date().getFullYear() ? { year: "numeric" } : {}) });
    return { text: `At your recent pace (~${fmtH(rate)}/week) you'd finish around ${when}`, short: `done ~${when}`, date: d };
  };
  api.diffOf = x => [x.name, ...(x.aliases || [])].map(n => api.difficulty[n]).find(e => e?.combined && Object.keys(e.combined).length) || null;
  function diffLine(x) {
    const e = api.diffOf(x); if (!e) return "";
    const c = e.combined, bits = [];
    if (c.difficulty != null) bits.push(`<b>Platinum ${c.difficulty}/10</b>`);
    if (c.hours) bits.push(c.difficulty != null ? `~${c.hours} h` : `<b>Platinum ~${c.hours} h</b>`);
    if (c.playthroughs) bits.push(`${c.playthroughs} playthrough${c.playthroughs > 1 ? "s" : ""}`);
    // missables stand out in the details while there is still something to miss
    if (c.missable != null) bits.push(!c.missable ? "no missables" : x.base_status === "completed" ? `${c.missable} missable` : `<span class="warn-miss">⚠️ ${c.missable} missable: read the guide before you start</span>`);
    if (c.online) bits.push(`${c.online} online`);
    if (c.glitched) bits.push(`${c.glitched} glitched`);
    const srcs = Object.entries(e.sources || {}).filter(([, v]) => v).map(([k, v]) => `<a href="${esc(v.url)}" target="_blank" rel="noopener">${SRC[k] || k}${v.difficulty != null ? ` ${v.difficulty}/10` : ""}${v.hours ? ` · ${v.hours_text || v.hours} h` : ""}</a>`);
    return `<div class="pdiff"><span>${bits.join(" · ")}</span><span class="pdiff-src">${srcs.join(" · ")}</span></div>`;
  }

  function repoUrl() {
    const h = location.hostname; if (!h.endsWith(".github.io")) return null;
    const owner = h.split(".")[0], repo = location.pathname.split("/").filter(Boolean)[0] || `${owner}.github.io`;
    return `https://github.com/${owner}/${repo}`;
  }
  const issue = (title, lines) => `${repoUrl()}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(
    `Tap "Create" (or "Submit new issue") to save this. The dashboard updates in about a minute.\n\n${lines.join("\n")}\n`)}`;
  const flagUrl = (flag, name) => issue(flag === "none" ? `Flag ${name}: remove flag` : `Flag ${name} as ${flag}`, [`flag: ${flag}`, `game: ${name}`]);
  const rateUrl = (name, v) => issue(v === "none" ? `Rate ${name}: remove rating` : `Rate ${name}: ${v}/100`, [`rating: ${v}`, `game: ${name}`]);
  const ratingOf = x => api.ratings[x.name] || (x.aliases || []).map(n => api.ratings[n]).find(Boolean);

  function ratingBar(x) {
    const r = ratingOf(x), repo = repoUrl();
    const start = r ? r.score : (x.metacritic ?? 70);   // start from your score, or the critics' as a reference point
    const hint = r ? (x.metacritic != null ? `Metacritic ${x.metacritic}` : "") : x.metacritic != null ? `Starts at the Metacritic score (${x.metacritic})` : "Not rated yet";
    return `<div class="rating" data-name="${esc(x.name)}" data-saved="${r ? r.score : ""}">
      <div class="rater"><span class="val ${mcClass(start)}" aria-live="polite">${start}</span>
        <input type="range" min="0" max="100" step="1" value="${start}" aria-label="Your rating, 0 to 100">
        <button class="step" data-step="-1" aria-label="One point lower">−</button><button class="step" data-step="1" aria-label="One point higher">+</button>
        ${repo ? `<a class="save${r ? " same" : ""}" target="_blank" rel="noopener" href="${rateUrl(x.name, start)}">${r ? "Saved" : "Save"}</a>` : ""}</div>
      <div class="rater-actions"><span>${hint}${repo ? "" : " · saving works on your GitHub Pages dashboard"}</span>
        ${r && repo ? `<a href="${rateUrl(x.name, "none")}" target="_blank" rel="noopener">Remove rating</a>` : ""}</div></div>`;
  }

  function syncRater(box, v) {
    v = Math.max(0, Math.min(100, v));
    box.querySelector("input").value = v;
    const val = box.querySelector(".val"); val.textContent = v; val.className = "val " + mcClass(v);
    const save = box.querySelector("a.save");
    if (save) {
      const same = String(v) === box.dataset.saved;
      save.classList.toggle("same", same); save.classList.remove("added");
      save.textContent = same ? "Saved" : "Save";
      save.href = rateUrl(box.dataset.name, v);
    }
  }

  function actionsBar(x) {
    const repo = repoUrl(), Q = api.queue;
    if (x.base_status === "completed") return `<p class="flagnote">Completed: the platinum or 100% trophies say you finished it.</p>`;
    if (!repo) return `<p class="flagnote">Up next and Beaten / Dropped work on your GitHub Pages dashboard.</p>`;
    const link = (href, label, cls, title) => `<a class="flagbtn ${cls}" target="_blank" rel="noopener" href="${href}"${title ? ` title="${title}"` : ""}>${label}</a>`;
    const names = [x.name, ...(x.aliases || [])], inQ = names.some(n => Q.includes(n));
    const pos = Math.max(...names.map(n => Q.indexOf(n))) + 1;
    const q = inQ ? link(issue(`Up next: remove ${x.name}`, ["queue: remove", `game: ${x.name}`]), `✓ Up next #${pos}`, "queue on", "Tap to remove from Up next")
      : Q.length >= 5 ? `<span class="flagbtn" title="Up next holds 5 games. Remove one on Play next.">Up next is full</span>`
      : link(issue(`Up next: add ${x.name}`, ["queue: add", `game: ${x.name}`]), "+ Up next", "queue");
    const fl = x.flag?.flag;
    const b = fl === "beaten" ? link(flagUrl("none", x.name), "✓ Beaten", "beaten on", "Tap to remove the flag") : link(flagUrl("beaten", x.name), "Beaten", "beaten", "Finished without the platinum");
    const d = fl === "dropped" ? link(flagUrl("none", x.name), "✓ Dropped", "dropped on", "Tap to remove the flag") : link(flagUrl("dropped", x.name), "Dropped", "dropped", "Stopped playing");
    const note = fl === "beaten" ? `Beaten since ${fmtDate(x.flag.at)}. Earning the platinum later switches it to Completed.`
      : fl === "dropped" ? `Dropped since ${fmtDate(x.flag.at)}. Playing it again clears this at the next refresh.` : "";
    return `<div class="flagbar">${q}${b}${d}</div>${note ? `<p class="flagnote">${note}</p>` : ""}`;
  }

  api.panel = (x, { id = "", extra = "" } = {}) => {
    const pend = x.defined
      ? `<div class="pending">${TIERS.map(t => `<span class="tier"><span class="dot d-${t}"></span>${x.earned[t]}/${x.defined[t]}</span>`).join("")}<span class="tleft">${x.trophies_total - x.trophies_earned} left</span></div>`
      : `<div class="pending"><span class="tleft">No trophies yet</span></div>`;
    const facts = [
      ["Genres", (x.genres || []).join(", ") || "—"],
      ["Released", fmtDate(x.released)],
      ["Owned", x.owned ? (x.acquired ? "Since " + fmtDate(x.acquired) : "Yes") : "Not in digital library"],
      ["First played", fmtDate(x.first_played)],
      ["Last played", fmtDate(x.last_played)],
      ["Last trophy", fmtDate(x.last_trophy)],
    ];
    const fc = api.forecast(x), fcLine = fc ? `<div class="forecast">⏱ ${esc(fc.text)}</div>` : "";
    const H = x.hltb, hl = H ? `<div class="hltb"><span>HowLongToBeat</span>${[["Main story", H.main], ["Main + extras", H.extra], ["Completionist", H.complete]].filter(([, v]) => v).map(([k, v]) => `<span>${k} <b>${fmtH(v)}</b></span>`).join("")}${H.url ? `<a href="${esc(H.url)}" target="_blank" rel="noopener">Open</a>` : ""}</div>` : "";
    const link = x.rawg_slug ? `<a href="https://rawg.io/games/${esc(x.rawg_slug)}" target="_blank" rel="noopener">Game page on RAWG</a>` : "";
    return `<div class="detail"${id ? ` id="${id}"` : ""}>${pend}${diffLine(x)}${hl}${fcLine}<dl class="facts">${facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>${link}
      <div class="you"><div class="you-h">You</div>${ratingBar(x)}${actionsBar(x)}</div>${fixForm(x)}${extra}</div>`;
  };

  /* "Wrong info?": correct a match or a name. Saved like everything else (pending changes → one GitHub issue),
     written to overrides.json; the trophy guide is re-read straight away, the rest at the next data refresh. */
  const FIX = {
    guide: ["Trophy guide (difficulty)", "Paste the PowerPyx guide address, or type none if there is no guide.", "https://www.powerpyx.com/…-trophy-guide-roadmap/", "url"],
    hltb: ["HowLongToBeat match", "The game's title as written on howlongtobeat.com, or none.", "Title on HowLongToBeat", "text"],
    rawg: ["Game match (genres, Metacritic, release)", "Paste the game's rawg.io address, or type none.", "https://rawg.io/games/…", "url"],
    metacritic: ["Metacritic score", "The score from metacritic.com (0–100).", "e.g. 87", "number"],
    name: ["Name shown", "The name to show on the dashboard.", "Name", "text"],
  };
  function fixForm(x) {
    if (!repoUrl()) return "";
    return `<details class="fixit" data-name="${esc(x.name)}"><summary>Wrong info?</summary>
      <div class="fx"><select class="fx-what" aria-label="What's wrong">${Object.entries(FIX).map(([k, [l]]) => `<option value="${k}">${l}</option>`).join("")}</select>
        <p class="fx-hint note">${FIX.guide[1]}</p>
        <input class="fx-val" type="url" placeholder="${FIX.guide[2]}" aria-label="Correct value">
        <span class="fx-act"><a class="fx-save off" target="_blank" rel="noopener" href="#">Save fix</a><a class="fx-reset" target="_blank" rel="noopener" href="${fixUrl(x.name, "guide", "auto")}">Back to automatic</a></span></div></details>`;
  }
  const fixUrl = (name, what, value) => issue(`Fix ${name}: ${FIX[what][0].toLowerCase()}`, [`fix: ${what}`, `game: ${name}`, `value: ${value}`]);
  function syncFix(box) {
    const what = box.querySelector(".fx-what").value, inp = box.querySelector(".fx-val"), [, hint, ph, type] = FIX[what];
    if (inp.dataset.what !== what) { inp.dataset.what = what; inp.type = type; inp.placeholder = ph; box.querySelector(".fx-hint").textContent = hint; }
    const v = inp.value.trim(), ok = what === "metacritic" ? /^(100|[1-9]?\d)$/.test(v) : !!v;
    const save = box.querySelector(".fx-save"); save.classList.toggle("off", !ok); save.href = ok ? fixUrl(box.dataset.name, what, v) : "#";
    box.querySelector(".fx-reset").href = fixUrl(box.dataset.name, what, "auto");
  }
  document.addEventListener("input", e => { const b = e.target.closest(".fixit"); if (b) syncFix(b); });
  document.addEventListener("change", e => { const b = e.target.closest(".fixit"); if (b) syncFix(b); });
  document.addEventListener("click", e => { if (e.target.matches(".fx-save.off")) e.preventDefault(); }, true);

  // Rating slider and ± buttons, and "✓ Added" once a change goes into the pending list
  document.addEventListener("input", e => { if (e.target.matches(".detail .rater input")) syncRater(e.target.closest(".rating"), +e.target.value); });
  document.addEventListener("click", e => { const st = e.target.closest(".detail .rater .step"); if (st) { const box = st.closest(".rating"); syncRater(box, +box.querySelector("input").value + +st.dataset.step); } });
  document.addEventListener("pending-added", e => { const a = e.target.closest(".detail a.save, .detail a.flagbtn"); if (a) { a.classList.add("added"); a.textContent = "✓ Added"; } });
  return api;
})();
