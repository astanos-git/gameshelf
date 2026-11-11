/* Pixel quest: your gaming history as a side-scrolling pixel-art adventure.
   A little wanderer walks from your first game to today. Every game is a monument on the road (a signpost, a banner, a stone or a tower, by hours played),
   its trophies are coins to collect, a platinum puts a golden cup on top, a dropped game is a grey ruin. Each year starts at a gate, and the scenery of a year
   is the land you spent most hours in (the same eight lands as the planet). One year on the road is one day in the sky: dawn in January, night in December.
   The wanderer and the scenery are original, generic pixel art; nothing is taken from a game's own art. */
import { REALMS, realmOf } from "./viz-planet.js";

const FONT = { A: "010101111101101", B: "110101110101110", C: "011100100100011", D: "110101101101110", E: "111100110100111", F: "111100110100100", G: "011100101101011", H: "101101111101101", I: "111010010010111",
  J: "001001001101010", K: "101101110101101", L: "100100100100111", M: "101111111101101", N: "110101101101101", O: "010101101101010", P: "110101110100100", Q: "010101101110011", R: "110101110101101",
  S: "011100010001110", T: "111010010010010", U: "101101101101111", V: "101101101101010", W: "101101111111101", X: "101101010101101", Y: "101101010010010", Z: "111001010100111",
  0: "111101101101111", 1: "010110010010111", 2: "110001010100111", 3: "110001010001110", 4: "101101111001001", 5: "111100110001110", 6: "011100111101111", 7: "111001010010010", 8: "111101111101111", 9: "111101111001110",
  ":": "000010000010000", "-": "000000111000000", ".": "000000000000010", "'": "010010000000000", "&": "010101010101011", "!": "010010010000010", "?": "110001010000010", "+": "000010111010000" };
const plain = s => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[™®©]/g, "").toUpperCase().replace(/[^A-Z0-9:.'&!?+ -]/g, " ").replace(/\s+/g, " ").trim();
const hash = (s, salt = 0) => { let h = 2166136261 ^ salt; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995); h ^= h >>> 15; return ((h >>> 0) % 100000) / 100000; };
const rgb = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const mix = (a, b, t) => { const A = rgb(a), B = rgb(b); return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(",")})`; };
const HEX = new Map(), hex = (a, b, t) => { t = Math.round(t * 40) / 40; const key = a + b + t; let c = HEX.get(key); if (!c) { const A = rgb(a), B = rgb(b); c = "#" + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, "0")).join(""); if (HEX.size > 6000) HEX.clear(); HEX.set(key, c); } return c; };
const COIN = ["#c98a5e", "#d5dce8", "#f6c945", "#9fe0ff"], INK = "#f4efe2", DARK = "#161222";
/* the look of each land: far hills, nearer hills, ground, and one landmark on the horizon */
const LOOK = {
  fantasy: { far: ["tri", 46, 30, "#3d5f7a"], mid: ["tri", 17, 15, "#2c6b45"], grass: "#4fa04a", dirt: "#6b4a34", prop: "pine", feat: "castle" },
  scifi: { far: ["block", 9, 34, "#3a3470"], mid: ["block", 6, 17, "#262450"], grass: "#5b6bd0", dirt: "#2a2a52", prop: "crystal", feat: "spire" },
  horror: { far: ["tri", 30, 20, "#3b3552"], mid: ["round", 24, 9, "#2a2538"], grass: "#5c5670", dirt: "#33293a", prop: "tomb", feat: "deadtree" },
  waste: { far: ["mesa", 52, 24, "#b0683e"], mid: ["round", 38, 9, "#8f5a3a"], grass: "#d2a560", dirt: "#8a5f3c", prop: "cactus", feat: "pylon" },
  old: { far: ["round", 60, 20, "#8aa0b0"], mid: ["round", 30, 10, "#7f9455"], grass: "#a5b55a", dirt: "#7a6240", prop: "column", feat: "aqueduct" },
  arena: { far: ["mesa", 80, 18, "#5d7f9a"], mid: ["round", 44, 6, "#3f9a50"], grass: "#58c05a", dirt: "#4a7a3c", prop: "goal", feat: "lights" },
  wonder: { far: ["round", 40, 22, "#c98ac0"], mid: ["round", 22, 12, "#e7a3c6"], grass: "#7fd6a0", dirt: "#b77aa8", prop: "mushroom", feat: "bigshroom" },
  story: { far: ["sea", 1, 9, "#3f7fa8"], mid: ["round", 50, 8, "#c79a55"], grass: "#d9b86a", dirt: "#9a7446", prop: "lantern", feat: "lighthouse" },
};
const HERO = { k: "#1a1423", s: "#f2c9a0", h: "#3b2a4a", c: "#e0533d", d: "#a83a2c", b: "#3a2a22", p: "#c9a35a", y: "#ffd84d" };
const BODY = ["..hhhh...", ".hhhhhh..", ".hhsssh..", ".hsskss..", "..ssss...", "yycccc...", ".pccccc..", ".pcccdc..", "..cccc..."];
const LEGS = [["..c..c...", "..b..b...", "..bb.bb.."], ["..cc.c...", ".bb...b..", "......bb."], ["..c..c...", "..b..b...", "..bb.bb.."], ["...cc....", "..b.bb...", ".bb..b..."]];

export function createQuest(env) {
  const { canvas, DATA, FLAGS, info, esc, calm } = env, $ = id => document.getElementById(id), ctx = canvas.getContext("2d");
  const ms = s => s ? new Date(s).getTime() : null;
  /* the road */
  const games = DATA.games.filter(g => (g.hours || 0) > 0 || g.trophies_earned > 0).map(g => { const mk = Object.keys(g.months || {}).sort();
    const birth = ms(g.first_played) ?? ms(g.first_trophy_at) ?? (mk[0] ? ms(mk[0] + "-01") : null) ?? ms(g.acquired) ?? Date.now(), flag = FLAGS[g.name]?.flag, e = g.earned || {};
    return { g, name: g.name, birth, hours: g.hours || Math.min(40, (g.trophies_earned || 0) * .6) || 1, guess: !g.hours, plat: !!g.platinum, dropped: flag === "dropped", beaten: flag === "beaten" || g.status === "completed",
      realm: REALMS[realmOf(g)], earned: [e.bronze || 0, e.silver || 0, e.gold || 0, e.platinum || 0] }; }).sort((a, b) => a.birth - b.birth);
  const backlog = DATA.games.filter(g => !((g.hours || 0) > 0 || g.trophies_earned > 0));
  const M = { x: 0, playing: false, speed: 1, segs: [], gates: [], coins: [], fx: [], clock: 0, phi: .3, jump: 0, vy: 0, cur: null, L: 0 };
  let x = 46, year = null, trophies = 0, hours = 0; const yearHours = {};
  games.forEach((o, i) => { const y = new Date(o.birth).getFullYear(), t = o.earned.reduce((a, b) => a + b, 0);
    (yearHours[y] = yearHours[y] || {})[o.realm.id] = (yearHours[y][o.realm.id] || 0) + o.hours;
    if (y !== year) { M.gates.push({ x, y }); x += year === null ? 22 : 34; year = y; }
    const w = Math.round(13 + 4.2 * Math.sqrt(o.hours)), seg = { x0: x, w, o, i, cx: x + (w >> 1), t0: trophies, h0: hours, n: t, tier: o.hours < 4 ? 0 : o.hours < 15 ? 1 : o.hours < 45 ? 2 : 3, y };
    const start = new Date(y, 0, 1).getTime(); seg.phi = (o.birth - start) / (new Date(y + 1, 0, 1).getTime() - start);
    const n = Math.min(t, Math.floor((w - 4) / 6)), bag = []; o.earned.forEach((c, gr) => { for (let k = 0; k < Math.round(c / Math.max(1, t) * n) || (gr === 3 && c && !k); k++) bag.push(gr); });
    bag.slice(0, Math.max(n, o.plat ? 1 : 0)).forEach((gr, k, all) => M.coins.push({ x: x + 4 + (k + .5) * (w - 6) / all.length, y: 17 + Math.round(Math.sin((k + .5) / all.length * Math.PI) * (seg.tier > 1 ? 9 : 4)), gr, seg }));
    trophies += t; hours += o.hours; M.segs.push(seg); x += w; });
  M.gates.forEach(g => { const e = Object.entries(yearHours[g.y] || {}).sort((a, b) => b[1] - a[1])[0]; g.look = LOOK[e ? e[0] : "story"]; g.realm = REALMS.find(r => r.id === (e ? e[0] : "story")); });
  M.endX = x + 26; M.L = M.endX; M.trophies = trophies; M.hours = hours;
  const lookAt = wx => { let g = M.gates[0]; for (const k of M.gates) { if (k.x <= wx) g = k; else break; } return g; };
  M.legend = `<span>Monuments = games (bigger = more hours)</span><span>coins = trophies</span><span>gates = years</span>`;

  /* drawing, in big pixels */
  let W = 130, Hh = 280, S = 3, topY = 60, G = 200;
  const R = (x, y, w, h, c) => { if (c) ctx.fillStyle = c; ctx.fillRect(Math.round(x), Math.round(y), w, h); };
  function text(s, x, y, c, k = 1) { ctx.fillStyle = c; for (const ch of String(s)) { const g = FONT[ch]; if (g) for (let i = 0; i < 15; i++) if (g[i] === "1") ctx.fillRect(Math.round(x) + (i % 3) * k, Math.round(y) + (i / 3 | 0) * k, k, k); x += 4 * k; } }
  const label = (s, cx, y, c = INK, k = 1) => { const w = String(s).length * 4 * k - k, x = Math.round(Math.max(3, Math.min(W - w - 3, cx - w / 2))); if (k > 1) text(s, x + k, y + k, DARK, k); else { ctx.globalAlpha = .78; R(x - 2, y - 2, w + 4, 9, DARK); ctx.globalAlpha = 1; } text(s, x, y, c, k); };
  function resize() {
    S = innerWidth < 700 ? 3 : 4; W = Math.ceil(innerWidth / S); Hh = Math.ceil(innerHeight / S); canvas.width = W; canvas.height = Hh;
    topY = Math.round(document.querySelector("header").getBoundingClientRect().bottom / S) + 2; G = Math.round(document.querySelector("footer").getBoundingClientRect().top / S) - 15; draw();
  }
  const shape = (kind, period, amp, wx, seed) => { const cell = Math.floor(wx / period), f = wx / period - cell, r = hash(cell, seed);
    if (kind === "tri") return amp * (.45 + .55 * r) * (1 - Math.abs(2 * f - 1));
    if (kind === "round") return amp * (.5 + .5 * r) * Math.sqrt(Math.max(0, 1 - (2 * f - 1) ** 2));
    if (kind === "mesa") return amp * (.5 + .5 * r) * Math.min(1, Math.min(f, 1 - f) * 5) * (r > .35 ? 1 : .25);
    if (kind === "block") return f > .88 ? 0 : amp * (.25 + .75 * r);
    return amp; };
  function landmark(kind, x, base, c, night, t) {      // a silhouette on the horizon
    if (kind === "castle") { R(x, base - 13, 13, 13, c); R(x - 2, base - 19, 4, 19); R(x + 11, base - 19, 4, 19); R(x - 3, base - 21, 2, 2); R(x + 1, base - 21, 2, 2); R(x + 10, base - 21, 2, 2); R(x + 14, base - 21, 2, 2); R(x + 5, base - 16, 3, 3); if (night) { R(x + 5, base - 9, 2, 3, "#ffd27a"); R(x - 1, base - 15, 1, 2); } }
    if (kind === "spire") { R(x, base - 44, 5, 44, c); R(x + 2, base - 54, 1, 10); R(x - 3, base - 30, 11, 2); R(x + 2, base - 55, 1, 1, (t * 2 | 0) % 2 ? "#ff5fd2" : c); for (let k = 0; k < 6; k++) R(x + 1 + (k % 2) * 2, base - 40 + k * 6, 1, 2, "#62e8ff"); }
    if (kind === "deadtree") { R(x, base - 17, 2, 17, c); R(x - 4, base - 13, 4, 1); R(x - 5, base - 16, 1, 3); R(x + 2, base - 11, 5, 1); R(x + 6, base - 15, 1, 4); R(x + 1, base - 21, 1, 4); R(x - 2, base - 20, 1, 3); }
    if (kind === "pylon") { R(x, base - 26, 1, 26, c); R(x + 6, base - 26, 1, 26); for (let k = 0; k < 5; k++) R(x, base - 4 - k * 5, 7, 1); R(x - 4, base - 26, 15, 1); R(x - 4, base - 20, 15, 1); }
    if (kind === "aqueduct") { R(x - 4, base - 20, 42, 3, c); for (let k = 0; k < 6; k++) R(x - 4 + k * 8, base - 17, 2, 17); for (let k = 0; k < 5; k++) { R(x - 2 + k * 8, base - 17, 6, 1); R(x - 2 + k * 8, base - 16, 1, 1); R(x + 3 + k * 8, base - 16, 1, 1); } }
    if (kind === "lights") { R(x, base - 34, 1, 34, c); R(x - 3, base - 37, 7, 3); if (night) { R(x - 2, base - 36, 5, 1, "#fff6c9"); ctx.globalAlpha = .12; for (let k = 1; k < 14; k++) R(x - 3 - k, base - 34 + k * 2, 7 + k * 2, 2, "#fff6c9"); ctx.globalAlpha = 1; } }
    if (kind === "bigshroom") { R(x + 3, base - 16, 3, 16, "#f3e6d0"); R(x - 4, base - 21, 17, 5, "#e2504a"); R(x - 2, base - 23, 13, 2); R(x - 1, base - 20, 2, 2, "#ffffff"); R(x + 6, base - 22, 2, 2); R(x + 10, base - 19, 1, 1); }
    if (kind === "lighthouse") { R(x, base - 26, 5, 26, "#e9e2d0"); R(x, base - 20, 5, 3, "#d0483c"); R(x, base - 10, 5, 3); R(x - 1, base - 29, 7, 3, c); R(x + 1, base - 32, 3, 3, night ? "#fff2a8" : "#bcd"); if (night) { ctx.globalAlpha = .16; const dir = Math.sin(t * .8) > 0 ? 1 : -1; for (let k = 0; k < 22; k++) R(x + 2 + dir * (3 + k), base - 31 - (k >> 3), 1, 2 + (k >> 2), "#fff2a8"); ctx.globalAlpha = 1; } }
  }
  function prop(kind, x, night) {                      // a small thing growing by the road
    if (kind === "pine") { R(x, G - 2, 1, 2, "#5b4030"); [[0, 1], [-1, 3], [-2, 5], [-1, 3], [-2, 5], [-3, 7]].forEach(([dx, w], k) => R(x + dx, G - 8 + k, w, 1, k < 3 ? "#2f8a4a" : "#236b3a")); }
    if (kind === "crystal") { R(x, G - 7, 1, 7, "#bff6ff"); R(x - 1, G - 5, 3, 5, "#62e8ff"); R(x + 2, G - 3, 1, 3, "#b58cff"); }
    if (kind === "tomb") { R(x - 2, G - 5, 5, 5, "#8f93a0"); R(x - 1, G - 6, 3, 1); R(x, G - 4, 1, 3, "#5c606c"); R(x - 1, G - 3, 3, 1); }
    if (kind === "cactus") { R(x, G - 8, 2, 8, "#6f9a4a"); R(x - 2, G - 6, 1, 3); R(x - 2, G - 4, 2, 1); R(x + 3, G - 7, 1, 3); R(x + 2, G - 5, 2, 1); }
    if (kind === "column") { R(x - 1, G - 1, 5, 1, "#d9d0bb"); R(x, G - 9, 3, 8, "#f3eddd"); R(x + 2, G - 9, 1, 8, "#cfc6b0"); R(x - 1, G - 10, 5, 1, "#e9e2d0"); }
    if (kind === "goal") { R(x, G - 6, 1, 6, "#ffffff"); R(x + 8, G - 6, 1, 6); R(x, G - 7, 9, 1); ctx.globalAlpha = .35; for (let k = 2; k < 8; k += 2) R(x + k, G - 6, 1, 6); ctx.globalAlpha = 1; }
    if (kind === "mushroom") { R(x, G - 3, 2, 3, "#f3e6d0"); R(x - 2, G - 5, 6, 2, "#e2504a"); R(x - 1, G - 6, 4, 1); R(x - 1, G - 5, 1, 1, "#ffffff"); R(x + 2, G - 6, 1, 1); }
    if (kind === "lantern") { R(x, G - 8, 1, 8, "#3b3440"); R(x - 1, G - 11, 3, 3, night ? "#ffd27a" : "#c9a35a"); R(x - 1, G - 12, 3, 1, "#3b3440"); }
  }
  function monument(seg, sx, night, t) {
    const o = seg.o, grey = o.dropped, acc = grey ? "#5d5d66" : o.realm.accent, st = grey ? "#6a6a74" : "#a9afbd", sd = grey ? "#4c4c55" : "#757b8c"; let top = G - 9;
    if (seg.tier === 0) { R(sx, G - 6, 1, 6, grey ? "#55505a" : "#7a5a3a"); R(sx - 3, G - 10, 7, 4, grey ? "#77727c" : "#c79a5c"); R(sx - 2, G - 8, 5, 1, grey ? "#55505a" : "#7a5a3a"); top = G - 10; }
    else if (seg.tier === 1) { R(sx, G - 16, 1, 16, sd); const wv = (t * 4 + seg.i | 0) % 2; R(sx + 1, G - 16, 4, 5, acc); R(sx + 5, G - 16 + wv, 3, 5, acc); R(sx + 1, G - 14, 7, 1, hex(acc, "#000000", .25)); R(sx - 1, G - 1, 3, 1, sd); top = G - 17; }
    else if (seg.tier === 2) { R(sx - 5, G - 2, 11, 2, sd); R(sx - 3, G - 15, 7, 13, st); R(sx - 2, G - 16, 5, 1, st); R(sx + 3, G - 15, 1, 13, sd); R(sx - 1, G - 12, 3, 3, acc); R(sx - 1, G - 7, 3, 1, sd); R(sx - 1, G - 5, 3, 1, sd); top = G - 16; }
    else { R(sx - 6, G - 2, 13, 2, sd); R(sx - 5, G - 26, 11, 24, st); R(sx + 4, G - 26, 2, 24, sd); for (let k = 0; k < 3; k++) R(sx - 6 + k * 5, G - 29, 3, 3, st); R(sx - 1, G - 7, 3, 5, DARK); R(sx - 1, G - 19, 3, 4, night && !grey ? "#ffd27a" : "#2a3350");
      R(sx - 5, G - 13, 9, 1, sd); R(sx, G - 36, 1, 7, sd); const wv = (t * 4 + seg.i | 0) % 2; R(sx + 1, G - 36 + wv, 5, 3, acc); top = G - 37; }
    if (grey) { R(sx - 1, top + 5, 1, 2, DARK); R(sx, top + 7, 1, 2, DARK); }                                 // a crack
    if (o.plat) { const y = top - 8, tw = (t * 3 + seg.i | 0) % 3; R(sx - 2, y, 5, 3, "#f6c945"); R(sx - 3, y, 1, 2); R(sx + 3, y, 1, 2); R(sx - 1, y + 3, 3, 1); R(sx, y + 4, 1, 2); R(sx - 1, y + 6, 3, 1); R(sx - 1, y, 1, 2, "#fff3b0");
      if (tw === 0) { R(sx + 4, y - 3, 1, 3, "#ffffff"); R(sx + 3, y - 2, 3, 1); } if (tw === 1) R(sx - 5, y - 1, 1, 1, "#ffffff"); top = y; }
    else if (o.beaten) { R(sx - 2, top - 3, 1, 1, "#7be08a"); R(sx - 1, top - 2, 1, 1); R(sx, top - 3, 1, 1); R(sx + 1, top - 4, 1, 1); top -= 4; }   // a small "done" tick
    return top;
  }
  const SKY = [[0, "#0a0f2e", "#1c2552"], [.1, "#3a3676", "#ee8a5c"], [.26, "#4a9fe6", "#c2e6f8"], [.72, "#4a9fe6", "#c2e6f8"], [.86, "#4c3878", "#f39a4c"], [1, "#0a0f2e", "#1c2552"]];
  const sky = p => { for (let i = 1; i < SKY.length; i++) if (p <= SKY[i][0]) { const a = SKY[i - 1], b = SKY[i], t = (p - a[0]) / (b[0] - a[0]); return [hex(a[1], b[1], t), hex(a[2], b[2], t)]; } return [SKY[0][1], SKY[0][2]]; };
  const nightAt = p => Math.max(0, Math.min(1, p < .5 ? 1 - (p - .06) / .12 : (p - .8) / .12));

  function draw() {
    const t = M.clock, hx = Math.round(W * .34), cam = M.x - hx, night = nightAt(M.phi), [top, bot] = sky(M.phi);
    ctx.globalAlpha = 1;
    for (let k = 0; k < 10; k++) R(0, Math.round(G * k / 10), W, Math.ceil(G / 10) + 1, hex(top, bot, Math.min(1, k / 8)));                                 // the sky, in bands
    if (night > 0) { ctx.globalAlpha = night; for (let k = 0; k < 46; k++) { const tw = Math.sin(t * 2 + k * 1.7) > .6; R(hash(k, 1) * W, topY - 20 + hash(k, 2) * (G - topY - 20), 1, 1, tw ? "#ffffff" : "#9fb0e8"); } ctx.globalAlpha = 1; }
    { const d = (M.phi - .1) / .76, on = d > 0 && d < 1, m = M.phi < .5 ? .5 + M.phi / .2 : (M.phi - .8) / .4, a = on ? d : m, bx = Math.round(W * (.08 + .84 * a)), by = Math.round(topY + 34 - Math.sin(a * Math.PI) * 26);
      if (on) { R(bx - 4, by - 3, 9, 7, "#fff1a8"); R(bx - 3, by - 4, 7, 9); R(bx - 2, by - 2, 5, 5, "#fffbe0"); }
      else { R(bx - 3, by - 2, 7, 5, "#e8ecff"); R(bx - 2, by - 3, 5, 7); R(bx + 1, by - 1, 2, 2, "#b9c2e8"); R(bx - 2, by + 1, 1, 1); } }
    for (let k = 0; k < 7; k++) { const cx = ((hash(k, 3) * 400 - cam * .08 - t * (1 + k % 3)) % (W + 60) + W + 60) % (W + 60) - 30, cy = topY + 30 + hash(k, 4) * 44, c = hex("#ffffff", bot, .25 + night * .4);
      R(cx, cy, 16, 3, c); R(cx + 3, cy - 2, 9, 2); R(cx + 5, cy + 3, 8, 1); }
    // far and near hills: each column belongs to the year it sits in, so a new land slides in from the right
    for (const [par, key, lift, shade] of [[.22, "far", 0, .42], [.5, "mid", 0, .12]]) {
      for (let sx = 0; sx < W; sx++) { const lx = sx + cam * par, look = lookAt(cam + (sx - hx) / par + hx).look, [kind, period, amp, colr] = look[key];
        const h = Math.round(shape(kind, period, amp, lx, key === "far" ? 5 : 6)), c = hex(hex(colr, bot, shade), "#0a0f2e", night * .5);
        if (kind === "sea") { R(sx, G - 9, 1, 9, c); if (hash(Math.floor(lx / 3), 7) > .8 && ((t * 2 + lx) | 0) % 3 === 0) R(sx, G - 8 + (Math.floor(lx) % 7), 1, 1, "#d8f0ff"); }
        else if (h > 0) { R(sx, G - h - lift, 1, h + lift, c); if (kind === "block" && h > 5 && Math.floor(lx) % 2 === 0) for (let y = G - h + 2; y < G - 2; y += 3) if (hash(Math.floor(lx) * 31 + y, 8) > (night ? .45 : .8)) R(sx, y, 1, 1, hash(y, 9) > .5 ? "#62e8ff" : "#ff8fe0"); } }
      if (key === "mid") { const first = Math.floor((cam * par - 40) / 150); for (let k = first; k <= first + Math.ceil(W / 150) + 1; k++) { if (hash(k, 10) < .25) continue; const lx = k * 150 + hash(k, 11) * 80, sx = Math.round(lx - cam * par), look = lookAt(cam + (sx - hx) / par + hx).look;
          landmark(look.feat, sx, G, hex(hex(look.far[3], "#101020", .45), "#0a0f2e", night * .4), night > .5, t); } }
    }
    // the ground
    for (let sx = 0; sx < W; sx++) { const wx = sx + cam, look = wx > M.endX + 20 ? null : lookAt(wx).look, gx = Math.floor(wx);
      const grass = look ? look.grass : "#5a6070", dirt = look ? look.dirt : "#3a3f4c";
      R(sx, G, 1, 2, hash(gx, 12) > .8 ? hex(grass, "#ffffff", .18) : grass); R(sx, G + 2, 1, Hh - G, dirt); if (hash(gx, 13) > .55) R(sx, G + 3 + Math.floor(hash(gx, 14) * 9), 1, 1, hex(dirt, "#000000", .25));
      if (hash(gx, 15) > .9) R(sx, G - 1, 1, 1, hex(grass, "#000000", .15)); }
    // things on the road
    const first = M.segs.findIndex(s => s.x0 + s.w > cam - 20), tops = [];
    for (let k = Math.max(0, first); k < M.segs.length; k++) { const s = M.segs[k]; if (s.x0 > cam + W + 20) break; if (first < 0) break;
      const pk = s.o.realm.id, pr = LOOK[pk].prop; if (s.w > 20) prop(pr, Math.round(s.x0 - cam + 3 + hash(s.i, 16) * 3), night > .5); if (s.w > 38) prop(pr, Math.round(s.x0 + s.w - cam - 6 - hash(s.i, 17) * 4), night > .5);
      tops.push([s, monument(s, Math.round(s.cx - cam), night > .5, t)]); }
    for (const g of M.gates) { const sx = Math.round(g.x - cam); if (sx < -30 || sx > W + 10) continue;                                                       // a gate for each new year
      R(sx, G - 30, 3, 30, "#8d8a9a"); R(sx + 17, G - 30, 3, 30); R(sx + 2, G - 30, 1, 30, "#5f5c70"); R(sx + 19, G - 30, 1, 30); R(sx - 2, G - 33, 24, 3, "#a9a6b8"); R(sx - 2, G - 31, 24, 1, "#5f5c70");
      R(sx - 1, G - 2, 5, 2, "#5f5c70"); R(sx + 16, G - 2, 5, 2); label(g.y, sx + 10, G - 46, "#ffe9a8", 2); }
    { const sx = Math.round(M.endX - cam); if (sx > -40 && sx < W + 20) {                                                                                    // today: a campfire, and the road ahead
        R(sx + 8, G - 2, 7, 2, "#5b4030"); const f = (t * 8 | 0) % 3; R(sx + 9, G - 6 - f, 5, 4 + f, "#ff8a2e"); R(sx + 10, G - 5 - f, 3, 3 + f, "#ffd84d"); R(sx + 11, G - 8 - f * 2, 1, 2, "#ff8a2e");
        label("TODAY", sx + 12, G - 20, INK); R(sx + 34, G - 10, 1, 10, "#7a5a3a"); R(sx + 28, G - 15, 13, 6, "#c79a5c"); text(String(backlog.length), sx + 35 - String(backlog.length).length * 2, G - 14, DARK);
        for (let k = 0; k < 40; k++) { const ex = sx + 46 + k * 5; if (ex > W) break; R(ex, G - 3, 3, 3, hex(REALMS[realmOf(backlog[k % Math.max(1, backlog.length)] || {})].accent, "#ffffff", .3)); R(ex + 1, G - 4, 1, 1); } } }
    for (const c of M.coins) { const sx = Math.round(c.x - cam); if (sx < -4 || sx > W + 4 || c.x < M.x - 1) continue; const spin = (t * 6 + c.x | 0) % 4, y = G - c.y - (c.gr === 3 ? 3 : 0);
      if (spin === 3) R(sx, y - 2, 1, 4, COIN[c.gr]); else { R(sx - 1, y - 2, 3, 4, COIN[c.gr]); R(sx - 1, y - 2, 1, 1, "#ffffff"); if (c.gr === 3) { R(sx - 2, y - 1, 5, 2, COIN[3]); R(sx, y - 4, 1, 1, "#ffffff"); } } }
    // the wanderer
    { const moving = M.playing && M.x < M.endX, frame = moving ? (t * 9 | 0) % 4 : 0, y0 = G - 12 - Math.round(M.jump), rows = [...BODY, ...LEGS[M.jump > 1 ? 3 : frame]];
      rows.forEach((row, ry) => { for (let cx = 0; cx < 9; cx++) { const ch = row[cx]; if (ch !== ".") R(hx - 4 + cx, y0 + ry + (moving && frame % 2 && ry < 9 ? 1 : 0), 1, 1, HERO[ch]); } });
      if (moving && (t * 6 | 0) % 2) R(hx - 6, y0 + 4, 2, 1, HERO.y); else R(hx - 6, y0 + 6, 2, 1, HERO.y); }                                                  // the scarf flaps
    M.fx = M.fx.filter(p => t - p.t < p.life);
    for (const p of M.fx) { const a = (t - p.t) / p.life; R(p.x - cam + p.vx * a, G - p.y - p.vy * a + 18 * a * a * (p.g || 0), 1, 1, a > .7 && p.c2 ? p.c2 : p.c); }
    if (night > 0) { ctx.globalAlpha = night * .3; R(0, 0, W, Hh, "#0a0f3a"); ctx.globalAlpha = 1; }                                                          // dusk falls on everything...
    for (const [s, top] of tops) if (s.tier >= 2 && Math.abs(s.cx - M.x) < 46) label(plain(s.o.name).slice(0, 26), Math.round(s.cx - cam), top - 8 - (s.i % 2) * 7, s.o.dropped ? "#b9b9c4" : INK);   // ...except the names
    // score, like an old cartridge
    const cur = M.segs[Math.max(0, Math.min(M.segs.length - 1, M.segIndex | 0))], prog = cur ? Math.max(0, Math.min(1, (M.x - cur.x0) / cur.w)) : 0, done = M.x >= M.endX - 1;
    const tr = done ? M.trophies : cur ? Math.round(cur.t0 + cur.n * prog) : 0, hr = done ? M.hours : cur ? cur.h0 + cur.o.hours * prog : 0, yr = cur && M.x >= M.gates[0].x ? lookAt(M.x).y : M.gates[0].y;
    label(yr, 16, topY + 3, "#ffe9a8", 2); const rl = (s, y, c) => label(s, W - 3 - String(s).length * 2, y, c);
    rl(String(tr).padStart(4, "0"), topY + 3, INK); R(W - 24, topY + 3, 3, 5, COIN[2]); R(W - 24, topY + 3, 1, 1, "#ffffff"); rl(`${Math.round(hr)} H`, topY + 11, "#bfe0ff");
    label((lookAt(M.x).realm?.name || "").toUpperCase(), 4 + (lookAt(M.x).realm?.name || "").length * 2, topY + 16, "#d9d4e6");
    M.yr = yr;
  }
  const burst = (x, y, c, n, big) => { for (let k = 0; k < n; k++) { const a = Math.random() * 6.283, v = (big ? 14 : 6) * (.4 + Math.random()); M.fx.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v + (big ? 8 : 3), c, c2: "#ffffff", t: M.clock, life: big ? .9 : .4, g: 1 }); } };
  function enterSeg(s) { const o = s.o, g = o.g; if (o.hours < 3 && !o.plat) return;
    const state = o.plat ? "Platinum ✦" : o.beaten ? "Finished" : o.dropped ? "Dropped" : "Started";
    info(g.image ? `<img src="${esc(g.image)}" alt="">` : "🗺️", o.name, `${s.y} · ${o.guess ? "" : (o.hours >= 10 ? Math.round(o.hours) : o.hours) + " h · "}${state} · ${o.realm.name}`); }
  function button() { const b = $("play"); b.textContent = M.playing ? "❚❚" : "▶"; b.setAttribute("aria-label", M.playing ? "Pause" : "Play"); }
  function play(on) { M.playing = on && M.x < M.L; button(); }
  function toggle() { if (M.x >= M.L - .5) seek(0); play(!M.playing); }
  function locate() { let i = M.segs.findIndex(s => s.x0 + s.w > M.x); if (i < 0) i = M.segs.length - 1; M.segIndex = i; return M.segs[i]; }
  function frame(dt) {
    M.clock += dt;
    if (M.playing) { const before = M.x; M.x = Math.min(M.L, M.x + dt * 44 * M.speed);
      for (const c of M.coins) { if (c.x > before && c.x <= M.x) burst(c.x, c.y, COIN[c.gr], c.gr === 3 ? 26 : 5, c.gr === 3); if (c.y > 18 && M.jump === 0 && M.vy === 0 && c.x > before + 7 && c.x <= M.x + 7) M.vy = 52; }
      const s = locate(); if (s !== M.cur && M.x >= s.x0) { M.cur = s; enterSeg(s); }
      if (M.x >= M.L) { play(false); burst(M.endX + 12, 10, "#ffd84d", 30, true); info("🔥", "Today", `${M.segs.length} games, ${Math.round(M.hours).toLocaleString()} hours and ${M.trophies.toLocaleString()} trophies on the road so far. ${backlog.length} games wait ahead.`); }
      $("scrub").value = Math.round(M.x / M.L * 1000); }
    if (M.jump > 0 || M.vy > 0) { M.jump += M.vy * dt; M.vy -= 190 * dt; if (M.jump <= 0) { M.jump = 0; M.vy = 0; } }
    const s = M.segs[M.segIndex | 0], want = M.x >= M.endX - 1 ? .93 : s ? s.phi * .86 + .07 : .3; let d = want - M.phi; if (d < -.5) d += 1; if (d > .5) d -= 1; M.phi = ((M.phi + d * Math.min(1, dt * 1.5)) % 1 + 1) % 1;
    draw(); $("yr").textContent = M.yr ?? "";
  }
  function seek(p) { M.x = Math.max(0, Math.min(M.L, p * M.L)); M.fx = []; const s = locate(); M.cur = s; if (s) { M.phi = s.phi * .86 + .07; enterSeg(s); } }
  function hello() { info("🗺️", "Your history, as a pixel quest", `A wanderer walks through ${M.gates.length} years: every game is a monument, every trophy a coin. Tap a monument to read it, tap anywhere else to jump.`); }
  function enter() { $("legend").innerHTML = M.legend; hello(); resize(); if (M.x >= M.L - .5) seek(0); if (calm) { seek(1); play(false); } else play(true); }
  function leave() { play(false); $("play").textContent = "↺"; $("play").setAttribute("aria-label", "Replay"); }
  function pick(ev) {
    const r = canvas.getBoundingClientRect(), wx = (ev.clientX - r.left) / S + M.x - Math.round(W * .34), y = (ev.clientY - r.top) / S;
    const s = M.segs.find(s => Math.abs(s.cx - wx) < Math.max(6, s.w / 2 - 1));
    if (s && y > G - 60 && y < G + 6 && Math.abs(s.cx - wx) < 9) { const o = s.o, g = o.g, e = o.earned, state = o.plat ? "Platinum ✦" : o.beaten ? "Finished" : o.dropped ? "Dropped" : "Started";
      info(g.image ? `<img src="${esc(g.image)}" alt="">` : "🗺️", o.name, `${s.y} · ${o.guess ? "" : (o.hours >= 10 ? Math.round(o.hours) : o.hours) + " h · "}${state} · ${s.n} trophies${e[2] ? ` (${e[2]} gold)` : ""} · ${o.realm.name}`); return; }
    if (M.jump === 0) M.vy = 62;
  }
  seek(0);
  return Object.assign(M, { frame, enter, leave, pick, seek, toggle, resize, speedTo: s => { M.speed = s; } });
}
