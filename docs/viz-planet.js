/* Your planet: a small living world grown by your games.
   Each kind of game grows its own land (fantasy = dragon woods, sci-fi = neon frontier, horror = haunted marsh...), sized by the hours you spent there,
   and every game you've played is a creature of that land: bigger = more hours, a halo for a platinum, turned to stone if you dropped it.
   The lands and creatures are generic archetypes picked from each game's tags; nothing here is drawn from a game's own art.
   The moon is the backlog. Day and night pass: walkers sleep in the dark, ghosts only come out then, lanterns and crystals light up. */
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

const RP = 10, DAY = 864e5, YEAR = 365.25 * DAY, LIFT = .075;
const hash = (s, salt = 0) => { let h = 2166136261 ^ salt; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995); h ^= h >>> 15; return ((h >>> 0) % 100000) / 100000; };

export const REALMS = [
  { id: "fantasy", name: "Dragon woods", creature: "dragon", a: "A dragon", many: "dragons", col: "#3c8a48", accent: "#e8584a",
    tags: { fantasy: 3, "dark-fantasy": 3, magic: 3, medieval: 3, "souls-like": 3, dragons: 3, jrpg: 2, mythology: 3, demons: 2, "hack-and-slash": 1, "action-rpg": 1 }, genres: { RPG: 2 } },
  { id: "scifi", name: "Neon frontier", creature: "drone", a: "A drone", many: "drones", col: "#4a4f9e", accent: "#5ee6ff",
    tags: { "sci-fi": 3, space: 3, futuristic: 3, aliens: 3, cyberpunk: 3, robots: 3, dystopian: 2, superhero: 1 } },
  { id: "horror", name: "Haunted marsh", creature: "ghost", a: "A ghost", many: "ghosts", col: "#5a5568", accent: "#dfeaff",
    tags: { horror: 3, "survival-horror": 4, zombies: 3, gore: 1, dark: 1, supernatural: 2, surreal: 1 } },
  { id: "waste", name: "The wasteland", creature: "beetle", a: "A scrap beetle", many: "scrap beetles", col: "#b68d52", accent: "#e8853a",
    tags: { "post-apocalyptic": 4, war: 3, military: 3, fps: 2, "third-person-shooter": 2, survival: 1, tactical: 1 }, genres: { Shooter: 1 } },
  { id: "old", name: "Old world", creature: "eagle", a: "An eagle", many: "eagles", col: "#9aa857", accent: "#f1e3c0",
    tags: { historical: 4, assassin: 4, stealth: 2, parkour: 2, crime: 2, america: 1, western: 3, "open-world": 1 } },
  { id: "arena", name: "The arena", creature: "hare", a: "A hare", many: "hares", col: "#58b65a", accent: "#ffffff",
    tags: { soccer: 5, football: 5, sports: 4, racing: 4, competitive: 2, "beat-em-up": 2, fighting: 3 }, genres: { Sports: 5, Racing: 5, Fighting: 3 } },
  { id: "wonder", name: "Wonderland", creature: "hopper", a: "A hopper", many: "hoppers", col: "#d98fb6", accent: "#ffd84d",
    tags: { cute: 3, colorful: 2, "family-friendly": 3, "3d-platformer": 3, "side-scroller": 2, cartoony: 3, comedy: 2, funny: 2, "hand-drawn": 2, relaxing: 2, music: 2, "pixel-graphics": 1 },
    genres: { Platformer: 3, Puzzle: 2, Family: 3, Casual: 2, Arcade: 2 } },
  { id: "story", name: "Story coast", creature: "stag", a: "A stag", many: "stags", col: "#c99a4a", accent: "#b9703a",
    tags: { mystery: 2, detective: 3, "walking-simulator": 3, "point-click": 3, drama: 2, "choices-matter": 2, "visual-novel": 3, investigation: 2, "story-rich": 1, cinematic: 1 } },
];
export function realmOf(g) {                         // which land a game belongs to, from its tags and genres
  const tags = (g.tags || []).map(t => Array.isArray(t) ? t[0] : String(t).toLowerCase()), genres = g.genres || [];
  let best = 7, top = 0;
  REALMS.forEach((r, i) => { let s = 0; tags.forEach(t => s += r.tags[t] || 0); genres.forEach(x => s += r.genres?.[x] || 0); if (s > top) { top = s; best = i; } });
  return best;
}

/* ---------- terrain ---------- */
const WAVES = Array.from({ length: 8 }, (_, i) => { const a = hash("w", i) * 6.283, b = Math.acos(2 * hash("v", i) - 1), f = 1.1 + i * .55;
  return { x: Math.sin(b) * Math.cos(a) * f, y: Math.cos(b) * f, z: Math.sin(b) * Math.sin(a) * f, p: hash("p", i) * 6.283, a: 1 / (1 + i * .55) }; });
const WSUM = WAVES.reduce((n, w) => n + w.a, 0);
const height = n => { let h = 0; for (const w of WAVES) h += w.a * Math.sin(n.x * w.x + n.y * w.y + n.z * w.z + w.p); return h / WSUM * 2.2; };
let SEA = 0;
const radiusAt = n => RP * (1 + LIFT * Math.max(0, height(n) - SEA));

/* ---------- little low-poly models: every part has a colour, a glow, a "part" number (wings, legs) and whether it takes the creature's own colour ---------- */
function part(geo, color, o = {}) {
  const g = geo.index ? geo.toNonIndexed() : geo.clone(); g.deleteAttribute("uv");
  g.applyMatrix4(new THREE.Matrix4().compose(new THREE.Vector3(...(o.p || [0, 0, 0])), new THREE.Quaternion().setFromEuler(new THREE.Euler(...(o.r || [0, 0, 0]))), new THREE.Vector3(...(o.s || [1, 1, 1]))));
  g.computeVertexNormals();
  const n = g.attributes.position.count, c = new THREE.Color(color), col = new Float32Array(n * 3), fx = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { col.set([c.r, c.g, c.b], i * 3); fx.set([o.glow || 0, o.part || 0, o.tint || 0], i * 3); }
  g.setAttribute("aC", new THREE.BufferAttribute(col, 3)); g.setAttribute("aFx", new THREE.BufferAttribute(fx, 3));
  return g;
}
const tri = pts => { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pts.flat(), 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(pts.flat(), 3)); return g; };
const cyl = (a, b, h, seg = 6) => new THREE.CylinderGeometry(a, b, h, seg), cone = (r, h, seg = 6) => new THREE.ConeGeometry(r, h, seg), box = (x, y, z) => new THREE.BoxGeometry(x, y, z),
  ball = (r, d = 1) => new THREE.IcosahedronGeometry(r, d), dome = r => new THREE.SphereGeometry(r, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2);
const PROPS = {                                       // two "elements" per land: a common one and a rarer one
  fantasy: [() => [part(cyl(.05, .07, .24), "#5b4030", { p: [0, .12, 0] }), part(cone(.3, .5), "#1f6b3a", { p: [0, .45, 0] }), part(cone(.21, .42), "#2a8046", { p: [0, .74, 0] })],
    () => [part(cyl(.15, .18, .62, 7), "#9a968f", { p: [0, .31, 0] }), part(cone(.23, .34, 7), "#b5473c", { p: [0, .79, 0] }), part(box(.07, .1, .04), "#ffd27a", { p: [0, .42, .16], glow: 1 })]],
  scifi: [() => [part(new THREE.OctahedronGeometry(.17), "#62e8ff", { p: [0, .36, 0], s: [1, 2.3, 1], glow: .8 }), part(new THREE.OctahedronGeometry(.1), "#b58cff", { p: [.17, .18, .05], s: [1, 2, 1], r: [0, 0, -.5], glow: .8 })],
    () => [part(cyl(.02, .035, .95, 5), "#aeb6c8", { p: [0, .47, 0] }), part(ball(.065, 0), "#ff5fd2", { p: [0, .98, 0], glow: 1 }), part(cyl(.16, .02, .07, 8), "#d5dbe8", { p: [0, .6, 0] })]],
  horror: [() => [part(cyl(.035, .07, .62, 5), "#3a3038", { p: [0, .31, 0] }), part(cyl(.018, .028, .32, 4), "#3a3038", { p: [.12, .5, 0], r: [0, 0, -.95] }), part(cyl(.018, .028, .28, 4), "#3a3038", { p: [-.1, .42, .03], r: [.2, 0, .9] }), part(cyl(.012, .02, .2, 4), "#3a3038", { p: [.02, .68, .07], r: [.7, 0, .1] })],
    () => [part(box(.2, .26, .06), "#8f93a0", { p: [0, .13, 0] }), part(cyl(.1, .1, .06, 8), "#8f93a0", { p: [0, .26, 0], r: [Math.PI / 2, 0, 0] })]],
  waste: [() => [part(box(.34, .36, .08), "#a39684", { p: [0, .18, 0], r: [0, 0, .06] }), part(box(.08, .56, .3), "#8f8372", { p: [-.17, .28, .13] }), part(box(.16, .1, .14), "#7a6f61", { p: [.12, .05, .16], r: [0, .5, 0] })],
    () => [part(cyl(.07, .07, .52, 6), "#6f8f4a", { p: [0, .26, 0] }), part(cyl(.04, .04, .2, 5), "#6f8f4a", { p: [.14, .34, 0] }), part(cyl(.04, .04, .1, 5), "#6f8f4a", { p: [.09, .25, 0], r: [0, 0, Math.PI / 2] }), part(cyl(.04, .04, .16, 5), "#6f8f4a", { p: [-.13, .27, 0] }), part(cyl(.04, .04, .1, 5), "#6f8f4a", { p: [-.08, .2, 0], r: [0, 0, Math.PI / 2] })]],
  old: [() => [part(cyl(.04, .06, .3), "#6a4a30", { p: [0, .15, 0] }), part(ball(.27, 1), "#6f9440", { p: [0, .5, 0], s: [1, .85, 1] })],
    () => [part(cyl(.1, .1, .05, 8), "#e9e2d0", { p: [0, .025, 0] }), part(cyl(.065, .075, .62, 8), "#f3eddd", { p: [0, .36, 0] }), part(box(.22, .06, .22), "#e9e2d0", { p: [0, .7, 0] })]],
  arena: [() => [part(cyl(.014, .014, .8, 4), "#f2f2f2", { p: [0, .4, 0] }), part(tri([[0, .78, 0], [0, .58, 0], [.3, .68, 0]]), "#ff4d4d", {}), part(tri([[0, .78, 0], [.3, .68, 0], [0, .58, 0]]), "#ff4d4d", {})],
    () => [part(cyl(.02, .02, .4, 4), "#ffffff", { p: [0, .2, -.28] }), part(cyl(.02, .02, .4, 4), "#ffffff", { p: [0, .2, .28] }), part(cyl(.02, .02, .58, 4), "#ffffff", { p: [0, .4, 0], r: [Math.PI / 2, 0, 0] })]],
  wonder: [() => [part(cyl(.06, .085, .3, 7), "#f3e6d0", { p: [0, .15, 0] }), part(dome(.25), "#e2504a", { p: [0, .27, 0], s: [1, .8, 1] }), part(ball(.045, 0), "#ffffff", { p: [.1, .42, .06] }), part(ball(.04, 0), "#ffffff", { p: [-.09, .4, -.1] })],
    () => [part(cyl(.012, .012, .32, 4), "#4f9a4a", { p: [0, .16, 0] }), part(ball(.09, 0), "#ffd84d", { p: [0, .35, 0], glow: .35 }), part(cyl(.14, .14, .015, 6), "#ff9ecb", { p: [0, .33, 0] })]],
  story: [() => [part(cyl(.03, .04, .14), "#5b4030", { p: [0, .07, 0] }), part(cone(.13, .85, 6), "#2f6a5a", { p: [0, .55, 0] })],
    () => [part(cyl(.014, .018, .5, 4), "#3b3440", { p: [0, .25, 0] }), part(box(.1, .12, .1), "#ffd27a", { p: [0, .56, 0], glow: 1 }), part(cone(.1, .07, 4), "#3b3440", { p: [0, .66, 0], r: [0, Math.PI / 4, 0] })]],
};
const wing = (root, back, tip, side, shade) => part(tri(side > 0 ? [[root, 0, 0], [tip[0], tip[1], tip[2]], [back, 0, 0]] : [[root, 0, 0], [back, 0, 0], [tip[0], tip[1], -tip[2]]]), shade, { part: 1, tint: 1 });
const two = f => [f(1), f(-1)];
const CREATURES = {                                   // nose towards +x, feet at y = 0 (flyers are centred)
  dragon: { anim: 0, freq: 7, fly: [1.3, 1.3], speed: 1.5, roam: 1.3, parts: () => [
    part(ball(1, 1), "#ffffff", { s: [.42, .13, .14], tint: 1 }), part(ball(.12, 1), "#ffffff", { p: [.48, .09, 0], s: [1.25, .85, .85], tint: 1 }), part(cone(.05, .16, 4), "#f6e7b0", { p: [.47, .23, 0], r: [0, 0, .5] }),
    part(cone(.085, .5, 5), "#cfcfcf", { p: [-.6, 0, 0], r: [0, 0, Math.PI / 2], tint: 1 }), ...two(s => wing(.2, -.22, [-.08, 0, .7], s, "#b9b9b9")), ...two(s => part(ball(.022, 0), "#111111", { p: [.56, .12, .07 * s] }))] },
  eagle: { anim: 0, freq: 3, fly: [2.3, 1.2], speed: 2, roam: 4, parts: () => [
    part(ball(1, 1), "#6b4a30", { s: [.3, .09, .1] }), part(ball(.085, 1), "#ffffff", { p: [.3, .03, 0], tint: 1 }), part(cone(.03, .1, 4), "#f2b632", { p: [.42, .02, 0], r: [0, 0, -Math.PI / 2] }),
    ...two(s => part(tri(s > 0 ? [[.14, 0, 0], [-.04, 0, .8], [-.16, 0, 0]] : [[.14, 0, 0], [-.16, 0, 0], [-.04, 0, -.8]]), "#7d5a3c", { part: 1 })), part(tri([[-.25, 0, 0], [-.48, 0, .12], [-.48, 0, -.12]]), "#ffffff", { tint: 1 }), part(tri([[-.25, 0, 0], [-.48, 0, -.12], [-.48, 0, .12]]), "#ffffff", { tint: 1 })] },
  drone: { anim: 1, freq: 2, fly: [.75, .3], speed: .9, roam: 1, parts: () => [
    part(ball(1, 1), "#aab2c4", { s: [.4, .08, .4] }), part(ball(.17, 1), "#ffffff", { p: [0, .08, 0], s: [1, .8, 1], tint: 1, glow: .7 }), part(ball(.06, 0), "#ffffff", { p: [0, -.1, 0], tint: 1, glow: 1 }),
    ...[0, 1, 2].map(i => part(ball(.035, 0), "#ffffff", { p: [Math.cos(i * 2.094) * .36, 0, Math.sin(i * 2.094) * .36], tint: 1, glow: 1 }))] },
  ghost: { anim: 2, freq: 3, fly: [.5, .25], speed: .35, roam: .9, parts: () => [
    part(dome(.27), "#ffffff", { p: [0, .08, 0], tint: 1, glow: .55 }), part(new THREE.CylinderGeometry(.27, .31, .4, 9, 2, true), "#ffffff", { p: [0, -.12, 0], tint: 1, glow: .55 }),
    ...two(s => part(ball(.045, 0), "#14121c", { p: [.24, .1, .09 * s] }))] },
  beetle: { anim: 3, freq: 14, speed: .5, roam: .8, parts: () => [
    part(ball(1, 1), "#ffffff", { p: [0, .15, 0], s: [.38, .2, .3], tint: 1 }), part(ball(.12, 1), "#2b2622", { p: [.4, .11, 0] }), part(box(.5, .012, .012), "#2b2622", { p: [0, .345, 0] }),
    ...[-.2, 0, .2].flatMap(x => two(s => part(box(.035, .16, .035), "#2b2622", { p: [x, .07, .29 * s], r: [.5 * s, 0, 0], part: 3 })))] },
  hare: { anim: 4, freq: 6, speed: 1.1, roam: .8, parts: () => [
    part(ball(1, 1), "#ffffff", { p: [0, .24, 0], s: [.3, .2, .18], tint: 1 }), part(ball(.14, 1), "#ffffff", { p: [.28, .42, 0], tint: 1 }), ...two(s => part(box(.045, .3, .03), "#ffffff", { p: [.25, .68, .06 * s], r: [0, 0, .2], tint: 1 })),
    part(ball(.075, 0), "#ffffff", { p: [-.31, .3, 0] }), ...two(s => part(ball(.02, 0), "#111111", { p: [.39, .45, .07 * s] })), ...[-.16, .18].flatMap(x => two(s => part(box(.06, .14, .05), "#cfcfcf", { p: [x, .07, .1 * s], tint: 1, part: 3 })))] },
  hopper: { anim: 4, freq: 4, speed: .45, roam: .8, parts: () => [
    part(ball(.3, 2), "#ffffff", { p: [0, .24, 0], s: [1, .8, 1], tint: 1 }), ...two(s => part(ball(.05, 0), "#16131c", { p: [.24, .3, .1 * s] })), ...two(s => part(ball(.02, 0), "#ffffff", { p: [.28, .32, .1 * s] })),
    part(ball(.05, 0), "#ffffff", { p: [0, .5, 0], glow: .5 })] },
  stag: { anim: 3, freq: 7, speed: .45, roam: .8, parts: () => [
    part(ball(1, 1), "#ffffff", { p: [0, .52, 0], s: [.38, .17, .15], tint: 1 }), ...[-.24, .25].flatMap(x => two(s => part(box(.05, .42, .05), "#c8c8c8", { p: [x, .21, .09 * s], tint: 1, part: 3 }))),
    part(box(.1, .3, .09), "#ffffff", { p: [.36, .72, 0], r: [0, 0, -.5], tint: 1 }), part(ball(.1, 1), "#ffffff", { p: [.5, .88, 0], s: [1.4, 1, 1], tint: 1 }), part(ball(.06, 0), "#fff8e8", { p: [-.38, .58, 0] }),
    ...two(s => part(box(.025, .24, .025), "#f3e9cf", { p: [.46, 1.06, .07 * s], r: [.5 * s, 0, .25] })), ...two(s => part(box(.02, .12, .02), "#f3e9cf", { p: [.5, 1.1, .14 * s], r: [-.6 * s, 0, -.5] }))] },
};
const LIGHT = `uniform vec3 uSun;
vec3 lit(vec3 c, vec3 n, vec3 up, float glow) { float day = dot(up, uSun), l = smoothstep(-.22, .3, day), d = max(dot(n, uSun), 0.) * .8 + .28 * max(day, 0.);
  return c * (.1 + 1.05 * d * l) + c * vec3(.2, .25, .46) * (1. - l) + c * glow * (.3 + 1.5 * (1. - l)); }`;

export function createPlanet(env) {
  const { camera, controls, canvas, info, esc, labels, calm, tex } = env, $ = id => document.getElementById(id);
  const scene = new THREE.Scene(); scene.background = new THREE.Color("#04050c");
  const U = { uTime: { value: 0 }, uSun: { value: new THREE.Vector3(1, .25, .4).normalize() } }, grow = new Float32Array(8);
  const P = { scene, follow: null, zoom: 0, back: 0, home: 50, T: env.now, legend: "" };
  const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), v3 = new THREE.Vector3(), m4 = new THREE.Matrix4();

  /* games -> realms */
  const realms = REALMS.map((r, i) => ({ ...r, i, games: [], hours: 0, land: new THREE.Color(r.col), tint: new THREE.Color(r.accent) }));
  const games = env.games.map(f => ({ f, realm: realms[realmOf(f.g)] }));
  games.forEach(c => { c.realm.games.push(c); c.realm.hours += c.f.hours; });
  const total = realms.reduce((n, r) => n + r.hours, 0) || 1;

  /* the ground: an icosphere, one flat colour per triangle */
  const geo = new THREE.IcosahedronGeometry(1, 20), pos = geo.attributes.position, NF = pos.count / 3;
  const cents = [], hs = [];
  for (let f = 0; f < NF; f++) { const c = new THREE.Vector3(); for (let k = 0; k < 3; k++) c.add(v1.fromBufferAttribute(pos, f * 3 + k)); cents.push(c.normalize()); hs.push(height(c)); }
  SEA = [...hs].sort((a, b) => a - b)[Math.floor(NF * .4)];
  const fib = i => { const y = 1 - (i + .5) / 4, r = Math.sqrt(1 - y * y), a = i * 2.39996; return new THREE.Vector3(Math.cos(a) * r, y * .85, Math.sin(a) * r).normalize(); };
  const order = [...realms].sort((a, b) => b.hours - a.hours);
  order.forEach((r, k) => { const want = fib([3, 4, 1, 6, 2, 5, 0, 7][k]); let best = 0, bd = -2;        // biggest lands around the equator; seeds sit on dry ground
    for (let f = 0; f < NF; f++) if (hs[f] > SEA + .1) { const d = cents[f].dot(want); if (d > bd) { bd = d; best = f; } }
    r.seed = cents[best].clone(); r.w = Math.pow(Math.max(.03, r.hours / total), .32); r.faces = []; r.radius = .1; });
  const col = new Float32Array(NF * 9), br = new Float32Array(NF * 6), faceRealm = new Int8Array(NF), sand = new THREE.Color("#d9c98f"), rock = new THREE.Color("#8b8782"), snow = new THREE.Color("#f4f6fa"), c1 = new THREE.Color();
  for (let f = 0; f < NF; f++) {
    const c = cents[f], h = hs[f] - SEA; let ri = -1;
    if (h > 0) { let bd = 1e9; for (const r of realms) { const d = Math.acos(Math.min(1, c.dot(r.seed))) / r.w; if (d < bd) { bd = d; ri = r.i; } }
      const r = realms[ri], ang = Math.acos(Math.min(1, c.dot(r.seed))); r.faces.push({ f, ang }); r.radius = Math.max(r.radius, ang);
      c1.copy(r.land).offsetHSL((hash(f, 1) - .5) * .03, 0, (hash(f, 2) - .5) * .09 + Math.min(.08, h * .12));
      if (h < .07) c1.lerp(sand, .7); if (h > .75) c1.lerp(rock, Math.min(1, (h - .75) * 4)); if (h > 1.05) c1.lerp(snow, Math.min(1, (h - 1.05) * 5));
    } else c1.setRGB(.07, .3, .55).lerp(new THREE.Color(.16, .55, .75), Math.max(0, 1 + h * 2.2)).offsetHSL(0, 0, (hash(f, 3) - .5) * .03);
    faceRealm[f] = ri;
    for (let k = 0; k < 3; k++) { col.set([c1.r, c1.g, c1.b], (f * 3 + k) * 3); br[(f * 3 + k) * 2] = ri; }
  }
  realms.forEach(r => { r.faces.sort((a, b) => a.ang - b.ang); r.faces.forEach(o => { const rank = o.ang / r.radius; o.rank = rank; for (let k = 0; k < 3; k++) br[(o.f * 3 + k) * 2 + 1] = rank; }); });
  for (let i = 0; i < pos.count; i++) { v1.fromBufferAttribute(pos, i).normalize(); v1.multiplyScalar(radiusAt(v1)); pos.setXYZ(i, v1.x, v1.y, v1.z); }
  geo.computeVertexNormals(); geo.setAttribute("aC", new THREE.BufferAttribute(col, 3)); geo.setAttribute("aBR", new THREE.BufferAttribute(br, 2));
  const ground = new THREE.Mesh(geo, new THREE.ShaderMaterial({ uniforms: { ...U, uGrow: { value: grow } },
    vertexShader: `attribute vec3 aC; attribute vec2 aBR; uniform float uGrow[8]; uniform float uTime; varying vec3 vC, vN, vUp; varying float vW;
      void main() { float alive = aBR.x < -.5 ? 1. : smoothstep(0., .08, uGrow[int(aBR.x + .5)] - aBR.y * .92);
        vec3 bare = vec3(.3, .27, .26) * (.6 + .9 * dot(aC, vec3(.33))); vC = mix(bare, aC, alive); vW = aBR.x < -.5 ? 1. : 0.;
        vN = normalize(mat3(modelMatrix) * normal); vUp = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
    fragmentShader: LIGHT + `uniform float uTime; varying vec3 vC, vN, vUp; varying float vW;
      void main() { vec3 c = vC; if (vW > .5) c *= .93 + .09 * sin(vUp.x * 40. + uTime * 1.3) * sin(vUp.y * 37. - uTime) * sin(vUp.z * 43. + uTime * .7);
        gl_FragColor = vec4(lit(c, normalize(vN), vUp, 0.), 1.); }` }));
  scene.add(ground);

  /* instanced things (props, clouds, creatures) share one shader */
  const material = (anim, freq, uG) => new THREE.ShaderMaterial({ side: THREE.DoubleSide, uniforms: { ...U, uAnim: { value: anim }, uFreq: { value: freq }, uG: uG || { value: 1 } },
    vertexShader: `attribute vec3 aC, aFx, aCol; attribute vec4 aInst; attribute float aRank; uniform float uTime, uFreq, uG; uniform int uAnim; varying vec3 vC, vN, vUp; varying float vGlow;
      void main() { vec3 p = position; float ph = aInst.x, mv = aInst.y, t = uTime;
        if (uAnim == 0) { if (aFx.y > .5 && aFx.y < 1.5) { float a = sin(t * uFreq + ph) * .7 + .12; p.y += abs(p.z) * sin(a); p.z *= cos(a); } }
        else if (uAnim == 1) p.y += sin(t * 2. + ph) * .06;
        else if (uAnim == 2) { p.x += sin(t * 3. + p.y * 9. + ph) * .06 * smoothstep(.1, -.3, p.y); p.y += sin(t * 1.5 + ph) * .06; }
        else if (uAnim == 3) { if (aFx.y > 2.5) p.x += sin(t * uFreq + ph + p.z * 9. + p.x * 6.) * .075 * mv * smoothstep(.42, 0., p.y); p.y += abs(sin(t * uFreq * .5 + ph)) * .02 * mv; }
        else if (uAnim == 4) { float s = sin(t * uFreq + ph); p.y = p.y * (1. + .2 * s * mv) + max(0., s) * mv * .5; p.xz *= 1. - .1 * s * mv; }
        else p *= smoothstep(0., .1, uG - aRank * .92);
        vec4 w = modelMatrix * instanceMatrix * vec4(p, 1.);
        vC = mix(aC, aC * aCol, aFx.z); vC = mix(vC, vec3(dot(vC, vec3(.33))) * .62 + .08, aInst.z); vGlow = aFx.x * (1. - aInst.z) + aInst.w * .22;
        vN = normalize(mat3(modelMatrix) * mat3(instanceMatrix) * normal); vUp = normalize(w.xyz); gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: LIGHT + `varying vec3 vC, vN, vUp; varying float vGlow; void main() { vec3 n = normalize(vN); if (!gl_FrontFacing) n = -n; gl_FragColor = vec4(lit(vC, mix(n, vUp, .35), vUp, vGlow), 1.); }` });
  const instanced = (parts, n, mat) => { const g = mergeGeometries(parts);
    g.setAttribute("aCol", new THREE.InstancedBufferAttribute(new Float32Array(n * 3).fill(1), 3)); g.setAttribute("aInst", new THREE.InstancedBufferAttribute(new Float32Array(n * 4), 4)); g.setAttribute("aRank", new THREE.InstancedBufferAttribute(new Float32Array(n), 1));
    const m = new THREE.InstancedMesh(g, mat, n); m.frustumCulled = false; return m; };
  const place = (mesh, i, n, yaw, scale, lift = 0) => { v1.copy(n).multiplyScalar(radiusAt(n) + lift); v2.set(0, 1, 0).cross(n); if (v2.lengthSq() < 1e-4) v2.set(1, 0, 0); v2.normalize().applyAxisAngle(n, yaw); v3.crossVectors(v2, n);
    m4.makeBasis(v2, n, v3).scale(typeof scale === "number" ? v2.set(scale, scale, scale) : scale).setPosition(v1); mesh.setMatrixAt(i, m4); };

  /* elements: trees, towers, crystals, ruins... each land grows its own as you play there */
  realms.forEach(r => {
    r.uG = { value: 0 };
    const spots = r.faces.filter(o => hs[o.f] - SEA > .06 && hs[o.f] - SEA < .95), want = Math.min(Math.floor(spots.length * .3), Math.max(8, Math.round(r.hours / 4)));
    const pick = spots.map(o => [hash(o.f, 9), o]).sort((a, b) => a[0] - b[0]).slice(0, want).map(e => e[1]);
    [pick.filter((_, i) => i % 5 !== 0), pick.filter((_, i) => i % 5 === 0)].forEach((list, k) => { if (!list.length) return;
      const mesh = instanced(PROPS[r.id][k](), list.length, material(9, 0, r.uG));
      list.forEach((o, i) => { place(mesh, i, cents[o.f], hash(o.f, 4) * 6.283, .75 + hash(o.f, 5) * .7); mesh.geometry.attributes.aRank.setX(i, Math.min(1, o.rank + .04)); });
      scene.add(mesh); });
  });

  /* creatures: one per game */
  const cLen = h => .7 + .15 * Math.sqrt(h);
  realms.forEach(r => { const def = CREATURES[r.creature]; r.def = def; if (!r.games.length) return;
    r.mesh = instanced(def.parts(), r.games.length, material(def.anim, def.freq)); r.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage); scene.add(r.mesh);
    r.games.forEach((c, i) => { const f = c.f, name = f.name; c.i = i; c.ph = hash(name, 2) * 6.283;
      const near = r.faces.filter(o => o.rank < .55 && hs[o.f] - SEA > .05), spot = (near.length ? near : r.faces)[Math.floor(hash(name, 5) * (near.length || r.faces.length))];
      c.n = (spot ? cents[spot.f] : r.seed).clone(); c.t = v1.set(hash(name, 6) - .5, hash(name, 7) - .5, hash(name, 8) - .5).cross(c.n).normalize().clone();
      c.alt = def.fly ? def.fly[0] + hash(name, 3) * def.fly[1] : 0; c.speed = def.speed * (.75 + hash(name, 4) * .5); c.roam = Math.min(3.2, r.radius * def.roam); c.side = hash(name, 10) > .5 ? 1 : -1;
      c.s = 0; c.target = 0; c.p = new THREE.Vector3(); c.vis = 1;
      const tint = r.tint.clone().offsetHSL((hash(name, 11) - .5) * .12, 0, (hash(name, 12) - .5) * .16); r.mesh.geometry.attributes.aCol.setXYZ(i, tint.r, tint.g, tint.b);
      r.mesh.geometry.attributes.aInst.setXYZW(i, c.ph, 1, 0, 0); });
  });
  const halo = (() => { const n = games.length, g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(n * 3), 3)); g.setAttribute("aSize", new THREE.BufferAttribute(new Float32Array(n), 1)); g.setAttribute("aCol", new THREE.BufferAttribute(new Float32Array(n * 4), 4));
    const p = new THREE.Points(g, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uMap: { value: tex }, uScale: P.uScale = { value: 800 } },
      vertexShader: `attribute float aSize; attribute vec4 aCol; uniform float uScale; varying vec4 vCol; void main() { vec4 mv = modelViewMatrix * vec4(position, 1.); gl_Position = projectionMatrix * mv; gl_PointSize = aSize * uScale / max(.1, -mv.z); vCol = aCol; }`,
      fragmentShader: `uniform sampler2D uMap; varying vec4 vCol; void main() { gl_FragColor = vec4(vCol.rgb, vCol.a * texture2D(uMap, gl_PointCoord).a); }` }));
    p.frustumCulled = false; scene.add(p); return p; })();

  /* sky: air, clouds, stars and the backlog moon */
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(RP * 1.2, 48, 32), new THREE.ShaderMaterial({ side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { ...U },
    vertexShader: `varying vec3 vN, vW; void main() { vN = normalize(normalMatrix * normal); vW = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
    fragmentShader: `uniform vec3 uSun; varying vec3 vN, vW; void main() { float i = pow(max(0., .72 - dot(vN, vec3(0., 0., 1.))), 2.6); float day = smoothstep(-.5, .5, dot(vW, uSun)); gl_FragColor = vec4(mix(vec3(.12, .16, .5), vec3(.35, .65, 1.), day), 1.) * i * (.35 + .85 * day); }` })));
  const clouds = new THREE.Group(); { const n = 16, mesh = instanced([part(ball(1, 1), "#ffffff", {})], n * 3, material(1, 0));
    for (let i = 0; i < n; i++) { const c = new THREE.Vector3(hash("c", i) - .5, (hash("d", i) - .5) * .8, hash("e", i) - .5).normalize();
      for (let k = 0; k < 3; k++) { v3.copy(c).applyAxisAngle(v1.set(0, 1, 0), (k - 1) * .075).normalize(); const s = .55 + hash(i, k) * .5; place(mesh, i * 3 + k, v3.clone(), hash(i, 20) * 6, new THREE.Vector3(s * 1.5, s * .38, s), 2 + hash("f", i) * .5 + (k === 1 ? .12 : 0)); } }
    clouds.add(mesh); scene.add(clouds); }
  { const n = 900, a = new Float32Array(n * 3); for (let i = 0; i < n; i++) { v1.set(hash(i, 30) - .5, hash(i, 31) - .5, hash(i, 32) - .5).normalize().multiplyScalar(700); a.set([v1.x, v1.y, v1.z], i * 3); }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(a, 3)); scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0xcfd8ff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: .75 }))); }
  const moonGeo = new THREE.IcosahedronGeometry(1, 3); { const p = moonGeo.attributes.position; for (let i = 0; i < p.count; i++) { v1.fromBufferAttribute(p, i).normalize(); const d = 1 + .07 * Math.sin(v1.x * 5 + 1) * Math.sin(v1.y * 6) * Math.sin(v1.z * 4 + 2) - .05 * Math.max(0, Math.sin(v1.x * 9) * Math.sin(v1.z * 8)); p.setXYZ(i, v1.x * d, v1.y * d, v1.z * d); } moonGeo.computeVertexNormals(); }
  const moon = new THREE.Mesh(moonGeo, new THREE.ShaderMaterial({ uniforms: { ...U }, vertexShader: `varying vec3 vN; varying float vS; void main() { vN = normalize(mat3(modelMatrix) * normal); vS = .8 + .25 * sin(position.x * 7.) * sin(position.y * 9.); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
    fragmentShader: `uniform vec3 uSun; varying vec3 vN; varying float vS; void main() { gl_FragColor = vec4(vec3(.72, .72, .78) * vS * (.07 + max(0., dot(normalize(vN), uSun))), 1.); }` }));
  scene.add(moon);

  /* time */
  const hoursAt = (f, T) => { if (T < f.birth) return 0; if (!f.hy) return f.hours * Math.min(1, (T - f.birth) / Math.max(DAY, f.last - f.birth));
    const Y = new Date(T).getFullYear(), y0 = new Date(Y, 0, 1).getTime(), y1 = new Date(Y + 1, 0, 1).getTime(); let h = 0;
    for (const [y, v] of f.hy) { if (y < Y) h += v; else if (y === Y) { const a = Math.max(y0, f.birth), b = Math.max(a + DAY, Math.min(y1, f.last, env.now)); h += v * Math.min(1, Math.max(0, (T - a) / (b - a))); } }
    return h; };
  function time(p, instant) {                         // the planet at a moment between your first game (0) and today (1)
    const T = P.T = env.t0 + p * (env.now - env.t0);
    realms.forEach(r => { let h = 0; for (const c of r.games) { const f = c.f, hh = hoursAt(f, T); h += hh; c.born = T >= f.birth; c.target = c.born ? cLen(Math.max(.05, hh)) : 0;
        c.plat = !!(f.platAt && T >= f.platAt); c.stone = f.dropped && T > f.last + 60 * DAY; c.active = c.born && T >= f.last && T - f.last < 45 * DAY;
        if (instant) c.s = c.target; }
      r.now = h; grow[r.i] = r.hours ? Math.sqrt(h / r.hours) : 0; r.uG.value = grow[r.i]; });
    P.backlog = env.backlog.filter(o => (o.acquired ?? 0) <= T).length; P.moonTarget = P.backlog ? .5 + 1.1 * Math.sqrt(P.backlog / Math.max(1, env.backlog.length)) : 0; if (instant) moon.scale.setScalar(Math.max(.001, P.moonTarget));
    $("yr").textContent = new Date(T).getFullYear();
  }
  function frame(dt) {
    const t = U.uTime.value += dt, sun = U.uSun.value;
    if (!calm) sun.set(Math.cos(t * .07), .28, Math.sin(t * .07)).normalize();                     // a day lasts about a minute and a half
    clouds.rotation.y = t * .012; clouds.rotation.x = Math.sin(t * .004) * .2;
    const ma = t * .06 + 1; moon.position.set(Math.cos(ma) * 17.5, Math.sin(ma * .7) * 5 + 4, Math.sin(ma) * 17.5); moon.rotation.y = t * .1;
    moon.scale.setScalar(Math.max(.001, moon.scale.x + (P.moonTarget - moon.scale.x) * Math.min(1, dt * 3)));
    const hp = halo.geometry.attributes; let hi = 0;
    for (const r of realms) { if (!r.mesh) continue; const def = r.def, inst = r.mesh.geometry.attributes.aInst;
      for (const c of r.games) {
        c.s += (c.target - c.s) * Math.min(1, dt * 2.5);
        const day = c.n.dot(sun), asleep = !def.fly && day < -.12, moving = c.born && !c.stone && !asleep;
        if (r.creature === "ghost") c.vis += ((day < .05 || c.stone ? 1 : 0) - c.vis) * Math.min(1, dt * 1.5);          // ghosts fade in at dusk
        if (moving) {
          c.t.applyAxisAngle(c.n, (Math.sin(t * .31 + c.ph * 7) * .7 + Math.sin(t * .13 + c.ph) * .4) * dt);
          if (c.roam < 3 && c.n.angleTo(r.seed) > c.roam) { v1.copy(r.seed).addScaledVector(c.n, -c.n.dot(r.seed)).normalize(); c.t.lerp(v1, Math.min(1, dt * 1.4)).normalize(); }
          v2.copy(c.n).addScaledVector(c.t, c.speed * (c.active ? 1.3 : 1) * dt / RP).normalize();
          if (!def.fly && height(v2) < SEA + .04) c.t.applyAxisAngle(c.n, dt * 2.6 * c.side);                              // walkers turn away from the sea
          else { c.n.copy(v2); c.t.addScaledVector(c.n, -c.t.dot(c.n)).normalize(); }
        }
        const rad = (def.fly ? RP * (1 + LIFT * .5) + c.alt * (c.stone ? 0 : 1) : radiusAt(c.n)) + (c.stone && def.fly ? radiusAt(c.n) - RP * (1 + LIFT * .5) : 0);
        c.p.copy(c.n).multiplyScalar(rad); v3.crossVectors(c.t, c.n); const s = c.s * c.vis;
        m4.makeBasis(c.t, c.n, v3).scale(v1.set(s, s, s)).setPosition(c.p); r.mesh.setMatrixAt(c.i, m4);
        inst.setXYZW(c.i, c.ph, moving ? 1 : 0, c.stone ? 1 : 0, c.plat ? 1 : 0);
        const on = c.born && s > .05 && (c.plat || c.active);
        { const up = s * (def.fly ? .35 : 1.05); hp.position.setXYZ(hi, c.p.x + c.n.x * up, c.p.y + c.n.y * up, c.p.z + c.n.z * up); } hp.aSize.setX(hi, on ? (c.plat ? s * .9 + .25 : s * 1.1 + .3 * (1 + Math.sin(t * 4 + c.ph))) : 0);
        if (c.plat) hp.aCol.setXYZW(hi, 1, .8, .3, .75); else hp.aCol.setXYZW(hi, .8, .95, 1, .3); hi++;
      }
      r.mesh.instanceMatrix.needsUpdate = inst.needsUpdate = true; }
    hp.position.needsUpdate = hp.aSize.needsUpdate = hp.aCol.needsUpdate = true;
    // camera: face the creature you tapped, drift back when you let go
    const f = P.follow, k = Math.min(1, dt * 2.5);
    if (f) {                                                                                         // a low, slanted close-up: look at the creature from a little above the ground
      v1.copy(camera.position).sub(f.p); v1.addScaledVector(f.n, -v1.dot(f.n)); if (v1.lengthSq() < 1e-4) v1.copy(f.t); v1.normalize();
      v3.copy(f.p).addScaledVector(f.n, 2.2 + f.s * 1.6).addScaledVector(v1, 5 + f.s * 3.2);
      controls.target.lerp(f.p, k); camera.position.lerp(v3, k * .8); camera.up.lerp(f.n, k).normalize();
    } else if (P.back > 0) { controls.target.lerp(v1.set(0, 0, 0), k); v3.copy(camera.position).setLength(P.home); camera.position.lerp(v3, k); camera.up.lerp(v1.set(0, 1, 0), k).normalize();
      if ((P.back -= dt) <= 0) { controls.target.set(0, 0, 0); camera.up.set(0, 1, 0); } }
    // labels: the lands facing you
    const list = [], cd = v2.copy(camera.position).normalize();
    if (f) list.push({ text: esc(f.f.name), p: f.p.clone().addScaledVector(f.n, f.s + .5), big: true });
    else { realms.forEach(r => { if (r.games.length && grow[r.i] > .05 && r.seed.dot(cd) > .45) list.push({ text: esc(r.name), p: r.seed.clone().multiplyScalar(RP + 2.2), big: true }); });
      if (P.backlog && moon.position.dot(cd) > -4) list.push({ text: `Backlog moon · ${P.backlog}`, p: moon.position.clone().add(v1.set(0, moon.scale.x + .9, 0)) }); }
    labels(list);
  }
  function homeDist() {
    const top = document.querySelector("header").getBoundingClientRect().bottom, bot = document.querySelector("footer").getBoundingClientRect().top;
    const free = Math.max(.4, (bot - top) / innerHeight), v = THREE.MathUtils.degToRad(camera.fov) / 2, hx = Math.atan(Math.tan(v) * camera.aspect);
    camera.setViewOffset(innerWidth, innerHeight, 0, Math.round((innerHeight - bot - top) / 2), innerWidth, innerHeight);
    P.uScale.value = env.renderer.domElement.height / (2 * Math.tan(v));
    return P.home = Math.max((RP + 3.4) / (Math.tan(v) * free), (RP + 4.2) / Math.tan(hx));
  }
  const hello = () => info("🌍", "Your games grew this planet", "Each kind of game grows a land, each game is a creature living on it (bigger = more hours). Platinums wear a halo, dropped games turn to stone, the moon is your backlog. Tap anything.");
  function enter() {
    P.follow = null; P.back = 0; camera.up.set(0, 1, 0); controls.minDistance = RP + 4; controls.maxDistance = 140; controls.minPolarAngle = .25; controls.maxPolarAngle = Math.PI - .25; controls.autoRotate = !calm; controls.autoRotateSpeed = .5;
    const d = homeDist(); controls.target.set(0, 0, 0); v1.copy(order[0].seed).setY(order[0].seed.y + .35).normalize(); camera.position.copy(v1).multiplyScalar(d);
    $("legend").innerHTML = P.legend; hello();
  }
  const ray = new THREE.Raycaster();
  function pick(ev) {
    const r = canvas.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top, cd = v2.copy(camera.position).normalize();
    let best = null, bd = 1e9;
    for (const c of games) { if (!c.born || c.s * c.vis < .15 || c.n.dot(cd) < .12) continue; v1.copy(c.p).addScaledVector(c.n, c.s * .3).project(camera);
      const d = Math.hypot((v1.x + 1) / 2 * r.width - mx, (1 - v1.y) / 2 * r.height - my), reach = Math.max(24, c.s * .6 * r.height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * camera.position.distanceTo(c.p)));
      if (d < reach && d / reach < bd) { bd = d / reach; best = c; } }
    if (best) { const f = best.f, g = f.g, state = g.platinum ? "Platinum ✦" : f.beaten ? "Finished" : f.dropped ? "Dropped, turned to stone" : best.active ? "Playing now" : "Started";
      P.follow = best; controls.autoRotate = false; controls.minDistance = 3;
      info(g.image ? `<img src="${esc(g.image)}" alt="">` : "🌍", f.name, `${best.realm.a} of ${best.realm.name.replace(/^The /, "the ")} · ${f.guess ? "" : (f.hours >= 10 ? Math.round(f.hours) : f.hours) + " h · "}${state}`); return; }
    if (P.follow) { P.follow = null; P.back = 1.8; controls.autoRotate = !calm; controls.minDistance = RP + 4; hello(); return; }
    ray.setFromCamera(new THREE.Vector2(mx / r.width * 2 - 1, -(my / r.height) * 2 + 1), camera);
    v1.copy(moon.position).sub(ray.ray.origin); const along = v1.dot(ray.ray.direction);
    if (P.backlog && along > 0 && v1.lengthSq() - along * along < Math.pow(moon.scale.x + .8, 2)) { info("🌙", "The backlog moon", `${P.backlog} games you own and haven't started. It grows with every game you add and shrinks when you start one.`); return; }
    const hit = ray.intersectObject(ground)[0];
    if (hit) { const ri = faceRealm[hit.faceIndex];
      if (ri < 0) { info("🌊", "The sea", "Nothing lives here yet."); return; }
      const rl = realms[ri], top = [...rl.games].sort((a, b) => b.f.hours - a.f.hours).filter(c => c.born).slice(0, 2).map(c => c.f.name);
      info("🌍", rl.name, rl.games.length ? `${rl.games.filter(c => c.born).length} ${rl.many} · ${Math.round(rl.now)} h played here${top.length ? " · biggest: " + top.join(", ") : ""}` : "No games here yet."); }
  }
  P.legend = `<span>${realms.filter(r => r.games.length).length} lands · ${games.length} creatures · day and night pass</span>`;
  time(1, true);
  return Object.assign(P, { time, frame, enter, pick, resize: homeDist, realms });
}
