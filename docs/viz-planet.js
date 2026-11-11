/* Your planet: a small living world grown by your games.
   The planet itself is rendered per pixel (procedural terrain, sea, clouds, city lights); the creatures and elements on it stay small low-poly models.
   Each kind of game grows its own land (fantasy = dragon woods, sci-fi = neon frontier, horror = haunted marsh...), sized by the hours you spent there,
   and every game you've played is a creature of that land: bigger = more hours, a halo for a platinum, turned to stone if you dropped it.
   The lands and creatures are generic archetypes picked from each game's tags; nothing here is drawn from a game's own art.
   The moon is the backlog. Day and night pass: walkers sleep in the dark, ghosts only come out then, lanterns and crystals light up. */
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

const RP = 10, DAY = 864e5, YEAR = 365.25 * DAY, LIFT = .05;
const hash = (s, salt = 0) => { let h = 2166136261 ^ salt; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995); h ^= h >>> 15; return ((h >>> 0) % 100000) / 100000; };

export const REALMS = [
  { id: "fantasy", low: "#2a4a20", high: "#58733a", lamp: "#ffc070", name: "Dragon woods", creature: "dragon", a: "A dragon", many: "dragons", col: "#3c8a48", accent: "#e8584a",
    tags: { fantasy: 3, "dark-fantasy": 3, magic: 3, medieval: 3, "souls-like": 3, dragons: 3, jrpg: 2, mythology: 3, demons: 2, "hack-and-slash": 1, "action-rpg": 1 }, genres: { RPG: 2 } },
  { id: "scifi", low: "#2a2f3e", high: "#4c5468", lamp: "#5ee6ff", name: "Neon frontier", creature: "drone", a: "A drone", many: "drones", col: "#4a4f9e", accent: "#5ee6ff",
    tags: { "sci-fi": 3, space: 3, futuristic: 3, aliens: 3, cyberpunk: 3, robots: 3, dystopian: 2, superhero: 1 } },
  { id: "horror", low: "#2c3324", high: "#4c4b3e", lamp: "#9dffc0", name: "Haunted marsh", creature: "ghost", a: "A ghost", many: "ghosts", col: "#5a5568", accent: "#dfeaff",
    tags: { horror: 3, "survival-horror": 4, zombies: 3, gore: 1, dark: 1, supernatural: 2, surreal: 1 } },
  { id: "waste", low: "#7d5a38", high: "#b08c5e", lamp: "#ff8a3a", name: "The wasteland", creature: "beetle", a: "A scrap beetle", many: "scrap beetles", col: "#b68d52", accent: "#e8853a",
    tags: { "post-apocalyptic": 4, war: 3, military: 3, fps: 2, "third-person-shooter": 2, survival: 1, tactical: 1 }, genres: { Shooter: 1 } },
  { id: "old", low: "#6c7234", high: "#a89c5c", lamp: "#ffd08a", name: "Old world", creature: "eagle", a: "An eagle", many: "eagles", col: "#9aa857", accent: "#f1e3c0",
    tags: { historical: 4, assassin: 4, stealth: 2, parkour: 2, crime: 2, america: 1, western: 3, "open-world": 1 } },
  { id: "arena", low: "#3c7628", high: "#6ca43e", lamp: "#fff2cc", name: "The arena", creature: "hare", a: "A hare", many: "hares", col: "#58b65a", accent: "#ffffff",
    tags: { soccer: 5, football: 5, sports: 4, racing: 4, competitive: 2, "beat-em-up": 2, fighting: 3 }, genres: { Sports: 5, Racing: 5, Fighting: 3 } },
  { id: "wonder", low: "#7c6274", high: "#b98fa4", lamp: "#ffe27a", name: "Wonderland", creature: "hopper", a: "A hopper", many: "hoppers", col: "#d98fb6", accent: "#ffd84d",
    tags: { cute: 3, colorful: 2, "family-friendly": 3, "3d-platformer": 3, "side-scroller": 2, cartoony: 3, comedy: 2, funny: 2, "hand-drawn": 2, relaxing: 2, music: 2, "pixel-graphics": 1 },
    genres: { Platformer: 3, Puzzle: 2, Family: 3, Casual: 2, Arcade: 2 } },
  { id: "story", low: "#86602e", high: "#c4944c", lamp: "#ffc070", name: "Story coast", creature: "stag", a: "A stag", many: "stags", col: "#c99a4a", accent: "#b9703a",
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
  fantasy: [() => [part(cyl(.05, .07, .24), "#5b4030", { p: [0, .12, 0] }), part(cone(.3, .5), "#1f6b3a", { p: [0, .45, 0], part: 5 }), part(cone(.21, .42), "#2a8046", { p: [0, .74, 0], part: 5 })],
    () => [part(cyl(.15, .18, .62, 7), "#9a968f", { p: [0, .31, 0] }), part(cone(.23, .34, 7), "#b5473c", { p: [0, .79, 0] }), part(box(.07, .1, .04), "#ffd27a", { p: [0, .42, .16], glow: 1 })]],
  scifi: [() => [part(new THREE.OctahedronGeometry(.17), "#62e8ff", { p: [0, .36, 0], s: [1, 2.3, 1], glow: .8 }), part(new THREE.OctahedronGeometry(.1), "#b58cff", { p: [.17, .18, .05], s: [1, 2, 1], r: [0, 0, -.5], glow: .8 })],
    () => [part(cyl(.02, .035, .95, 5), "#aeb6c8", { p: [0, .47, 0] }), part(ball(.065, 0), "#ff5fd2", { p: [0, .98, 0], glow: 1 }), part(cyl(.16, .02, .07, 8), "#d5dbe8", { p: [0, .6, 0] })]],
  horror: [() => [part(cyl(.035, .07, .62, 5), "#3a3038", { p: [0, .31, 0] }), part(cyl(.018, .028, .32, 4), "#3a3038", { p: [.12, .5, 0], r: [0, 0, -.95] }), part(cyl(.018, .028, .28, 4), "#3a3038", { p: [-.1, .42, .03], r: [.2, 0, .9] }), part(cyl(.012, .02, .2, 4), "#3a3038", { p: [.02, .68, .07], r: [.7, 0, .1] })],
    () => [part(box(.2, .26, .06), "#8f93a0", { p: [0, .13, 0] }), part(cyl(.1, .1, .06, 8), "#8f93a0", { p: [0, .26, 0], r: [Math.PI / 2, 0, 0] })]],
  waste: [() => [part(box(.34, .36, .08), "#a39684", { p: [0, .18, 0], r: [0, 0, .06] }), part(box(.08, .56, .3), "#8f8372", { p: [-.17, .28, .13] }), part(box(.16, .1, .14), "#7a6f61", { p: [.12, .05, .16], r: [0, .5, 0] })],
    () => [part(cyl(.07, .07, .52, 6), "#6f8f4a", { p: [0, .26, 0] }), part(cyl(.04, .04, .2, 5), "#6f8f4a", { p: [.14, .34, 0] }), part(cyl(.04, .04, .1, 5), "#6f8f4a", { p: [.09, .25, 0], r: [0, 0, Math.PI / 2] }), part(cyl(.04, .04, .16, 5), "#6f8f4a", { p: [-.13, .27, 0] }), part(cyl(.04, .04, .1, 5), "#6f8f4a", { p: [-.08, .2, 0], r: [0, 0, Math.PI / 2] })]],
  old: [() => [part(cyl(.04, .06, .3), "#6a4a30", { p: [0, .15, 0] }), part(ball(.27, 1), "#6f9440", { p: [0, .5, 0], s: [1, .85, 1], part: 5 })],
    () => [part(cyl(.1, .1, .05, 8), "#e9e2d0", { p: [0, .025, 0] }), part(cyl(.065, .075, .62, 8), "#f3eddd", { p: [0, .36, 0] }), part(box(.22, .06, .22), "#e9e2d0", { p: [0, .7, 0] })]],
  arena: [() => [part(cyl(.014, .014, .8, 4), "#f2f2f2", { p: [0, .4, 0] }), part(tri([[0, .78, 0], [0, .58, 0], [.3, .68, 0]]), "#ff4d4d", { part: 5 }), part(tri([[0, .78, 0], [.3, .68, 0], [0, .58, 0]]), "#ff4d4d", { part: 5 })],
    () => [part(cyl(.02, .02, .4, 4), "#ffffff", { p: [0, .2, -.28] }), part(cyl(.02, .02, .4, 4), "#ffffff", { p: [0, .2, .28] }), part(cyl(.02, .02, .58, 4), "#ffffff", { p: [0, .4, 0], r: [Math.PI / 2, 0, 0] })]],
  wonder: [() => [part(cyl(.06, .085, .3, 7), "#f3e6d0", { p: [0, .15, 0] }), part(dome(.25), "#e2504a", { p: [0, .27, 0], s: [1, .8, 1] }), part(ball(.045, 0), "#ffffff", { p: [.1, .42, .06] }), part(ball(.04, 0), "#ffffff", { p: [-.09, .4, -.1] })],
    () => [part(cyl(.012, .012, .32, 4), "#4f9a4a", { p: [0, .16, 0] }), part(ball(.09, 0), "#ffd84d", { p: [0, .35, 0], glow: .35 }), part(cyl(.14, .14, .015, 6), "#ff9ecb", { p: [0, .33, 0] })]],
  story: [() => [part(cyl(.03, .04, .14), "#5b4030", { p: [0, .07, 0] }), part(cone(.13, .85, 6), "#2f6a5a", { p: [0, .55, 0], part: 5 })],
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
  vec3 o = c * (.1 + vec3(1.08, 1.03, .96) * d * l) + c * vec3(.1, .13, .26) * (1. - l);
  o += c * vec3(1., .4, .1) * smoothstep(.34, 0., abs(day - .04)) * .55 * (.4 + max(dot(n, uSun), 0.));        // golden hour along the edge of the night
  return o + c * glow * (.3 + 1.7 * (1. - l)); }`;

const NOISE = `uniform float uTime;
float hash3(vec3 p) { p = fract(p * .3183099 + .1); p *= 17.; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float noise(vec3 x) { vec3 i = floor(x), f = fract(x); f = f * f * (3. - 2. * f);
  return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }
float fbm2(vec3 p) { return .62 * noise(p) + .38 * noise(p * 2.07 + 7.1); }
float fbm3(vec3 p) { return .5 * noise(p) + .28 * noise(p * 2.03 + 7.1) + .16 * noise(p * 4.1 + 13.7) + .06 * noise(p * 8.3 + 3.3); }
float cloud(vec3 d) { float a = uTime * .006; vec3 p = vec3(d.x * cos(a) - d.z * sin(a), d.y, d.x * sin(a) + d.z * cos(a));   // one drifting cloud field, shared by the cloud layer and its shadow on the ground
  float w = fbm3(p * 2.1 + 11.), c = fbm3(p * 4.2 + w * 1.7 + vec3(0., uTime * .003, 0.)) + .1 * sin(d.y * 7. + w * 5.); return smoothstep(.57, .76, c); }`;
const TERRAIN = `float terrain(vec3 n, out vec3 g) { float h = 0., s; g = vec3(0.);
` + WAVES.map(w => { const k = `vec3(${w.x.toFixed(5)}, ${w.y.toFixed(5)}, ${w.z.toFixed(5)})`; return `  s = dot(n, ${k}) + ${w.p.toFixed(5)}; h += ${w.a.toFixed(5)} * sin(s); g += ${w.a.toFixed(5)} * cos(s) * ${k};`; }).join("\n") + `
  g *= ${(2.2 / WSUM).toFixed(5)}; return h * ${(2.2 / WSUM).toFixed(5)}; }`;

export function createPlanet(env) {
  const { camera, controls, canvas, info, esc, labels, calm, tex } = env, $ = id => document.getElementById(id);
  const scene = new THREE.Scene(); scene.background = new THREE.Color("#010208");
  const U = { uTime: { value: 0 }, uSun: { value: new THREE.Vector3(1, .25, .4).normalize() } }, grow = new Float32Array(8);
  const P = { scene, sun0: 0, follow: null, zoom: 0, back: 0, home: 50, T: env.now, legend: "" };
  const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), v3 = new THREE.Vector3(), m4 = new THREE.Matrix4();

  /* games -> realms */
  const realms = REALMS.map((r, i) => ({ ...r, i, games: [], hours: 0, land: new THREE.Color(r.col), tint: new THREE.Color(r.accent) }));
  const games = env.games.map(f => ({ f, realm: realms[realmOf(f.g)] }));
  games.forEach(c => { c.realm.games.push(c); c.realm.hours += c.f.hours; });
  const total = realms.reduce((n, r) => n + r.hours, 0) || 1;

  /* the ground: a finely divided sphere, lifted by the terrain; all its colour and light is worked out per pixel */
  const geo = new THREE.IcosahedronGeometry(1, 48), pos = geo.attributes.position, NF = pos.count / 3;
  const cents = [], hs = [];
  for (let f = 0; f < NF; f++) { const c = new THREE.Vector3(); for (let k = 0; k < 3; k++) c.add(v1.fromBufferAttribute(pos, f * 3 + k)); cents.push(c.normalize()); hs.push(height(c)); }
  SEA = [...hs].sort((a, b) => a - b)[Math.floor(NF * .42)];
  const fib = i => { const y = 1 - (i + .5) / 4, r = Math.sqrt(1 - y * y), a = i * 2.39996; return new THREE.Vector3(Math.cos(a) * r, y * .85, Math.sin(a) * r).normalize(); };
  const order = [...realms].sort((a, b) => b.hours - a.hours);
  order.forEach((r, k) => { const want = fib([3, 4, 1, 6, 2, 5, 0, 7][k]); let best = 0, bd = -2;        // biggest lands around the equator; seeds sit on dry ground
    for (let f = 0; f < NF; f++) if (hs[f] > SEA + .1) { const d = cents[f].dot(want); if (d > bd) { bd = d; best = f; } }
    r.seed = cents[best].clone(); r.w = Math.pow(Math.max(.03, r.hours / total), .32); r.faces = []; r.radius = .1; });
  const faceRealm = new Int8Array(NF);
  for (let f = 0; f < NF; f++) { const c = cents[f]; let ri = -1;
    if (hs[f] - SEA > 0) { let bd = 1e9; for (const r of realms) { const d = Math.acos(Math.min(1, c.dot(r.seed))) / r.w; if (d < bd) { bd = d; ri = r.i; } }
      const r = realms[ri], ang = Math.acos(Math.min(1, c.dot(r.seed))); r.faces.push({ f, ang }); r.radius = Math.max(r.radius, ang); }
    faceRealm[f] = ri; }
  realms.forEach(r => { r.faces.sort((a, b) => a.ang - b.ang); r.faces.forEach(o => { o.rank = o.ang / r.radius; }); });
  for (let i = 0; i < pos.count; i++) { v1.fromBufferAttribute(pos, i).normalize(); v1.multiplyScalar(radiusAt(v1)); pos.setXYZ(i, v1.x, v1.y, v1.z); }
  const UG = { uSea: { value: SEA }, uGrow: { value: grow }, uSeed: { value: realms.map(r => new THREE.Vector4(r.seed.x, r.seed.y, r.seed.z, r.w)) }, uRad: { value: realms.map(r => r.radius) },
    uLow: { value: realms.map(r => new THREE.Color(r.low).multiplyScalar(1.5)) }, uHigh: { value: realms.map(r => new THREE.Color(r.high).multiplyScalar(1.5)) }, uLamp: { value: realms.map(r => new THREE.Color(r.lamp)) }, uNeon: { value: realms.find(r => r.id === "scifi").i } };
  const ground = new THREE.Mesh(geo, new THREE.ShaderMaterial({ uniforms: { ...U, ...UG },
    vertexShader: `varying vec3 vP; void main() { vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
    fragmentShader: NOISE + TERRAIN + `
      uniform vec4 uSeed[8]; uniform vec3 uLow[8]; uniform vec3 uHigh[8]; uniform vec3 uLamp[8]; uniform float uRad[8]; uniform float uGrow[8]; uniform float uSea, uNeon; uniform vec3 uSun; varying vec3 vP;
      void main() { vec3 d = normalize(vP), V = normalize(cameraPosition - vP), g, n = d, glow = vec3(0.), col;
        float h = terrain(d, g) - uSea, det = fbm3(d * 9.) - .45, fine = fbm3(d * 31. + 3.), hh = h + det * .2, spec = 0.;
        float day = dot(d, uSun), l = smoothstep(-.12, .22, day), shadow = 1. - .5 * cloud(normalize(d + uSun * .03));
        vec3 sunc = mix(vec3(1., .42, .16), vec3(1., .96, .9), smoothstep(-.05, .4, day));                       // sunlight reddens near the edge of the night
        if (hh > 0.) {
          vec3 q = normalize(d + (vec3(noise(d * 5. + 3.), noise(d * 5. + 11.), noise(d * 5. + 19.)) - .5) * .1);   // ragged, natural borders between lands
          float b1 = 9., b2 = 9.; int i1 = 0, i2 = 0;
          for (int i = 0; i < 8; i++) { float a = acos(clamp(dot(q, uSeed[i].xyz), -1., 1.)) / uSeed[i].w; if (a < b1) { b2 = b1; i2 = i1; b1 = a; i1 = i; } else if (a < b2) { b2 = a; i2 = i; } }
          float t = clamp(hh * .9 + (fine - .5) * .9, 0., 1.), w = smoothstep(0., .06, b2 - b1) * .5 + .5;
          vec3 lush = mix(mix(uLow[i2], uHigh[i2], t), mix(uLow[i1], uHigh[i1], t), w);
          float rank = acos(clamp(dot(d, uSeed[i1].xyz), -1., 1.)) / uRad[i1], alive = smoothstep(0., .1, uGrow[i1] - rank * .92 + (fine - .5) * .08);
          col = mix(mix(vec3(.3, .25, .21), vec3(.47, .42, .37), fine), lush, alive);                              // bare rock until you play there
          col *= .86 + .28 * noise(d * 120.);                                                                     // fine grain, for close-ups
          col = mix(col, vec3(.76, .7, .52), smoothstep(.06, 0., hh));                                             // beaches
          vec3 gt = g - d * dot(g, d);
          col = mix(col, mix(vec3(.34, .32, .3), vec3(.5, .48, .46), fine), smoothstep(.6, 1., hh + length(gt) * .1) * .85);   // rock on the heights
          float ice = clamp(smoothstep(1.05, 1.22, hh + det * .25) + smoothstep(.85, .91, abs(d.y) + det * .08), 0., 1.);
          col = mix(col, vec3(.93, .95, .98), ice);                                                                // snow on peaks and at the poles
          float e = .006; vec3 t1 = normalize(cross(d, vec3(.13, 1., .07))), t2 = cross(d, t1);
          float n0 = fbm2(d * 14.), nx = fbm2((d + t1 * e) * 14.), ny = fbm2((d + t2 * e) * 14.);
          n = normalize(d - gt * .17 - (t1 * (nx - n0) + t2 * (ny - n0)) / e * .035);                               // relief
          float town = smoothstep(.5, .72, noise(d * 13. + 5.)) * step(.76, noise(d * 170.)) * alive * (1. - ice);
          glow = uLamp[i1] * town * (1. - l) * 2.4;                                                                // lights come on at night where your lands are alive
          if (abs(float(i1) - uNeon) < .5) glow += vec3(.2, .9, 1.) * smoothstep(.035, 0., abs(noise(d * 16. + 2.) - .5)) * alive * (.2 + 1.7 * (1. - l));
        } else {
          float depth = -hh; col = mix(vec3(.05, .34, .4), vec3(.012, .065, .18), smoothstep(0., .45, depth));
          vec3 wv = vec3(noise(d * 70. + uTime * .5), noise(d * 70. + 17. - uTime * .4), noise(d * 70. + 31. + uTime * .3)) - .5; n = normalize(d + wv * .05);
          float r = max(dot(reflect(-uSun, n), V), 0.); spec = pow(r, 70.) * 2. + pow(r, 9.) * .1;
          col = mix(col, vec3(.45, .65, .9), pow(1. - max(dot(d, V), 0.), 4.) * .5);
          col = mix(col, vec3(.9, .96, 1.), smoothstep(.05, 0., depth) * smoothstep(.35, .7, noise(d * 60. + uTime * .3)) * .8);   // surf
          float ice = smoothstep(.87, .93, abs(d.y) + det * .08); col = mix(col, vec3(.9, .94, .98), ice); spec *= 1. - ice;
        }
        float diff = max(dot(n, uSun), 0.) * shadow;
        vec3 o = col * (sunc * diff * 1.5 + vec3(.06, .07, .09) * l) + col * vec3(.025, .035, .07) * (1. - l) + sunc * spec * shadow * smoothstep(0., .15, day) + glow;
        float rim = pow(1. - max(dot(d, V), 0.), 3.); o = mix(o, mix(vec3(.8, .45, .25), vec3(.35, .6, 1.), smoothstep(-.12, .12, day)) * smoothstep(-.3, .1, day), rim * .6);   // air
        gl_FragColor = vec4(o, 1.); }` }));
  scene.add(ground);

  /* instanced things (props, clouds, creatures) share one shader */
  const material = (anim, freq, uG) => new THREE.ShaderMaterial({ side: THREE.DoubleSide, uniforms: { ...U, uAnim: { value: anim }, uFreq: { value: freq }, uG: uG || { value: 1 } },
    vertexShader: `attribute vec3 aC, aFx, aCol; attribute vec4 aInst; attribute float aRank; uniform float uTime, uFreq, uG; uniform int uAnim; varying vec3 vC, vN, vUp; varying float vGlow;
      void main() { vec3 p = position; float ph = aInst.x, mv = aInst.y, t = uTime;
        if (uAnim == 0) { if (aFx.y > .5 && aFx.y < 1.5) { float a = sin(t * uFreq + ph) * .7 + .12; p.y += abs(p.z) * sin(a); p.z *= cos(a); } }
        else if (uAnim == 1) p.y += sin(t * 2. + ph) * .06;
        else if (uAnim == 2) { p.x += sin(t * 3. + p.y * 9. + ph) * .06 * smoothstep(.1, -.3, p.y); p.y += sin(t * 1.5 + ph) * .06; }
        else if (uAnim == 3) { if (aFx.y > 2.5) p.x += sin(t * uFreq + ph + p.z * 9. + p.x * 6.) * .075 * mv * smoothstep(.42, 0., p.y); p.y += abs(sin(t * uFreq * .5 + ph)) * .02 * mv; }
        else if (uAnim == 8) { }
        else if (uAnim == 4) { float s = sin(t * uFreq + ph); p.y = p.y * (1. + .2 * s * mv) + max(0., s) * mv * .5; p.xz *= 1. - .1 * s * mv; }
        else { p *= smoothstep(0., .1, uG - aRank * .92); if (aFx.y > 4.5) { vec4 o = instanceMatrix * vec4(0., 0., 0., 1.); p.x += sin(t * 1.4 + o.x * 2. + o.z * 3.) * .05 * p.y; p.z += cos(t * 1.1 + o.y * 3.) * .03 * p.y; } }
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
    const spots = r.faces.filter(o => hs[o.f] - SEA > .06 && hs[o.f] - SEA < .95), want = Math.min(Math.floor(spots.length * .12), 110, Math.max(8, Math.round(r.hours / 6)));
    const pick = spots.map(o => [hash(o.f, 9), o]).sort((a, b) => a[0] - b[0]).slice(0, want).map(e => e[1]);
    [pick.filter((_, i) => i % 5 !== 0), pick.filter((_, i) => i % 5 === 0)].forEach((list, k) => { if (!list.length) return;
      const mesh = instanced(PROPS[r.id][k](), list.length, material(9, 0, r.uG));
      list.forEach((o, i) => { place(mesh, i, cents[o.f], hash(o.f, 4) * 6.283, .5 + hash(o.f, 5) * .45); mesh.geometry.attributes.aRank.setX(i, Math.min(1, o.rank + .04)); });
      scene.add(mesh); });
  });

  /* creatures: one per game */
  const cLen = h => .55 + .12 * Math.sqrt(h);
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
  const plats = games.filter(c => c.f.platAt), rings = plats.length ? instanced([part(new THREE.TorusGeometry(.24, .035, 6, 18), "#ffd465", { r: [Math.PI / 2, 0, 0], glow: 1.5 })], plats.length, material(8, 0)) : null;
  if (rings) { rings.instanceMatrix.setUsage(THREE.DynamicDrawUsage); scene.add(rings); }
  const halo = (() => { const n = games.length, g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(n * 3), 3)); g.setAttribute("aSize", new THREE.BufferAttribute(new Float32Array(n), 1)); g.setAttribute("aCol", new THREE.BufferAttribute(new Float32Array(n * 4), 4));
    const p = new THREE.Points(g, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uMap: { value: tex }, uScale: P.uScale = { value: 800 } },
      vertexShader: `attribute float aSize; attribute vec4 aCol; uniform float uScale; varying vec4 vCol; void main() { vec4 mv = modelViewMatrix * vec4(position, 1.); gl_Position = projectionMatrix * mv; gl_PointSize = aSize * uScale / max(.1, -mv.z); vCol = aCol; }`,
      fragmentShader: `uniform sampler2D uMap; varying vec4 vCol; void main() { gl_FragColor = vec4(vCol.rgb, vCol.a * texture2D(uMap, gl_PointCoord).a); }` }));
    p.frustumCulled = false; scene.add(p); return p; })();

  /* sky: air, clouds, stars and the backlog moon */
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(RP * 1.16, 64, 48), new THREE.ShaderMaterial({ side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { ...U },
    vertexShader: `varying vec3 vN, vW; void main() { vN = normalize(normalMatrix * normal); vW = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
    fragmentShader: `uniform vec3 uSun; varying vec3 vN, vW; void main() { float i = pow(max(0., .8 - dot(vN, vec3(0., 0., 1.))), 3.2), day = dot(vW, uSun);
      gl_FragColor = vec4(mix(vec3(1., .45, .2), vec3(.3, .58, 1.), smoothstep(-.15, .12, day)) * smoothstep(-.45, .05, day), 1.) * i * 1.5; }` })));
  const cloudFade = { value: 1 };
  { const m = new THREE.Mesh(new THREE.SphereGeometry(RP + 1.05, 96, 64), new THREE.ShaderMaterial({ transparent: true, depthWrite: false, uniforms: { ...U, uFade: cloudFade },
      vertexShader: `varying vec3 vP; void main() { vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
      fragmentShader: NOISE + `uniform vec3 uSun; uniform float uFade; varying vec3 vP;
        void main() { vec3 d = normalize(vP); float dens = cloud(d); if (dens < .02) discard;
          float day = dot(d, uSun), self = cloud(normalize(d + uSun * .045));
          vec3 sunc = mix(vec3(1., .45, .2), vec3(1.), smoothstep(-.05, .4, day));
          vec3 c = sunc * smoothstep(-.2, .3, day) * (1. - .3 * self) * (.95 + .25 * dens) + vec3(.02, .03, .055);
          gl_FragColor = vec4(c, dens * .92 * uFade); }` }));
    m.renderOrder = 2; scene.add(m); }
  { const n = 2600, a = new Float32Array(n * 3), c = new Float32Array(n * 3), axis = new THREE.Vector3(.35, .8, .5).normalize();
    for (let i = 0; i < n; i++) { v1.set(hash(i, 30) - .5, hash(i, 31) - .5, hash(i, 32) - .5).normalize(); if (i % 5 < 2) v1.addScaledVector(axis, -v1.dot(axis) * .88).normalize();   // a milky band across the sky
      v1.multiplyScalar(700); a.set([v1.x, v1.y, v1.z], i * 3); const b = Math.pow(hash(i, 33), 3) * .9 + .12, t = hash(i, 34); c.set([b * (t > .8 ? 1 : .8), b * .88, b * (t < .2 ? 1 : .82)], i * 3); }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(a, 3)); g.setAttribute("color", new THREE.BufferAttribute(c, 3));
    scene.add(new THREE.Points(g, new THREE.PointsMaterial({ vertexColors: true, size: 1.7, sizeAttenuation: false, transparent: true, depthWrite: false }))); }
  const sunSprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color: new THREE.Color(5, 3.6, 2), blending: THREE.AdditiveBlending, depthWrite: false })); sunSprite.scale.setScalar(70); scene.add(sunSprite);
  const aurora = [1, -1].map(side => { const m = new THREE.Mesh(new THREE.CylinderGeometry(3.3, 4.6, 2.6, 72, 1, true), new THREE.ShaderMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, uniforms: { ...U, uSide: { value: side } },
      vertexShader: `varying vec2 vUv; varying vec3 vW; void main() { vUv = uv; vec4 w = modelMatrix * vec4(position, 1.); vW = normalize(w.xyz); gl_Position = projectionMatrix * viewMatrix * w; }`,
      fragmentShader: `uniform vec3 uSun; uniform float uTime; varying vec2 vUv; varying vec3 vW;
        void main() { float x = vUv.x * 6.283, curtain = .5 + .5 * sin(x * 7. + uTime * .8 + sin(x * 3. - uTime * .5) * 2.), fine = .6 + .4 * sin(x * 41. + uTime * 2.);
          float a = pow(1. - vUv.y, 1.6) * smoothstep(0., .12, vUv.y) * curtain * fine * (1. - smoothstep(-.25, .15, dot(vW, uSun)));
          gl_FragColor = vec4(mix(vec3(.2, 1.6, .7), vec3(.9, .3, 1.5), vUv.y) * a * .8, a); }` }));
    m.position.y = side * (RP + 1.25); if (side < 0) m.rotation.x = Math.PI; m.renderOrder = 5; scene.add(m); return m; });
  // fireflies over the gentler lands at night
  { const spots = realms.filter(r => ["wonder", "story", "fantasy", "horror"].includes(r.id)).flatMap(r => r.faces.filter(o => hash(o.f, 21) < .02 && hs[o.f] - SEA > .05).map(o => [r, o])), n = spots.length, g = new THREE.BufferGeometry();
    const a = new Float32Array(n * 3), b = new Float32Array(n * 3), c = new Float32Array(n * 3);
    spots.forEach(([r, o], i) => { v1.copy(cents[o.f]).multiplyScalar(radiusAt(cents[o.f]) + .35 + hash(o.f, 22) * .7); a.set([v1.x, v1.y, v1.z], i * 3); b.set([r.i, Math.min(1, o.rank + .05), hash(o.f, 23) * 6.283], i * 3); c.set(r.id === "horror" ? [.5, 1, .7] : [1, .9, .45], i * 3); });
    g.setAttribute("position", new THREE.BufferAttribute(a, 3)); g.setAttribute("aBR", new THREE.BufferAttribute(b, 3)); g.setAttribute("aC", new THREE.BufferAttribute(c, 3));
    const pts = new THREE.Points(g, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { ...U, uMap: { value: tex }, uScale: P.uScale, uGrow: { value: grow } },
      vertexShader: `attribute vec3 aBR, aC; uniform float uGrow[8]; uniform float uTime, uScale; uniform vec3 uSun; varying vec4 vCol;
        void main() { vec3 up = normalize(position), p = position + up * sin(uTime * 1.3 + aBR.z) * .15 + cross(up, vec3(.3, 1., .2)) * sin(uTime * .9 + aBR.z * 2.) * .2;
          vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv; gl_PointSize = .3 * uScale / max(.1, -mv.z);
          float a = (1. - smoothstep(-.2, .1, dot(up, uSun))) * step(aBR.y, uGrow[int(aBR.x + .5)]) * (.55 + .45 * sin(uTime * 3. + aBR.z * 5.)); vCol = vec4(aC * 2.2, a); }`,
      fragmentShader: `uniform sampler2D uMap; varying vec4 vCol; void main() { gl_FragColor = vec4(vCol.rgb, vCol.a * texture2D(uMap, gl_PointCoord).a); }` }));
    pts.frustumCulled = false; scene.add(pts); }
  const moon = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), new THREE.ShaderMaterial({ uniforms: { ...U },
    vertexShader: `varying vec3 vP; void main() { vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`,
    fragmentShader: NOISE + `uniform vec3 uSun; varying vec3 vP;
      float surf(vec3 d) { float c = noise(d * 5.) * noise(d * 5. + 9.); return fbm3(d * 3.5) * .6 - smoothstep(.22, .34, c) * .25 + smoothstep(.3, .36, c) * .12; }   // dust, and craters with a raised lip
      void main() { vec3 d = normalize(vP); float e = .012; vec3 t1 = normalize(cross(d, vec3(.13, 1., .07))), t2 = cross(d, t1);
        float s0 = surf(d), sx = surf(d + t1 * e), sy = surf(d + t2 * e); vec3 n = normalize(d - (t1 * (sx - s0) + t2 * (sy - s0)) / e * .22);
        float alb = .42 + .5 * s0 - .16 * smoothstep(.5, .62, noise(d * 1.7 + 4.));
        gl_FragColor = vec4(vec3(.82, .8, .78) * alb * (.012 + 1.25 * max(dot(n, uSun), 0.)), 1.); }` }));
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
    { const a = P.sun0 + (calm ? 0 : t * .07); sun.set(Math.cos(a), .28, Math.sin(a)).normalize(); }                     // a day lasts about a minute and a half
    sunSprite.position.copy(sun).multiplyScalar(420);
    cloudFade.value += (THREE.MathUtils.smoothstep(camera.position.distanceTo(controls.target), 10, 30) * (P.follow ? 0 : 1) - cloudFade.value) * Math.min(1, dt * 3);   // clouds part when you come close
    const ma = t * .06 + 4.2; moon.position.set(Math.cos(ma) * 25, Math.sin(ma * .7) * 6 + 5, Math.sin(ma) * 25); 
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
        const on = c.born && s > .05 && c.active && !c.plat;
        { const up = s * (def.fly ? .35 : 1.05); hp.position.setXYZ(hi, c.p.x + c.n.x * up, c.p.y + c.n.y * up, c.p.z + c.n.z * up); } hp.aSize.setX(hi, on ? s * 1.1 + .3 * (1 + Math.sin(t * 4 + c.ph)) : 0);
        if (c.plat) hp.aCol.setXYZW(hi, 1, .8, .3, .75); else hp.aCol.setXYZW(hi, .8, .95, 1, .3); hi++;
      }
      r.mesh.instanceMatrix.needsUpdate = inst.needsUpdate = true; }
    hp.position.needsUpdate = hp.aSize.needsUpdate = hp.aCol.needsUpdate = true;
    if (rings) { plats.forEach((c, i) => { const s = c.plat && c.born ? c.s * c.vis : 0, top = s * (c.realm.def.fly ? .4 : c.realm.creature === "stag" ? 1.35 : c.realm.creature === "hare" ? 1.05 : .75) + .12 * Math.sin(t * 2 + c.ph) * s;
        v3.crossVectors(c.t, c.n); v1.copy(c.p).addScaledVector(c.n, top); m4.makeBasis(c.t, c.n, v3).scale(v2.set(s, s, s)).setPosition(v1); rings.setMatrixAt(i, m4); }); rings.instanceMatrix.needsUpdate = true; }
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
  const composer = new EffectComposer(env.renderer, new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: 4 }));
  composer.addPass(new RenderPass(scene, camera)); const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), .5, .5, 1.); composer.addPass(bloom);
  const render = () => { composer.render();
    const now = performance.now(), took = now - (P.last || now); P.last = now;                              // a slow device gets a lighter picture instead of a slideshow
    if (took > 45 && took < 1000) P.slow++; if (++P.frames >= 45) { if (P.slow > 30 && P.quality > .55) { P.quality = P.quality > 1 ? 1 : P.quality - .25; homeDist(); } P.slow = P.frames = 0; } };
  function homeDist() {
    P.quality = Math.min(P.quality || 9, env.renderer.getPixelRatio()); composer.setPixelRatio(P.quality); composer.setSize(innerWidth, innerHeight);
    const top = document.querySelector("header").getBoundingClientRect().bottom, bot = document.querySelector("footer").getBoundingClientRect().top;
    const free = Math.max(.4, (bot - top) / innerHeight), v = THREE.MathUtils.degToRad(camera.fov) / 2, hx = Math.atan(Math.tan(v) * camera.aspect);
    camera.setViewOffset(innerWidth, innerHeight, 0, Math.round((innerHeight - bot - top) / 2), innerWidth, innerHeight);
    P.uScale.value = env.renderer.domElement.height / (2 * Math.tan(v));
    return P.home = Math.max((RP + 3.4) / (Math.tan(v) * free), (RP + 4.2) / Math.tan(hx));
  }
  const hello = () => info("🌍", "Your games grew this planet", "Each kind of game grows a land, each game is a creature living on it (bigger = more hours). Platinums wear a halo, dropped games turn to stone, the moon is your backlog. Tap anything.");
  function enter() {
    P.follow = null; P.back = 0; camera.up.set(0, 1, 0); P.slow = 0; P.frames = 0; P.last = 0; controls.minDistance = RP + 4; controls.maxDistance = 140; controls.minPolarAngle = .25; controls.maxPolarAngle = Math.PI - .25; controls.autoRotate = !calm; controls.autoRotateSpeed = .5;
    const d = homeDist(); controls.target.set(0, 0, 0); v1.copy(order[0].seed).setY(order[0].seed.y + .35).normalize(); camera.position.copy(v1).multiplyScalar(calm ? d : d * 1.9); if (!calm) P.back = 4;   // glide in
    P.sun0 = Math.atan2(v1.z, v1.x) - .75 - (calm ? 0 : U.uTime.value * .07);                             // start with the sun on the side you're looking at
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
  return Object.assign(P, { time, frame, enter, pick, render, resize: homeDist, realms });
}
