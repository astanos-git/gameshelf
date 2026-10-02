/* Pending changes: collect every save (ratings, flags, Up next, wishlist, 👍/👎, goals) and send them to
   GitHub in one go. Any "issues/new" link on the page is caught here and added to the basket instead of
   opening GitHub. The basket lives in this browser until you send it. */
(() => {
  const KEY = "shelf-pending", SENT = "shelf-pending-sent", MAX_URL = 6000;
  const read = k => { try { return JSON.parse(localStorage.getItem(k) || "[]"); } catch { return []; } };
  const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let repo = null, open = false;

  // The command lines of a change (drop the "Tap Create…" sentence)
  const commands = body => body.split("\n").filter(l => /^\s*[a-z]+:\s*\S/i.test(l)).join("\n");
  // Changes to the same thing replace each other (e.g. rating the same game twice)
  const keyOf = cmd => {
    const lines = cmd.split("\n"), kind = lines[0].split(":")[0].trim().toLowerCase();
    const target = lines.filter(l => /^(game|slug|goal):/i.test(l)).join("|");
    return kind === "flag" || kind === "queue" && !/^queue:\s*set/i.test(lines[0]) ? `${kind}|${lines[0]}|${target}` : `${kind}|${target}`;
  };

  function add(title, body) {
    const cmd = commands(body); if (!cmd) return;
    const items = read(KEY), key = keyOf(cmd);
    // a flag or rating for a game replaces the earlier one for that game; "remove flag" also cancels a pending flag
    const kind = key.split("|")[0];
    const rest = items.filter(i => i.key !== key && !(kind === "flag" && i.key.startsWith("flag|") && i.key.split("|").slice(2).join("|") === key.split("|").slice(2).join("|")));
    rest.push({ key, title, cmd, at: Date.now() });
    write(KEY, rest);
    render(`Added: ${title}`);
  }

  function parts(items) {
    const out = []; let cur = [];
    const url = list => `${repo}/issues/new?title=${encodeURIComponent(`Batch: ${list.length} change${list.length === 1 ? "" : "s"}`)}&body=${encodeURIComponent(
      `Tap "Create" (or "Submit new issue") to save all of these. The dashboard updates in about a minute.\n\n` + list.map(i => i.cmd).join("\n---\n") + "\n")}`;
    for (const i of items) { if (cur.length && url([...cur, i]).length > MAX_URL) { out.push(cur); cur = []; } cur.push(i); }
    if (cur.length) out.push(cur);
    return out.map(list => ({ list, href: url(list) }));
  }

  function render(toast) {
    let bar = document.getElementById("pendingBar");
    if (!bar) { bar = document.createElement("div"); bar.id = "pendingBar"; document.body.appendChild(bar); }
    const items = read(KEY), sent = read(SENT);
    if (!items.length && !sent.length) { bar.hidden = true; document.body.classList.remove("has-pending"); return; }
    bar.hidden = false; document.body.classList.add("has-pending");
    const ps = items.length ? parts(items) : [];
    bar.innerHTML = `<div class="pb-in">
      ${toast ? `<div class="pb-toast" role="status">${esc(toast)}</div>` : ""}
      ${items.length ? `<div class="pb-row"><button class="pb-toggle" aria-expanded="${open}"><b>${items.length}</b> change${items.length === 1 ? "" : "s"} pending ${open ? "▾" : "▸"}</button>
        <span class="pb-send">${ps.length === 1 ? `<a class="pb-go" data-part="0" href="${ps[0].href}" target="_blank" rel="noopener">Send all</a>`
          : ps.map((p, n) => `<a class="pb-go" data-part="${n}" href="${p.href}" target="_blank" rel="noopener">Send part ${n + 1}</a>`).join("")}</span></div>
        ${open ? `<ul class="pb-list">${items.map((i, n) => `<li><span>${esc(i.title)}</span><button data-drop="${n}" aria-label="Remove">✕</button></li>`).join("")}
          <li class="pb-clear"><button data-clear>Discard all</button></li></ul>` : ""}
        ${ps.length > 1 ? `<p class="pb-note">Too many changes for one GitHub page: send each part and tap Create on each.</p>` : ""}`
      : `<div class="pb-row"><span>Sent ${sent.length} change${sent.length === 1 ? "" : "s"} to GitHub. Didn't tap Create?</span><span class="pb-send"><button data-restore>Restore</button><button data-done>Done</button></span></div>`}
    </div>`;
  }

  document.addEventListener("click", e => {
    const a = e.target.closest("a[href*='/issues/new?']");
    if (a && !a.closest("#pendingBar")) {               // any save link on the page -> basket
      e.preventDefault();                               // page handlers still run (e.g. leaving select mode)
      const u = new URL(a.href);
      if (!repo) repo = u.origin + u.pathname.replace(/\/issues\/new$/, "");
      add(u.searchParams.get("title") || "Change", u.searchParams.get("body") || "");
      a.dispatchEvent(new CustomEvent("pending-added", { bubbles: true }));
      return;
    }
    const bar = e.target.closest("#pendingBar"); if (!bar) return;
    if (e.target.closest(".pb-toggle")) { open = !open; return render(); }
    const drop = e.target.closest("[data-drop]");
    if (drop) { const items = read(KEY); items.splice(+drop.dataset.drop, 1); write(KEY, items); return render(); }
    if (e.target.closest("[data-clear]")) { write(KEY, []); open = false; return render(); }
    const go = e.target.closest(".pb-go");
    if (go) {                                            // the link opens GitHub; keep a copy in case Create isn't tapped
      const items = read(KEY), sentNow = parts(items)[+go.dataset.part].list;
      write(SENT, [...read(SENT), ...sentNow]); write(KEY, items.filter(i => !sentNow.some(s => s.key === i.key)));
      setTimeout(() => render(), 300); return;
    }
    if (e.target.closest("[data-restore]")) { write(KEY, [...read(SENT), ...read(KEY)]); write(SENT, []); return render(); }
    if (e.target.closest("[data-done]")) { write(SENT, []); return render(); }
  }, true);

  // Work out the repo link even before the first click (GitHub Pages address: owner.github.io/repo)
  const h = location.hostname;
  if (h.endsWith(".github.io")) { const owner = h.split(".")[0]; repo = `https://github.com/${owner}/${location.pathname.split("/").filter(Boolean)[0] || owner + ".github.io"}`; }

  const css = document.createElement("style");
  css.textContent = `#pendingBar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 20; background: var(--fg); color: var(--bg);
      padding: 10px 16px calc(10px + env(safe-area-inset-bottom, 0px)); box-shadow: 0 -6px 20px rgba(0,0,0,.18); font-size: 14px; }
    #pendingBar[hidden] { display: none; }
    body.has-pending .wrap { padding-bottom: 120px; }
    body.has-pending.selecting #pendingBar { display: none; }
    .pb-in { max-width: 880px; margin: 0 auto; display: grid; gap: 8px; }
    .pb-row { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
    .pb-toggle { background: none; border: 0; color: inherit; font: inherit; cursor: pointer; padding: 0; }
    .pb-send { display: flex; gap: 8px; flex-wrap: wrap; }
    .pb-go, #pendingBar .pb-send button { background: var(--accent); color: #fff; border: 0; border-radius: 8px; padding: 7px 14px; font: 600 14px var(--body, system-ui); text-decoration: none; cursor: pointer; }
    #pendingBar [data-done] { background: transparent; border: 1px solid currentColor; color: inherit; }
    .pb-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; max-height: 40vh; overflow-y: auto; }
    .pb-list li { display: flex; justify-content: space-between; gap: 10px; align-items: center; border-top: 1px solid color-mix(in srgb, var(--bg) 25%, transparent); padding-top: 4px; }
    .pb-list li span { min-width: 0; overflow-wrap: anywhere; }
    .pb-list button { background: none; border: 0; color: inherit; cursor: pointer; font-size: 15px; padding: 2px 6px; }
    .pb-clear { justify-content: flex-end !important; } .pb-clear button { text-decoration: underline; font-size: 13px; }
    .pb-toast { font-size: 13px; opacity: .85; }
    .pb-note { margin: 0; font-size: 12.5px; opacity: .85; }`;
  document.head.appendChild(css);
  document.addEventListener("DOMContentLoaded", () => render());
  if (document.readyState !== "loading") render();
  window.addEventListener("storage", () => render());   // stays in sync across open tabs
})();
