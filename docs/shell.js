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

  try { localStorage.removeItem("shelf-theme"); } catch {}      // the appearance switch was removed: follow the phone again

  // Installed on iPhone, the page runs under the status bar. iOS 26 sometimes reports the status bar
  // height as 0 when the app opens (a WebKit bug) and only corrects it after the page re-lays out,
  // so the top of the page sat in the status bar's blur until you scrolled. Measure it ourselves,
  // keep re-checking for a moment, and fall back to a safe value if iOS still says 0.
  const standalone = navigator.standalone || matchMedia("(display-mode: standalone)").matches;
  if (standalone) {
    const probe = document.createElement("div");
    probe.style.cssText = "position:fixed;top:0;left:0;width:0;visibility:hidden;pointer-events:none;height:env(safe-area-inset-top,0px)";
    document.body.appendChild(probe);
    const root = document.documentElement.style;
    const fullScreen = () => window.innerHeight >= screen.height - 1;      // the page reaches under the status bar
    const fit = () => {
      const h = probe.getBoundingClientRect().height;
      root.setProperty("--safe-top", (h > 0 ? h : fullScreen() ? 54 : 0) + "px");
    };
    fit(); requestAnimationFrame(fit);
    [100, 400, 1000, 2500].forEach(t => setTimeout(fit, t));
    addEventListener("resize", fit); addEventListener("orientationchange", () => setTimeout(fit, 300));
    addEventListener("pageshow", fit); document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && fit());
  }

  // tapping the tab you're already on scrolls back to the top, like a native app
  document.querySelector(".tabs")?.addEventListener("click", e => {
    const a = e.target.closest('a[aria-current="page"]');
    if (a) { e.preventDefault(); window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
  });
})();
