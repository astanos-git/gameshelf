/* Game Shelf offline support: always try the network first (so data is fresh after every refresh),
   fall back to the last copy when offline or when the network takes too long. Fonts are cached once. */
const CACHE = "gameshelf-v1";
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));

const timeout = (ms) => new Promise((_, no) => setTimeout(() => no(new Error("slow")), ms));
self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET") return;
  if (/fonts\.(googleapis|gstatic)\.com$/.test(url.hostname)) {          // fonts: cache first
    e.respondWith(caches.open(CACHE).then(c => c.match(req).then(hit => hit || fetch(req).then(r => (r.ok && c.put(req, r.clone()), r)))));
    return;
  }
  if (url.origin !== location.origin) return;                            // covers, Wikipedia, GitHub: browser default
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const net = fetch(req).then(r => { if (r.ok) c.put(req, r.clone()); return r; });
    try { return await Promise.race([net, timeout(req.mode === "navigate" ? 4000 : 6000)]); }
    catch { return (await c.match(req, { ignoreSearch: req.mode === "navigate" })) || net; }   // slow network keeps going in the background
  })());
});
