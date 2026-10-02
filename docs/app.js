/* Game Shelf: small helpers shared by the pages. */

// Folded explanation: how("Text…") -> "How this works" disclosure
const how = (text, label = "How this works") => `<details class="how"><summary>${label}</summary><p>${text}</p></details>`;

// In-page parts: <nav class="subnav"> with [data-show] buttons, sections with [data-part].
// Shows one part at a time, remembers it in the address (#part) and calls onShow after switching.
function setupParts(onShow) {
  const nav = document.querySelector(".subnav"), btns = [...nav.querySelectorAll("[data-show]")];
  const names = btns.map(b => b.dataset.show);
  const show = (p, scroll) => {
    if (!names.includes(p)) p = names[0];
    document.querySelectorAll(".part-body[data-part]").forEach(s => s.hidden = s.dataset.part !== p);
    btns.forEach(b => b.setAttribute("aria-pressed", b.dataset.show === p));
    try { history.replaceState(null, "", p === names[0] ? location.pathname + location.search : "#" + p); } catch {}
    if (scroll && nav.getBoundingClientRect().top < 0) window.scrollTo({ top: nav.offsetTop, behavior: "auto" });
    onShow?.(p);
  };
  nav.addEventListener("click", e => { const b = e.target.closest("[data-show]"); if (b) show(b.dataset.show, true); });
  addEventListener("hashchange", () => show(location.hash.slice(1)));
  // a hairline under the bar once it sticks
  new IntersectionObserver(([e]) => nav.classList.toggle("stuck", e.intersectionRatio < 1), { threshold: [1], rootMargin: "-1px 0px 0px 0px" }).observe(nav);
  show(location.hash.slice(1));
  return show;
}
