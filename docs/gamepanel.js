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
  const api = { ratings: {}, queue: [] };

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
    const H = x.hltb, hl = H ? `<div class="hltb"><span>HowLongToBeat</span>${[["Main story", H.main], ["Main + extras", H.extra], ["Completionist", H.complete]].filter(([, v]) => v).map(([k, v]) => `<span>${k} <b>${fmtH(v)}</b></span>`).join("")}${H.url ? `<a href="${esc(H.url)}" target="_blank" rel="noopener">Open</a>` : ""}</div>` : "";
    const link = x.rawg_slug ? `<a href="https://rawg.io/games/${esc(x.rawg_slug)}" target="_blank" rel="noopener">Game page on RAWG</a>` : "";
    return `<div class="detail"${id ? ` id="${id}"` : ""}>${pend}${hl}<dl class="facts">${facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>${link}
      <div class="you"><div class="you-h">You</div>${ratingBar(x)}${actionsBar(x)}</div>${extra}</div>`;
  };

  // Rating slider and ± buttons, and "✓ Added" once a change goes into the pending list
  document.addEventListener("input", e => { if (e.target.matches(".detail .rater input")) syncRater(e.target.closest(".rating"), +e.target.value); });
  document.addEventListener("click", e => { const st = e.target.closest(".detail .rater .step"); if (st) { const box = st.closest(".rating"); syncRater(box, +box.querySelector("input").value + +st.dataset.step); } });
  document.addEventListener("pending-added", e => { const a = e.target.closest(".detail a.save, .detail a.flagbtn"); if (a) { a.classList.add("added"); a.textContent = "✓ Added"; } });
  return api;
})();
