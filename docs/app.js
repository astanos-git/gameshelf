/* Game Shelf: small helpers shared by the pages. */

// Folded explanation: how("Text…") -> "How this works" disclosure
const how = (text, label = "How this works") => `<details class="how"><summary>${label}</summary><p>${text}</p></details>`;

// In-page parts: <nav class="subnav"> with [data-show] buttons, sections with [data-part].
// Shows one part at a time, remembers it in the address (#part) and calls onShow after switching.
function setupParts(onShow) {
  const nav = document.querySelector(".subnav"), btns = [...nav.querySelectorAll("[data-show]")];
  const names = btns.map(b => b.dataset.show);
  // where the bar sits before it sticks: just below whatever comes before it
  const naturalTop = () => {
    const par = nav.parentElement, cs = getComputedStyle(par), gap = parseFloat(cs.rowGap) || 0;
    let prev = nav.previousElementSibling;
    while (prev && (["fixed", "absolute"].includes(getComputedStyle(prev).position) || !prev.getClientRects().length)) prev = prev.previousElementSibling;
    return prev ? prev.getBoundingClientRect().bottom + scrollY + gap : par.getBoundingClientRect().top + scrollY + parseFloat(cs.paddingTop);
  };
  const safeTop = () => parseFloat(getComputedStyle(nav).top) || 0;
  const show = (p, scroll) => {
    if (!names.includes(p)) p = names[0];
    document.querySelectorAll(".part-body[data-part]").forEach(s => s.hidden = s.dataset.part !== p);
    btns.forEach(b => b.setAttribute("aria-pressed", b.dataset.show === p));
    try { history.replaceState(null, "", p === names[0] ? location.pathname + location.search : "#" + p); } catch {}
    // a new part starts at its top: if the page is scrolled past the bar, bring the bar back to where it sticks
    if (scroll) { const top = naturalTop() - safeTop(); if (scrollY > top) window.scrollTo({ top, behavior: "auto" }); }
    onShow?.(p);
  };
  nav.addEventListener("click", e => { const b = e.target.closest("[data-show]"); if (b) show(b.dataset.show, true); });
  addEventListener("hashchange", () => show(location.hash.slice(1)));
  // a hairline under the bar once it sticks
  new IntersectionObserver(([e]) => nav.classList.toggle("stuck", e.intersectionRatio < 1), { threshold: [1], rootMargin: `-${safeTop() + 1}px 0px 0px 0px` }).observe(nav);
  show(location.hash.slice(1));
  return show;
}
