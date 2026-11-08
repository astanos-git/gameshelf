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

  // tapping the tab you're already on scrolls back to the top, like a native app
  document.querySelector(".tabs")?.addEventListener("click", e => {
    const a = e.target.closest('a[aria-current="page"]');
    if (a) { e.preventDefault(); window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
  });
})();
