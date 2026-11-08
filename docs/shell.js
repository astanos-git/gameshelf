/* Shared app behaviour for every page: offline support, offline notice, tab bar extras. */
(() => {
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) navigator.serviceWorker.register("sw.js").catch(() => {});

  // say so when the phone is offline: the page then shows the last saved copy of your data
  const note = document.createElement("div");
  note.className = "offline-note"; note.setAttribute("role", "status");
  note.textContent = "Offline: showing your last saved data. Changes can't be sent until you're back online.";
  const sync = () => { note.hidden = navigator.onLine; };
  addEventListener("online", sync); addEventListener("offline", sync);
  document.body.prepend(note); sync();

  // Appearance: Auto (follows the phone), Light or Dark; remembered on this device
  const metas = [...document.querySelectorAll('meta[name="theme-color"]')], tint = { light: "#eef1f6", dark: "#0e1320" };
  const applyTheme = t => {
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
    metas.forEach(m => { m.content = t === "light" || t === "dark" ? tint[t] : (m.media.includes("dark") ? tint.dark : tint.light); });
    try { t === "auto" ? localStorage.removeItem("shelf-theme") : localStorage.setItem("shelf-theme", t); } catch {}
    document.querySelectorAll("[data-theme-set]").forEach(b => b.setAttribute("aria-pressed", b.dataset.themeSet === t));
  };
  let cur = "auto"; try { cur = localStorage.getItem("shelf-theme") || "auto"; } catch {}
  const slot = document.getElementById("themeSlot");
  if (slot) {
    const ic = { auto: '<path d="M12 3a9 9 0 1 0 0 18z" fill="currentColor"/><circle cx="12" cy="12" r="9"/>', light: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>', dark: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>' };
    slot.innerHTML = `<div class="seg theme-seg" role="group" aria-label="Appearance">${["auto", "light", "dark"].map(t => `<button data-theme-set="${t}" aria-pressed="${t === cur}"><svg viewBox="0 0 24 24" aria-hidden="true">${ic[t]}</svg>${t[0].toUpperCase() + t.slice(1)}</button>`).join("")}</div>`;
    slot.addEventListener("click", e => { const b = e.target.closest("[data-theme-set]"); if (b) applyTheme(b.dataset.themeSet); });
  }
  applyTheme(cur);

  // tapping the tab you're already on scrolls back to the top, like a native app
  document.querySelector(".tabs")?.addEventListener("click", e => {
    const a = e.target.closest('a[aria-current="page"]');
    if (a) { e.preventDefault(); window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
  });
})();
