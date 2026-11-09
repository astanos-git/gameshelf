/* Year numbers shared by Review and Wrapped: totals, top games, genres, rarest trophy, persona, Gamer DNA,
   plus the canvas helpers used for share images. Reads the page's globals DATA, FLAGS, RATINGS and SESS. */
const sum = a => a.reduce((x, y) => x + y, 0);
const pick = (map, x) => map[x.name] || (x.aliases || []).map(n => map[n]).find(Boolean);
function statsFor(y) {
  const G = DATA.games, ins = DATA.insights || {};
  const trophies = g => sum(Object.entries(g.months || {}).filter(([m]) => m.startsWith(y)).flatMap(([, t]) => t));
  const plats = g => sum(Object.entries(g.months || {}).filter(([m]) => m.startsWith(y)).map(([, t]) => t[3]));
  const hours = g => (g.hours_by_year || {})[y] || 0;
  const played = G.filter(g => trophies(g) > 0 || hours(g) > 0);
  const started = G.filter(g => [g.first_played, g.first_trophy_at].filter(Boolean).sort()[0]?.startsWith(y));
  const finished = G.filter(g => { const f = pick(FLAGS, g);
    const beatenAt = f && f.flag === "beaten" ? (g.last_activity && g.last_activity < f.at ? g.last_activity : f.at) : null;
    const at = g.platinum_at || (g.status === "completed" ? g.last_trophy : null) || beatenAt;
    return at && String(new Date(at).getFullYear()) === y; });
  const months = Array(12).fill(0);
  for (const g of G) for (const [m, t] of Object.entries(g.months || {})) if (m.startsWith(y)) months[+m.slice(5) - 1] += sum(t);
  const genres = {};
  for (const g of played) for (const gn of g.genres || []) genres[gn] = (genres[gn] || 0) + hours(g);
  const days = Object.entries(ins.days || {}).filter(([d]) => d.startsWith(y)).sort();
  let streak = 0, run = 0, prev = null;
  for (const [d] of days) { const t = Date.parse(d + "T12:00:00Z"); run = prev && t - prev === 864e5 ? run + 1 : 1; streak = Math.max(streak, run); prev = t; }
  const wh = (ins.weekday_hour || {})[y];
  const byDay = wh ? Array.from({ length: 7 }, (_, d) => sum(wh.slice(d * 24, d * 24 + 24))) : null;
  const byHour = wh ? Array.from({ length: 24 }, (_, h) => sum(Array.from({ length: 7 }, (_, d) => wh[d * 24 + h]))) : null;
  const rare = G.flatMap(g => (g.rare || []).filter(r => r.at?.startsWith(y)).map(r => ({ ...r, game: g.name }))).sort((a, b) => a.r - b.r)[0];
  const rated = G.map(g => ({ g, r: pick(RATINGS, g) })).filter(o => o.r && played.includes(o.g)).sort((a, b) => b.r.score - a.r.score)[0];
  return {
    trophies: sum(played.map(trophies)), plats: sum(played.map(plats)), hours: sum(played.map(hours)),
    played, started: started.length, finished,
    byHours: [...played].sort((a, b) => hours(b) - hours(a)), byTrophies: [...played].sort((a, b) => trophies(b) - trophies(a)),
    hoursOf: hours, trophiesOf: trophies, months, genres, days, streak, byDay, byHour, rare, rated,
    platList: ((ins.milestones || []).filter(m => m.kind === "platinum" && m.at.startsWith(y))),
  };
}
function persona(s) {
  if (!s.byHour) return null;
  const total = sum(s.byHour), night = sum(s.byHour.slice(22)) + sum(s.byHour.slice(0, 5)), morning = sum(s.byHour.slice(5, 11));
  const weekend = s.byDay[5] + s.byDay[6];
  if (night / total > .35) return ["Night owl", `${Math.round(100 * night / total)}% of your trophies came after 22:00`];
  if (morning / total > .3) return ["Early bird", `${Math.round(100 * morning / total)}% of your trophies came before 11:00`];
  if (weekend / total > .45) return ["Weekend warrior", `${Math.round(100 * weekend / total)}% of your trophies came on weekends`];
  return ["Steady player", "Your trophies are spread across the week"];
}
function wrap(ctx, text, maxW, maxLines) {
  const words = String(text).split(/\s+/), lines = []; let cur = "";
  for (const w of words) { const t = cur ? cur + " " + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; }
  if (cur) lines.push(cur);
  if (lines.length > maxLines) { lines.length = maxLines; let l = lines[maxLines - 1]; while (ctx.measureText(l + "…").width > maxW && l.length) l = l.slice(0, -1); lines[maxLines - 1] = l + "…"; }
  return lines;
}
const TRAITS = [["story", "Story seeker", "play for the story"], ["explorer", "Explorer", "love open worlds"], ["completionist", "Completionist", "finish what you start"],
  ["hunter", "Trophy hunter", "go for the rare trophies"], ["owl", "Night owl", "play late at night"], ["marathon", "Marathoner", "play long sessions"],
  ["dayone", "Day-one player", "play new releases early"], ["sampler", "Sampler", "try lots of games"], ["indie", "Indie spirit", "love indie games"]];
function dna(y) {
  const G = DATA.games, ins = DATA.insights || {}, all = y === "all", inY = d => d && (all || d.startsWith(y));
  const hrs = g => all ? (g.hours || 0) : (g.hours_by_year || {})[y] || 0;
  const tro = g => sum(Object.entries(g.months || {}).filter(([m]) => all || m.startsWith(y)).flatMap(([, t]) => t));
  const played = G.filter(g => hrs(g) > 0 || tro(g) > 0);
  if (played.length < 3) return null;
  const H = sum(played.map(hrs)) || 1, clamp = v => v == null || isNaN(v) ? null : Math.round(Math.max(0, Math.min(100, v)));
  const tagShare = slugs => sum(played.filter(g => (g.tags || []).some(t => slugs.includes(t[0]))).map(hrs)) / H;
  const finished = played.filter(g => { const f = pick(FLAGS, g); const at = g.platinum_at || (g.status === "completed" ? g.last_trophy : null) || (f?.flag === "beaten" ? f.at : null); return at && (all || inY(at)); });
  const started = G.filter(g => inY([g.first_played, g.first_trophy_at].filter(Boolean).sort()[0]));
  const dayOne = started.filter(g => g.released && ([g.first_played, g.first_trophy_at].filter(Boolean).sort()[0] || "") <= new Date(Date.parse(g.released) + 31 * 864e5).toISOString());
  const wh = (ins.weekday_hour || {})[all ? "all" : y], night = wh ? sum(wh.filter((v, i) => i % 24 >= 22 || i % 24 < 4)) / Math.max(1, sum(wh)) : null;
  const rar = ((ins.rarity || {})[all ? "all" : y] || {}).score;
  return {
    story: clamp(tagShare(["story-rich", "narrative", "choices-matter", "great-soundtrack"]) * 120),
    explorer: clamp(tagShare(["open-world", "exploration"]) * 130),
    completionist: clamp(100 * finished.length / played.length * 1.4),
    hunter: rar == null ? null : clamp(rar * 2),
    owl: night == null ? null : clamp(night * 200),
    marathon: SESS[all ? "all" : y] ? clamp(SESS[all ? "all" : y].long_share * 2.5) : null,
    dayone: started.length >= 3 ? clamp(100 * dayOne.length / started.length * 2.5) : null,
    sampler: clamp(100 * played.filter(g => (g.hours || 0) > 0 && g.hours < 3 && g.status !== "completed").length / played.length * 1.5),
    indie: clamp(sum(played.filter(g => (g.genres || []).includes("Indie")).map(hrs)) / H * 200),
  };
}
const topTraits = d => TRAITS.filter(([k]) => d[k] != null).sort((a, b) => d[b[0]] - d[a[0]]);
async function shareCanvas(canvas, name, title, note) {
  const blob = await new Promise(r => canvas.toBlob(r, "image/png")), file = new File([blob], name, { type: "image/png" });
  try {
    if (navigator.canShare?.({ files: [file] })) await navigator.share({ files: [file], title });
    else { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000); note.textContent = "Image downloaded."; }
  } catch (e) { if (e.name !== "AbortError") note.textContent = "Couldn't share: " + e.message; }
}
