/* The music box: your trophy history as a punched paper strip, drawn in thin pixel lines, that actually plays.
   One row = one day you earned trophies. Each trophy is a hole: left = common (low notes), right = rare (high notes), colour = grade.
   Quiet stretches are squeezed to a short rest, a new game is printed on the strip and rings a low note, a platinum plays a rising chord. */
const DAY = 864e5, LANES = 15, LW = 8, RH = 8, SW = LANES * LW + 1, CASE = 46, BPS = 5;
const BG = "#0b0d14", INK = "#e8e4d8", GCOL = ["#c98a5e", "#c9d2e0", "#f2c94c", "#9fd8ff"], GNAME = ["bronze", "silver", "gold", "platinum"];
const SEMI = [0, 2, 4, 7, 9], MONTH = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const FONT = { A: "010101111101101", B: "110101110101110", C: "011100100100011", D: "110101101101110", E: "111100110100111", F: "111100110100100", G: "011100101101011", H: "101101111101101", I: "111010010010111",
  J: "001001001101010", K: "101101110101101", L: "100100100100111", M: "101111111101101", N: "110101101101101", O: "010101101101010", P: "110101110100100", Q: "010101101110011", R: "110101110101101",
  S: "011100010001110", T: "111010010010010", U: "101101101101111", V: "101101101101010", W: "101101111111101", X: "101101010101101", Y: "101101010010010", Z: "111001010100111",
  0: "111101101101111", 1: "010110010010111", 2: "110001010100111", 3: "110001010001110", 4: "101101111001001", 5: "111100110001110", 6: "011100111101111", 7: "111001010010010", 8: "111101111101111", 9: "111101111001110",
  ":": "000010000010000", "-": "000000111000000", ".": "000000000000010", "'": "010010000000000", "&": "010101010101011", "!": "010010010000010", "?": "110001010000010", "+": "000010111010000" };
const hash = s => { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) % 1000; };
const plain = s => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[™®©]/g, "").toUpperCase().replace(/[^A-Z0-9:.'&!?+ -]/g, " ").replace(/\s+/g, " ").trim();

export function createMusic(env) {
  const { canvas, GAL, DATA, info, esc } = env, $ = id => document.getElementById(id), ctx = canvas.getContext("2d");
  const byName = new Map(DATA.games.map(g => [g.name, g])), t0 = new Date(GAL.start).getTime(), tz = new Date().getTimezoneOffset() * 6e4;
  const M = { pos: 0, playing: false, speed: 1, beats: [], sparks: [], hit: new Float32Array(LANES).fill(-9), hitCol: new Array(LANES).fill(INK), flash: -9, clock: 0, spin: 0 };

  /* the score: days with trophies become rows, long silences become one or two empty rows */
  const days = []; let cur = null;
  for (const r of GAL.t) { const ms = t0 + r[0] * 36e5, di = Math.floor((ms - tz) / DAY);
    if (!cur || cur.di !== di) { cur = { type: "day", di, ms, notes: [], games: {} }; days.push(cur); }
    const rare = r[2] / 10, lane = rare > 0 ? Math.max(0, Math.min(LANES - 1, Math.round((LANES - 1) * (1 - Math.sqrt(rare / 100))))) : 4 + hash(r[0]) % 5;
    cur.notes.push({ lane, grade: r[1], name: r[4], gi: r[3] }); cur.games[r[3]] = (cur.games[r[3]] || 0) + 1; }
  let prev = null, seen = new Set(), count = 0, lastGame = -1;
  for (const d of days) {
    d.game = +Object.entries(d.games).sort((a, b) => b[1] - a[1])[0][0]; d.gname = GAL.games[d.game] || "?";
    const date = new Date(d.ms), gap = prev ? d.di - prev.di - 1 : 0;
    for (let k = gap >= 21 ? 2 : gap >= 4 ? 1 : 0; k > 0; k--) M.beats.push({ type: "rest", ms: d.ms, count });
    if (!prev || new Date(prev.ms).getFullYear() !== date.getFullYear()) M.beats.push({ type: "year", ms: d.ms, y: date.getFullYear(), count });
    if (!seen.has(d.game)) { seen.add(d.game); M.beats.push({ type: "title", ms: d.ms, text: plain(d.gname), game: d.game, gname: d.gname, count }); }
    d.month = !prev || new Date(prev.ms).getMonth() !== date.getMonth() ? date.getMonth() : -1;
    d.change = d.game !== lastGame; lastGame = d.game;
    const lanes = new Map(); for (const n of d.notes) { const o = lanes.get(n.lane); if (!o || n.grade > o.grade) lanes.set(n.lane, n); }       // one hole per lane, the best grade wins
    d.holes = [...lanes.values()].sort((a, b) => a.lane - b.lane); d.sound = [...d.holes].sort((a, b) => b.grade - a.grade || b.lane - a.lane).slice(0, 4).sort((a, b) => a.lane - b.lane);
    count += d.notes.length; d.count = count; M.beats.push(d); prev = d;
  }
  const N = M.beats.length; M.total = N; M.trophies = count;
  M.legend = `<span>One row = one day with trophies</span><span>left = common, right = rare (higher notes)</span>` + GCOL.map((c, i) => `<span><i style="background:${c}"></i>${GNAME[i]}</span>`).join("");

  /* sound: a small music box made of sine waves, tuned to a pentatonic scale so it can't hit a wrong note */
  let ac = null, out = null;
  function audio() {
    if (!ac) { const C = window.AudioContext || window.webkitAudioContext; if (!C) return null;
      ac = new C(); out = ac.createGain(); out.gain.value = .55; out.connect(ac.destination);
      const d = ac.createDelay(); d.delayTime.value = .24; const fb = ac.createGain(); fb.gain.value = .25; const wet = ac.createGain(); wet.gain.value = .22; out.connect(d); d.connect(fb); fb.connect(d); d.connect(wet); wet.connect(ac.destination); }
    if (ac.state === "suspended") ac.resume();
    return ac;
  }
  function note(freq, delay, vol, dur) {
    if (!ac || ac.state !== "running") return; const when = ac.currentTime + .02 + delay;
    const o = ac.createOscillator(), o2 = ac.createOscillator(), g = ac.createGain(), g2 = ac.createGain();
    o.frequency.value = freq; o2.frequency.value = freq * 4.02; g2.gain.value = .16;
    g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(vol, when + .005); g.gain.exponentialRampToValueAtTime(.0006, when + dur);
    o.connect(g); o2.connect(g2); g2.connect(g); g.connect(out); o.start(when); o2.start(when); o.stop(when + dur + .05); o2.stop(when + dur + .05);
  }
  const laneFreq = l => 261.63 * Math.pow(2, (SEMI[l % 5] + 12 * Math.floor(l / 5)) / 12);

  /* layout, in "big pixels" */
  let W = 195, Hh = 300, S = 2, sx = 40, topY = 60, playY = 220;
  function resize() {
    S = Math.max(2, Math.min(3, Math.round(Math.min(innerWidth, 560) / 195))); W = Math.ceil(innerWidth / S); Hh = Math.ceil(innerHeight / S);
    canvas.width = W; canvas.height = Hh;
    sx = Math.round((W - SW) / 2) + 5; topY = Math.round(document.querySelector("header").getBoundingClientRect().bottom / S) + 2;
    playY = Math.round(document.querySelector("footer").getBoundingClientRect().top / S) - CASE - 5; draw();
  }
  const px = (x, y, w = 1, h = 1) => ctx.fillRect(Math.round(x), Math.round(y), w, h);
  function text(s, x, y) { for (const ch of s) { const g = FONT[ch]; if (g) for (let i = 0; i < 15; i++) if (g[i] === "1") px(x + i % 3, y + (i / 3 | 0)); x += 4; } }
  function line(x0, y0, x1, y1) { x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1); const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx2 = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let e = dx + dy;
    for (;;) { px(x0, y0); if (x0 === x1 && y0 === y1) break; const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx2; } if (e2 <= dx) { e += dx; y0 += sy; } } }
  function circle(cx, cy, r) { let x = r, y = 0, e = 1 - r; while (x >= y) { for (const [a, b] of [[x, y], [y, x], [-x, y], [-y, x], [x, -y], [y, -x], [-x, -y], [-y, -x]]) px(cx + a, cy + b); y++; if (e < 0) e += 2 * y + 1; else { x--; e += 2 * (y - x) + 1; } } }
  const ring = (x, y, r) => { px(x - r + 1, y - r, 2 * r - 1, 1); px(x - r + 1, y + r, 2 * r - 1, 1); px(x - r, y - r + 1, 1, 2 * r - 1); px(x + r, y - r + 1, 1, 2 * r - 1); };   // a tiny round hole: a square outline without its corners
  const laneX = l => sx + l * LW + LW / 2;
  const alpha = a => ctx.globalAlpha = a;

  function draw() {
    const pos = M.pos, now = M.clock;
    alpha(1); ctx.fillStyle = BG; ctx.fillRect(0, 0, W, Hh);
    const scroll = Math.round(pos * RH), right = sx + SW;
    /* the paper strip */
    ctx.fillStyle = INK; alpha(.035); px(sx, topY, SW, playY - topY);
    alpha(.5); px(sx - 1, topY, 1, playY - topY); px(right, topY, 1, playY - topY);
    alpha(.28); for (let y = playY - 3 + (scroll % 6); y > topY; y -= 6) { px(sx - 5, y, 2, 2); px(right + 3, y, 2, 2); }                  // sprocket holes move with the paper
    alpha(.09); for (let l = 0; l < LANES; l++) for (let y = playY - 2 + (scroll % 4); y > topY; y -= 4) px(laneX(l), y);
    const first = Math.max(0, Math.floor(pos) - 1), last = Math.min(N - 1, Math.ceil(pos + (playY - topY) / RH));
    for (let b = first; b <= last; b++) { const o = M.beats[b], y = playY - Math.round((b - pos) * RH) - RH / 2; if (y < topY + 3 || y > playY) continue;
      const fade = Math.min(1, (y - topY) / 22);
      if (o.type === "year") { ctx.fillStyle = INK; alpha(.5 * fade); for (let x = sx + 2; x < right - 1; x += 4) px(x, y, 2, 1); alpha(.95 * fade); text(String(o.y), sx - 24, y - 2); }
      else if (o.type === "title") { ctx.fillStyle = INK; alpha(.6 * fade); text(o.text.slice(0, Math.floor((SW - 8) / 4)), sx + 4, y - 2); px(sx - 9, y, 3, 1); }
      else if (o.type === "day") {
        if (o.month >= 0) { ctx.fillStyle = INK; alpha(.4 * fade); text(MONTH[o.month], sx - 20, y - 2); }
        for (const h of o.holes) { ctx.fillStyle = GCOL[h.grade]; alpha((h.grade ? 1 : .8) * fade); const x = laneX(h.lane); ring(x, y, 2); if (h.grade >= 2) px(x, y);
          if (h.grade === 3) { px(x - 4, y); px(x + 4, y); px(x, y - 4); px(x, y + 4); } }
      } }
    /* the mechanism */
    const cx0 = sx - 14, cx1 = right + 14, cy0 = playY + 1, cy1 = playY + CASE;
    alpha(1); ctx.fillStyle = BG; px(cx0, cy0, cx1 - cx0, CASE);
    ctx.fillStyle = INK; alpha(.6); px(cx0 + 2, cy0, cx1 - cx0 - 3, 1); px(cx0 + 2, cy1, cx1 - cx0 - 3, 1); px(cx0, cy0 + 2, 1, CASE - 3); px(cx1, cy0 + 2, 1, CASE - 3);
    px(cx0 + 1, cy0 + 1); px(cx1 - 1, cy0 + 1); px(cx0 + 1, cy1 - 1); px(cx1 - 1, cy1 - 1);
    alpha(.25); px(cx0 + 3, cy0 + 3); px(cx1 - 3, cy0 + 3); px(cx0 + 3, cy1 - 3); px(cx1 - 3, cy1 - 3);                                       // screws
    const flash = now - M.flash < .6;
    ctx.fillStyle = flash ? GCOL[3] : INK; alpha(.95); px(sx - 6, playY, SW + 12, 1);                                                          // the play line
    for (let l = 0; l < LANES; l++) { const x = laneX(l), len = 31 - l * 1.35 | 0, age = now - M.hit[l], ringing = age < .45;
      ctx.fillStyle = ringing ? M.hitCol[l] : INK; alpha(ringing ? 1 : .5);
      const wob = ringing ? (Math.floor(age * 30) % 2 ? 1 : -1) * (age < .25 ? 1 : 0) : 0;
      px(x + wob, playY + 3, 1, len - 6); px(x, playY + len - 3, 1, 3); px(x - 1, playY + 3 - (ringing && age < .08 ? 1 : 0), 3, 1);              // a tooth of the comb, with its little pick
      ctx.fillStyle = INK; alpha(.5); px(x - LW / 2, playY + len, LW, 1); if (l < LANES - 1) px(x + LW / 2, playY + (31 - (l + 1) * 1.35 | 0), 1, len - (31 - (l + 1) * 1.35 | 0) + 1); }
    alpha(.5); px(sx, playY + 31, 1, 6); px(sx, playY + 37, SW, 1); px(right - 1, playY + 12, 1, 26);                                            // the comb's base
    // counter and date, under the short teeth
    const bi = Math.min(N - 1, Math.max(0, Math.floor(pos))), o = M.beats[bi], digits = String(o ? o.count : 0).padStart(4, "0"), d = new Date(o ? o.ms : t0);
    for (let i = 0; i < 4; i++) { const x = right - 27 + i * 6; alpha(.35); ring(x + 1, playY + 30, 3); alpha(.95); text(digits[i], x, playY + 28); }
    alpha(.55); text(`${MONTH[d.getMonth()]} ${d.getFullYear()}`, sx + 4, playY + 40);
    // gears on the left, the crank on the right: they turn while it plays
    const a = M.spin;
    alpha(.55); circle(cx0 - 9, playY + 20, 6); circle(cx0 - 9, playY + 35, 3);
    alpha(.8); for (let k = 0; k < 4; k++) { const an = a + k * Math.PI / 2; line(cx0 - 9, playY + 20, cx0 - 9 + Math.cos(an) * 5, playY + 20 + Math.sin(an) * 5); }
    for (let k = 0; k < 8; k++) { const an = a + k * Math.PI / 4 + .3; px(Math.round(cx0 - 9 + Math.cos(an) * 8), Math.round(playY + 20 + Math.sin(an) * 8)); }
    for (let k = 0; k < 3; k++) { const an = -a * 2 + k * 2.094; line(cx0 - 9, playY + 35, cx0 - 9 + Math.cos(an) * 2, playY + 35 + Math.sin(an) * 2); }
    alpha(.55); px(cx1 + 1, playY + 22, 3, 1); circle(cx1 + 8, playY + 22, 5);
    alpha(.95); const hx = cx1 + 8 + Math.cos(a) * 5, hy = playY + 22 + Math.sin(a) * 5; line(cx1 + 8, playY + 22, hx, hy); px(hx - 1, hy - 1, 3, 3);
    // rings where notes were struck
    M.sparks = M.sparks.filter(s => now - s.t < .5);
    for (const s of M.sparks) { const age = (now - s.t) / .5; ctx.fillStyle = s.col; alpha(1 - age); ring(s.x, playY, 2 + Math.round(age * (s.big ? 9 : 5))); }
    alpha(1);
  }

  function strike(b) {                                 // a row reaches the comb
    const o = M.beats[b]; if (!o) return; const sp = BPS * M.speed, dur = Math.max(.5, 1.5 / Math.sqrt(M.speed));
    if (o.type === "title") { note(130.81 * Math.pow(2, SEMI[hash(o.gname) % 5] / 12), 0, .2, 2); const g = byName.get(o.gname);
      info(g?.image ? `<img src="${esc(g.image)}" alt="">` : "♪", o.gname, `First trophy · ${new Date(o.ms).toLocaleDateString(undefined, { month: "long", year: "numeric" })}`); }
    if (o.type !== "day") return;
    if (o.change) note(65.41 * Math.pow(2, SEMI[hash(o.gname) % 5] / 12) * 2, 0, .12, 1.6);
    o.sound.forEach((h, i) => { note(laneFreq(h.lane), i * .22 / sp, [.15, .19, .25, .28][h.grade], dur);
      M.hit[h.lane] = M.clock + i * .22 / sp; M.hitCol[h.lane] = GCOL[h.grade]; M.sparks.push({ x: laneX(h.lane), t: M.clock + i * .22 / sp, col: GCOL[h.grade], big: h.grade === 3 }); });
    if (o.holes.some(h => h.grade === 3)) { M.flash = M.clock; [0, 2, 4, 5, 7, 9, 10, 12, 14].forEach((l, i) => note(laneFreq(l), .1 + i * .07, .14, 1.8)); }
  }
  function button() { const b = $("play"); b.textContent = M.playing ? "❚❚" : "▶"; b.setAttribute("aria-label", M.playing ? "Pause" : "Play"); }
  function play(on) { M.playing = on && M.pos < N; if (M.playing) audio(); button(); }
  function toggle() { if (M.pos >= N - .01) M.pos = 0; play(!M.playing); }
  function frame(dt) {
    M.clock += dt;
    if (M.playing) { const before = Math.floor(M.pos); M.pos = Math.min(N, M.pos + dt * BPS * M.speed); M.spin += dt * 2.2 * M.speed;
      for (let b = before + 1; b <= Math.floor(M.pos) && b - before <= 4; b++) strike(b);
      if (M.pos >= N) play(false);
      $("scrub").value = Math.round(M.pos / N * 1000); }
    const o = M.beats[Math.min(N - 1, Math.floor(M.pos))]; if (o) $("yr").textContent = new Date(o.ms).getFullYear();
    draw();
  }
  function seek(p) { M.pos = Math.max(0, Math.min(N, p * N)); M.sparks = [];
    for (let b = Math.min(N - 1, Math.floor(M.pos)); b >= 0; b--) { const o = M.beats[b]; if (o.type === "day") { const g = byName.get(o.gname);
      info(g?.image ? `<img src="${esc(g.image)}" alt="">` : "♪", o.gname, new Date(o.ms).toLocaleDateString(undefined, { month: "long", year: "numeric" })); break; } }
  }
  function hello() { info("♪", "Your trophies, as a music box", `${M.trophies.toLocaleString()} trophies on one paper strip. Press ▶ to play it (sound on: an iPhone in silent mode stays quiet). Tap a row to read it.`); }
  function enter(gesture) { $("legend").innerHTML = M.legend; hello(); resize(); if (M.pos >= N - .01) M.pos = 0; play(!!gesture); }
  function leave() { play(false); $("play").textContent = "↺"; $("play").setAttribute("aria-label", "Replay"); }
  function pick(ev) {
    const r = canvas.getBoundingClientRect(), y = (ev.clientY - r.top) / S; if (y > playY) { toggle(); return; }
    const b = Math.round(M.pos + (playY - RH / 2 - y) / RH); let best = null;
    for (const k of [0, -1, 1, -2, 2]) { const o = M.beats[b + k]; if (o && o.type === "day") { best = o; break; } }
    if (!best) return; const g = byName.get(best.gname), c = [0, 0, 0, 0]; best.notes.forEach(n => c[n.grade]++);
    const named = best.notes.filter(n => n.name).map(n => n.name).slice(0, 2), others = Object.keys(best.games).length - 1;
    info(g?.image ? `<img src="${esc(g.image)}" alt="">` : "♪", best.gname + (others > 0 ? ` +${others}` : ""),
      `${new Date(best.ms).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })} · ${c.map((n, i) => n ? `${n} ${GNAME[i]}` : "").filter(Boolean).join(", ")}${named.length ? " · " + named.join(", ") : ""}`);
  }
  return Object.assign(M, { frame, enter, leave, pick, seek, toggle, resize, speedTo: s => { M.speed = s; } });
}
