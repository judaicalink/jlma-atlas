/* The Atlas of JudaicaLink Mannheim (jlma-atlas): a map of entities, filtered by time and area. Plain JavaScript,
   no libraries; the base map and the data come from this site (decision 0001). */
(function () {
  "use strict";

  const app = document.getElementById("main");
  const BASE = app.dataset.base;
  const D = "http://data.judaicalink.org";
  const EARLIEST = -3000, NOW = 2026;
  const ROLE_LABEL = { birth: "born", activity: "active", exile: "in exile", death: "died", burial: "buried",
    seat: "seat", printed: "printed", edition: "edition", published: "published" };
  const KIND_PLURAL = ["people", "organisations", "publications"];
  const KIND_ONE = ["person", "organisation", "publication"];
  const REL_LABEL = { family: "family", friendship: "acquaintance or friendship", professional: "professional",
    creator: "book and maker" };
  const REL_DASH = { family: [], friendship: [5, 3], professional: [1.5, 3], creator: [9, 3, 2, 3] };
  const LIFE_ORDER = ["birth", "activity", "exile", "death", "burial"];

  // ---- state -------------------------------------------------------------------------------------------------
  const DEFAULTS = () => ({
    from: 1880, to: 1910, area: null, kinds: [true, true, true], mode: "life", rels: [true, true, true, true],
    sel: null, view: null, missing: null,
  });
  const S = DEFAULTS();
  let A = null;        // the data
  let BM = null;       // the base map
  let V = null;        // what the filters let through

  // ---- helpers -----------------------------------------------------------------------------------------------
  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids) if (k !== null && k !== undefined) e.append(k instanceof Node ? k : String(k));
    return e;
  }
  const fmt = (n) => n.toLocaleString("en");
  const fold = (s) => s.normalize("NFD").replace(/[̀-֑ͯ-ׇ]/g, "").toLowerCase();
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function iriOf(id, isPlace) {
    if (typeof id === "number") return `${D}/data/ep/${id}`;
    return id;
  }
  function viewHref(id) {
    const iri = iriOf(id);
    return iri.startsWith(D + "/") ? iri.slice(D.length) : iri;
  }
  function plural(n, kind) { return n === 1 ? KIND_ONE[kind] : KIND_PLURAL[kind]; }

  // ---- data --------------------------------------------------------------------------------------------------
  function decode(data) {
    const P = data.places.id.length, N = data.entities.id.length;
    const px = new Float64Array(P), py = new Float64Array(P);
    for (let i = 0; i < P; i++) [px[i], py[i]] = project(data.places.lon[i], data.places.lat[i]);
    const e = data.entities;
    const po = Int32Array.from(e.po), M = po[N];
    const plP = new Int32Array(M), plR = new Uint8Array(M), plY = new Int16Array(M), plE = new Int32Array(M);
    for (let j = 0; j < M; j++) { plP[j] = e.pl[3 * j]; plR[j] = e.pl[3 * j + 1]; plY[j] = e.pl[3 * j + 2]; }
    for (let i = 0; i < N; i++) for (let j = po[i]; j < po[i + 1]; j++) plE[j] = i;
    const roles = data.roles, R = (name) => roles.indexOf(name);
    // the main place of an entity, for its connections: a place of activity, else death, burial, birth
    const prim = new Int32Array(N);
    const order = [R("activity"), R("death"), R("burial"), R("birth")];
    for (let i = 0; i < N; i++) {
      let best = plP[po[i]], rank = 99;
      for (let j = po[i]; j < po[i + 1]; j++) {
        const k = order.indexOf(plR[j]);
        if (k >= 0 && k < rank) { rank = k; best = plP[j]; }
      }
      prim[i] = best;
    }
    // presences by place
    const pStart = new Int32Array(P + 1);
    for (let j = 0; j < M; j++) pStart[plP[j] + 1]++;
    for (let i = 0; i < P; i++) pStart[i + 1] += pStart[i];
    const pList = new Int32Array(M), fill = pStart.slice(0, P);
    for (let j = 0; j < M; j++) pList[fill[plP[j]]++] = j;
    // connections by entity
    const C = data.connections.length / 3;
    const cA = new Int32Array(C), cB = new Int32Array(C), cK = new Uint8Array(C);
    const aStart = new Int32Array(N + 1);
    for (let c = 0; c < C; c++) {
      cA[c] = data.connections[3 * c]; cB[c] = data.connections[3 * c + 1]; cK[c] = data.connections[3 * c + 2];
      aStart[cA[c] + 1]++; aStart[cB[c] + 1]++;
    }
    for (let i = 0; i < N; i++) aStart[i + 1] += aStart[i];
    const aList = new Int32Array(2 * C), afill = aStart.slice(0, N);
    for (let c = 0; c < C; c++) { aList[afill[cA[c]]++] = c; aList[afill[cB[c]]++] = c; }
    const byId = new Map(), placeById = new Map();
    e.id.forEach((id, i) => byId.set(String(id), i));
    data.places.id.forEach((id, i) => placeById.set(String(id), i));
    return {
      raw: data, P, N, M, C, px, py, lon: data.places.lon, lat: data.places.lat, plabel: data.places.label,
      pid: data.places.id, pcountry: Int16Array.from(data.places.country), kind: Uint8Array.from(e.kind),
      start: Int16Array.from(e.start), end: Int16Array.from(e.end), flags: Uint8Array.from(e.flags),
      label: e.label, id: e.id, po, plP, plR, plY, plE, prim, pStart, pList, cA, cB, cK, aStart, aList,
      roles, relKinds: data.relKinds, countries: data.countries, byId, placeById,
      R: { birth: R("birth"), death: R("death"), burial: R("burial") },
    };
  }

  // the time of a presence: [from, to], or null when it has no time in this mode
  function span(j) {
    const i = A.plE[j], r = A.plR[j];
    if (A.plY[j]) return [A.plY[j], A.plY[j]];
    if (S.mode === "events") {
      if (r === A.R.birth) return A.flags[i] & 1 ? null : [A.start[i], A.start[i]];
      if (r === A.R.death || r === A.R.burial) return A.flags[i] & 2 ? null : [A.end[i], A.end[i]];
    }
    return [A.start[i], A.end[i]];
  }
  function inTime(j) {
    const s = span(j);
    return s !== null && s[1] >= (S.from === null ? EARLIEST : S.from) && s[0] <= S.to;
  }
  function areaTest() {
    const a = S.area;
    if (!a) return null;
    const t = new Uint8Array(A.P);
    for (let p = 0; p < A.P; p++) {
      t[p] = a.type === "country" ? A.pcountry[p] === a.i
        : (A.lon[p] >= a.w && A.lon[p] <= a.e && A.lat[p] >= a.s && A.lat[p] <= a.n) ? 1 : 0;
    }
    return t;
  }

  let inArea = null;
  function compute() {
    const P = A.P, counts = new Int32Array(P * 3), stamp = new Int32Array(P).fill(-1), visE = new Uint8Array(A.N);
    let nE = [0, 0, 0];
    for (let i = 0; i < A.N; i++) {
      const k = A.kind[i];
      if (!S.kinds[k]) continue;
      for (let j = A.po[i]; j < A.po[i + 1]; j++) {
        const p = A.plP[j];
        if (inArea && !inArea[p]) continue;
        if (!inTime(j)) continue;
        if (!visE[i]) { visE[i] = 1; nE[k]++; }
        if (stamp[p] !== i) { stamp[p] = i; counts[p * 3 + k]++; }
      }
    }
    const places = [];
    for (let p = 0; p < P; p++) {
      const t = counts[p * 3] + counts[p * 3 + 1] + counts[p * 3 + 2];
      if (t) places.push(p);
    }
    const tot = (p) => counts[p * 3] + counts[p * 3 + 1] + counts[p * 3 + 2];
    places.sort((a, b) => tot(b) - tot(a));
    // connections between visible entities, joined per pair of main places and kind
    const pairs = new Map(), within = new Int32Array(P);
    let nC = 0;
    for (let c = 0; c < A.C; c++) {
      if (!S.rels[A.cK[c]] || !visE[A.cA[c]] || !visE[A.cB[c]]) continue;
      const pa = A.prim[A.cA[c]], pb = A.prim[A.cB[c]];
      if (inArea && !inArea[pa] && !inArea[pb]) continue;
      nC++;
      if (pa === pb) { within[pa]++; continue; }
      const key = ((pa < pb ? pa * P + pb : pb * P + pa) * 4) + A.cK[c];
      pairs.set(key, (pairs.get(key) || 0) + 1);
    }
    V = { counts, places, visE, nE, pairs, within, nC, tot };
  }

  // ---- projection and view -----------------------------------------------------------------------------------
  const W0 = 256;
  function project(lon, lat) {
    const f = Math.max(-85, Math.min(85, lat)) * Math.PI / 180;
    return [(lon + 180) / 360 * W0, (1 - Math.log(Math.tan(Math.PI / 4 + f / 2)) / Math.PI) / 2 * W0];
  }
  function unproject(x, y) {
    const lon = x / W0 * 360 - 180;
    const lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / W0))) * 180 / Math.PI;
    return [lon, lat];
  }
  const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
  let CW = 0, CH = 0, DPR = 1;
  const view = { cx: 0, cy: 0, z: 3 };
  const K = () => Math.pow(2, view.z);
  function toScreen(x, y) { const k = K(); return [(x - view.cx) * k + CW / 2, (y - view.cy) * k + CH / 2]; }
  function toWorld(sx, sy) { const k = K(); return [(sx - CW / 2) / k + view.cx, (sy - CH / 2) / k + view.cy]; }
  function minZ() { return Math.log2(Math.max(CW, 300) / W0) - 0.4; }
  function clampView() {
    view.z = Math.max(minZ(), Math.min(13, view.z));
    const k = K(), hw = CW / 2 / k, hh = CH / 2 / k;
    view.cx = hw * 2 >= W0 ? W0 / 2 : Math.max(hw, Math.min(W0 - hw, view.cx));
    view.cy = hh * 2 >= W0 * 0.86 ? W0 * 0.43 : Math.max(hh + W0 * 0.03, Math.min(W0 * 0.83 - hh, view.cy));
  }
  function fitBounds(w, s, e, n, pad) {
    const [x0, y1] = project(w, s), [x1, y0] = project(e, n);
    const p = pad === undefined ? 40 : pad;
    const zx = Math.log2((CW - 2 * p) / Math.max(x1 - x0, 1e-4)), zy = Math.log2((CH - 2 * p) / Math.max(y1 - y0, 1e-4));
    view.z = Math.min(zx, zy, 9);
    view.cx = (x0 + x1) / 2; view.cy = (y0 + y1) / 2;
    clampView();
  }
  function resize() {
    const r = cv.getBoundingClientRect();
    DPR = window.devicePixelRatio || 1;
    CW = r.width; CH = r.height;
    cv.width = Math.round(CW * DPR); cv.height = Math.round(CH * DPR);
    const tr = tl.getBoundingClientRect();
    tl.width = Math.round(tr.width * DPR); tl.height = Math.round(tr.height * DPR);
    if (A) { clampView(); render(); renderTimeline(); }
  }

  // ---- base map ----------------------------------------------------------------------------------------------
  let paths = null;
  function decodeLine(flat, q, path, close) {
    let x = 0, y = 0;
    for (let i = 0; i < flat.length; i += 2) {
      x += flat[i]; y += flat[i + 1];
      const [wx, wy] = project(x / q, y / q);
      if (i === 0) path.moveTo(wx, wy); else path.lineTo(wx, wy);
    }
    if (close) path.closePath();
  }
  function buildPaths(bm) {
    const q = bm.q, land = new Path2D(), lakes = new Path2D(), rivers = new Path2D(), country = [];
    for (const c of bm.countries) {
      const p = new Path2D();
      for (const r of c.p) decodeLine(r, q, p, true);
      land.addPath(p);
      country.push(p);
    }
    for (const r of bm.lakes) decodeLine(r, q, lakes, true);
    for (const l of bm.rivers) decodeLine(l, q, rivers, false);
    return { land, lakes, rivers, country };
  }

  // ---- colours -----------------------------------------------------------------------------------------------
  let C = {};
  function readColours() {
    C = {
      sea: css("--at-sea"), land: css("--at-land"), border: css("--at-border"), river: css("--at-river"),
      label: css("--at-label"), k: [css("--at-k0"), css("--at-k1"), css("--at-k2")], line: css("--at-line"),
      lineHi: css("--at-line-hi"), scrim: css("--at-scrim"), ring: css("--at-ring"), sel: css("--at-sel"),
      bar: css("--at-bar"), brush: css("--at-brush"), fg: css("--jl-fg"), muted: css("--jl-muted"),
      accent: css("--jl-accent"),
    };
  }

  // ---- map rendering -----------------------------------------------------------------------------------------
  let drawn = [];          // [p, sx, sy, r] of the drawn places, for hovering
  let drawRect = null;     // the rectangle being drawn (screen)
  let hoverP = -1;
  function radius(n) {
    const s = 0.5 * Math.pow(1.38, view.z - 4);
    return Math.min(5 + 3.2 * Math.max(view.z, 2), 1.6 + s * Math.sqrt(n));
  }
  let pending = false;
  function render() {
    if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; draw(); }); }
  }
  function draw() {
    if (!A || !paths) return;
    const k = K();
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.fillStyle = C.sea; ctx.fillRect(0, 0, CW, CH);
    // base map in world coordinates
    ctx.setTransform(DPR * k, 0, 0, DPR * k, DPR * (CW / 2 - view.cx * k), DPR * (CH / 2 - view.cy * k));
    ctx.fillStyle = C.land; ctx.fill(paths.land);
    ctx.fillStyle = C.sea; ctx.fill(paths.lakes);
    ctx.lineJoin = "round";
    if (view.z > 3.2) { ctx.strokeStyle = C.river; ctx.lineWidth = 0.9 / k; ctx.stroke(paths.rivers); }
    ctx.strokeStyle = C.border; ctx.lineWidth = 0.7 / k; ctx.stroke(paths.land);
    // outside the area: a scrim
    if (S.area) {
      ctx.fillStyle = C.scrim;
      if (S.area.type === "country") {
        const p = new Path2D(); p.rect(-W0, -W0, 3 * W0, 3 * W0); p.addPath(paths.country[S.area.i]);
        ctx.fill(p, "evenodd");
        ctx.strokeStyle = C.accent; ctx.lineWidth = 1.5 / k; ctx.stroke(paths.country[S.area.i]);
      } else {
        const [x0, y1] = project(S.area.w, S.area.s), [x1, y0] = project(S.area.e, S.area.n);
        const p = new Path2D(); p.rect(-W0, -W0, 3 * W0, 3 * W0); p.rect(x0, y0, x1 - x0, y1 - y0);
        ctx.fill(p, "evenodd");
        ctx.strokeStyle = C.accent; ctx.lineWidth = 1.5 / k; ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      }
    }
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    const selE = S.sel && S.sel.type === "entity" ? S.sel.i : -1;
    // connections
    if (S.rels.some(Boolean)) {
      ctx.lineCap = "round";
      for (const [key, n] of V.pairs) {
        const kind = key % 4, pair = Math.floor(key / 4), pa = Math.floor(pair / A.P), pb = pair % A.P;
        ctx.strokeStyle = C.line;
        ctx.globalAlpha = selE >= 0 ? 0.25 : 0.6;
        ctx.lineWidth = Math.min(4, 0.6 + Math.log2(n) * 0.6);
        ctx.setLineDash(REL_DASH[A.relKinds[kind]]);
        arc(pa, pb, kind);
      }
      ctx.globalAlpha = 1; ctx.setLineDash([]);
    }
    // places
    drawn = [];
    const order = V.places;
    for (let o = 0; o < order.length; o++) {
      const p = order[o];
      const [sx, sy] = toScreen(A.px[p], A.py[p]);
      const tot = V.tot(p);
      const R = radius(tot);
      if (sx < -R || sy < -R || sx > CW + R || sy > CH + R) continue;
      const ks = [0, 1, 2].filter((kk) => V.counts[p * 3 + kk] > 0).sort((a, b) => V.counts[p * 3 + b] - V.counts[p * 3 + a]);
      for (const kk of ks) {
        const r = radius(V.counts[p * 3 + kk]);
        ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2 * Math.PI);
        ctx.fillStyle = C.k[kk]; ctx.globalAlpha = 0.88; ctx.fill(); ctx.globalAlpha = 1;
        ctx.lineWidth = r > 3 ? 1.5 : 1; ctx.strokeStyle = C.ring; ctx.stroke();
      }
      drawn.push([p, sx, sy, R]);
    }
    // the selection
    if (selE >= 0) drawEntity(selE);
    if (S.sel && S.sel.type === "place") ringAt(S.sel.i, C.sel, 2.5);
    if (hoverP >= 0) ringAt(hoverP, C.sel, 1.5);
    drawLabels();
    if (drawRect) {
      ctx.strokeStyle = C.accent; ctx.lineWidth = 1.5; ctx.setLineDash([5, 4]);
      ctx.strokeRect(drawRect[0], drawRect[1], drawRect[2] - drawRect[0], drawRect[3] - drawRect[1]);
      ctx.setLineDash([]);
    }
  }
  function arc(pa, pb) {
    const [x0, y0] = toScreen(A.px[pa], A.py[pa]), [x1, y1] = toScreen(A.px[pb], A.py[pb]);
    const mx = (x0 + x1) / 2, my = (y0 + y1) / 2, dx = x1 - x0, dy = y1 - y0;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo(mx - dy * 0.18, my + dx * 0.18, x1, y1); ctx.stroke();
  }
  function ringAt(p, colour, w) {
    const [sx, sy] = toScreen(A.px[p], A.py[p]);
    const r = Math.max(5, radius(V.tot(p) || 1)) + 3;
    ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2 * Math.PI);
    ctx.lineWidth = w + 2; ctx.strokeStyle = C.ring; ctx.stroke();
    ctx.lineWidth = w; ctx.strokeStyle = colour; ctx.stroke();
  }
  function entityPlaces(i) {
    const out = [];
    for (let j = A.po[i]; j < A.po[i + 1]; j++) out.push(j);
    const rank = (j) => { const k = LIFE_ORDER.indexOf(A.roles[A.plR[j]]); return k < 0 ? 9 : k; };
    return out.sort((a, b) => rank(a) - rank(b) || (A.plY[a] || 0) - (A.plY[b] || 0));
  }
  function drawEntity(i) {
    // the entity's connections, then the way through its places, then its places
    ctx.lineWidth = 2; ctx.strokeStyle = C.lineHi;
    for (let a = A.aStart[i]; a < A.aStart[i + 1]; a++) {
      const c = A.aList[a], o = A.cA[c] === i ? A.cB[c] : A.cA[c];
      if (!S.rels[A.cK[c]]) continue;
      ctx.setLineDash(REL_DASH[A.relKinds[A.cK[c]]]);
      if (A.prim[i] !== A.prim[o]) arc(A.prim[i], A.prim[o]);
      ctx.setLineDash([]);
      ringAt(A.prim[o], C.lineHi, 1.5);
    }
    const js = entityPlaces(i);
    ctx.strokeStyle = C.k[A.kind[i]]; ctx.lineWidth = 2.5;
    ctx.beginPath();
    js.forEach((j, n) => {
      const [sx, sy] = toScreen(A.px[A.plP[j]], A.py[A.plP[j]]);
      if (n === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
    });
    ctx.stroke();
    for (const j of js) {
      const [sx, sy] = toScreen(A.px[A.plP[j]], A.py[A.plP[j]]);
      ctx.beginPath(); ctx.arc(sx, sy, 6, 0, 2 * Math.PI);
      ctx.fillStyle = C.k[A.kind[i]]; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = C.sel; ctx.stroke();
    }
  }
  function drawLabels() {
    ctx.font = "12px system-ui, -apple-system, 'Segoe UI', sans-serif";
    ctx.textBaseline = "middle";
    const boxes = [];
    const want = [];
    if (S.sel && S.sel.type === "place") want.push(S.sel.i);
    if (S.sel && S.sel.type === "entity") for (const j of entityPlaces(S.sel.i)) want.push(A.plP[j]);
    const limit = Math.max(12, Math.round(CW * CH / 26000));
    for (const d of drawn.slice().sort((a, b) => b[3] - a[3]).slice(0, limit)) want.push(d[0]);
    const seen = new Set();
    for (const p of want) {
      if (seen.has(p)) continue;
      seen.add(p);
      const [sx, sy] = toScreen(A.px[p], A.py[p]);
      if (sx < 0 || sy < 0 || sx > CW || sy > CH) continue;
      const r = Math.max(4, radius(V.tot(p) || 1));
      const t = A.plabel[p], w = ctx.measureText(t).width;
      const box = [sx + r + 3, sy - 8, sx + r + 5 + w, sy + 8];
      if (boxes.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
      boxes.push(box);
      ctx.lineWidth = 3; ctx.strokeStyle = C.land; ctx.lineJoin = "round";
      ctx.strokeText(t, box[0], sy); ctx.fillStyle = C.label; ctx.fillText(t, box[0], sy);
    }
  }

  // ---- map interaction ---------------------------------------------------------------------------------------
  const tip = document.getElementById("tip");
  let drawing = false;
  const pointers = new Map();
  let dragStart = null, pinch = null, moved = false;
  function placeAt(sx, sy) {
    let best = -1, bestR = Infinity, near = -1, nearD = 14;
    for (const [p, x, y, r] of drawn) {
      const d = Math.hypot(sx - x, sy - y);
      if (d <= r + 3 && r < bestR) { best = p; bestR = r; }
      if (d < nearD) { near = p; nearD = d; }
    }
    return best >= 0 ? best : near;
  }
  function showTip(p, sx, sy) {
    if (p < 0) { tip.hidden = true; return; }
    tip.replaceChildren(el("b", { text: A.plabel[p] }));
    for (let k = 0; k < 3; k++) {
      const n = V.counts[p * 3 + k];
      if (!n) continue;
      const i = el("i"); i.style.background = C.k[k];
      tip.append(el("div", { class: "at-row" }, i, el("strong", { text: fmt(n) }), " " + plural(n, k)));
    }
    if (V.within[p]) tip.append(el("div", { class: "at-muted", text: `${fmt(V.within[p])} connections within the place` }));
    tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(CW - w - 6, sx + 14) + "px";
    tip.style.top = Math.max(6, sy - h - 10) + "px";
  }
  cv.addEventListener("pointerdown", (ev) => {
    cv.setPointerCapture(ev.pointerId);
    pointers.set(ev.pointerId, [ev.offsetX, ev.offsetY]);
    moved = false;
    if (drawing) { drawRect = [ev.offsetX, ev.offsetY, ev.offsetX, ev.offsetY]; return; }
    if (pointers.size === 1) dragStart = [ev.offsetX, ev.offsetY, view.cx, view.cy];
    else if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = [Math.hypot(a[0] - b[0], a[1] - b[1]), view.z];
      dragStart = null;
    }
  });
  cv.addEventListener("pointermove", (ev) => {
    if (!A) return;
    if (pointers.has(ev.pointerId)) pointers.set(ev.pointerId, [ev.offsetX, ev.offsetY]);
    if (drawing && drawRect) { drawRect[2] = ev.offsetX; drawRect[3] = ev.offsetY; render(); return; }
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      zoomAt((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, pinch[1] + Math.log2(d / pinch[0]) - view.z);
      moved = true;
      return;
    }
    if (dragStart && pointers.size === 1) {
      const dx = ev.offsetX - dragStart[0], dy = ev.offsetY - dragStart[1];
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      if (moved) {
        cv.classList.add("at-dragging");
        view.cx = dragStart[2] - dx / K(); view.cy = dragStart[3] - dy / K();
        clampView(); tip.hidden = true; render(); saveSoon();
      }
      return;
    }
    const p = placeAt(ev.offsetX, ev.offsetY);
    if (p !== hoverP) { hoverP = p; render(); }
    cv.classList.toggle("at-hover", p >= 0);
    showTip(p, ev.offsetX, ev.offsetY);
  });
  function endPointer(ev) {
    pointers.delete(ev.pointerId);
    cv.classList.remove("at-dragging");
    if (drawing && drawRect) {
      const [x0, y0, x1, y1] = drawRect;
      drawRect = null;
      setDrawing(false);
      if (Math.abs(x1 - x0) > 8 && Math.abs(y1 - y0) > 8) {
        const [w, n] = unproject(...toWorld(Math.min(x0, x1), Math.min(y0, y1)));
        const [e, s] = unproject(...toWorld(Math.max(x0, x1), Math.max(y0, y1)));
        setArea({ type: "box", w: +w.toFixed(2), s: +s.toFixed(2), e: +e.toFixed(2), n: +n.toFixed(2) }, false);
      } else render();
      return;
    }
    if (pointers.size < 2) pinch = null;
    if (ev.type === "pointerup" && !moved && pointers.size === 0 && dragStart) {
      const p = placeAt(ev.offsetX, ev.offsetY);
      select(p >= 0 ? { type: "place", i: p } : null);
    }
    if (pointers.size === 0) dragStart = null;
  }
  cv.addEventListener("pointerup", endPointer);
  cv.addEventListener("pointercancel", endPointer);
  cv.addEventListener("pointerleave", () => { if (hoverP >= 0) { hoverP = -1; render(); } tip.hidden = true; });
  function zoomAt(sx, sy, dz) {
    const [wx, wy] = toWorld(sx, sy);
    view.z += dz; clampView();
    const k = K();
    view.cx = wx - (sx - CW / 2) / k; view.cy = wy - (sy - CH / 2) / k;
    clampView(); render(); saveSoon();
  }
  cv.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const dz = -ev.deltaY * (ev.deltaMode === 1 ? 0.05 : 0.0022);
    zoomAt(ev.offsetX, ev.offsetY, Math.max(-1, Math.min(1, dz)));
  }, { passive: false });
  cv.addEventListener("dblclick", (ev) => zoomAt(ev.offsetX, ev.offsetY, ev.shiftKey ? -1 : 1));
  cv.addEventListener("keydown", (ev) => {
    const step = 80 / K();
    const keys = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (keys[ev.key]) { view.cx += keys[ev.key][0]; view.cy += keys[ev.key][1]; clampView(); render(); saveSoon(); }
    else if (ev.key === "+" || ev.key === "=") zoomAt(CW / 2, CH / 2, 0.5);
    else if (ev.key === "-") zoomAt(CW / 2, CH / 2, -0.5);
    else if (ev.key === "Escape") { setDrawing(false); select(null); }
    else return;
    ev.preventDefault();
  });
  document.getElementById("z-in").onclick = () => zoomAt(CW / 2, CH / 2, 1);
  document.getElementById("z-out").onclick = () => zoomAt(CW / 2, CH / 2, -1);
  document.getElementById("z-fit").onclick = () => fitSelection();
  function fitSelection() {
    if (S.sel && S.sel.type === "entity") {
      const js = entityPlaces(S.sel.i), ps = js.map((j) => A.plP[j]);
      for (let a = A.aStart[S.sel.i]; a < A.aStart[S.sel.i + 1]; a++) {
        const c = A.aList[a]; ps.push(A.prim[A.cA[c]], A.prim[A.cB[c]]);
      }
      fitPlaces(ps);
    } else if (S.sel && S.sel.type === "place") {
      const p = S.sel.i;
      view.cx = A.px[p]; view.cy = A.py[p]; view.z = Math.max(view.z, 7); clampView();
    } else if (S.area) fitArea();
    else fitPlaces(V.places.slice(0, 400));
    render(); saveSoon();
  }
  function fitPlaces(ps) {
    if (!ps.length) return;
    let w = 180, e = -180, s = 90, n = -90;
    for (const p of ps) { w = Math.min(w, A.lon[p]); e = Math.max(e, A.lon[p]); s = Math.min(s, A.lat[p]); n = Math.max(n, A.lat[p]); }
    const padLon = Math.max(0.4, (e - w) * 0.1), padLat = Math.max(0.3, (n - s) * 0.1);
    fitBounds(w - padLon, s - padLat, e + padLon, n + padLat, 50);
  }
  function fitArea() {
    const a = S.area;
    if (a.type === "box") fitBounds(a.w, a.s, a.e, a.n);
    else {
      const b = BM.countries[a.i].b;
      // countries across the date line or with far territories: fit their places instead
      const ps = [];
      for (let p = 0; p < A.P; p++) if (A.pcountry[p] === a.i) ps.push(p);
      if (b[2] - b[0] > 90 && ps.length) fitPlaces(ps); else fitBounds(b[0], b[1], b[2], b[3]);
    }
  }

  // ---- timeline ----------------------------------------------------------------------------------------------
  const tl = document.getElementById("tl"), tctx = tl.getContext("2d");
  const T0 = 1000, TB = 1500, T1 = 2030, F_EARLY = 0.035, F_BREAK = 0.2;
  const BINS = 1 + (T1 - T0) / 10;    // bin 0: before 1000; then decades
  let hist = null;
  function yearToF(y) {
    if (y === null || y < T0) return F_EARLY * 0.5;
    if (y < TB) return F_EARLY + (y - T0) / (TB - T0) * (F_BREAK - F_EARLY);
    return F_BREAK + (Math.min(y, T1) - TB) / (T1 - TB) * (1 - F_BREAK);
  }
  function fToYear(f) {
    if (f < F_EARLY) return null;
    if (f < F_BREAK) return Math.round(T0 + (f - F_EARLY) / (F_BREAK - F_EARLY) * (TB - T0));
    return Math.round(TB + (f - F_BREAK) / (1 - F_BREAK) * (T1 - TB));
  }
  function binOf(y) { return y < T0 ? 0 : Math.min(BINS - 1, 1 + Math.floor((y - T0) / 10)); }
  function binF(b) { return b === 0 ? [0, F_EARLY] : [yearToF(T0 + (b - 1) * 10), yearToF(T0 + b * 10)]; }
  function computeHist() {
    hist = new Float32Array(BINS * 3);
    for (let i = 0; i < A.N; i++) {
      const k = A.kind[i];
      if (!S.kinds[k]) continue;
      if (inArea) {
        let ok = false;
        for (let j = A.po[i]; j < A.po[i + 1]; j++) if (inArea[A.plP[j]]) { ok = true; break; }
        if (!ok) continue;
      }
      const b1 = binOf(A.end[i]);
      for (let b = binOf(A.start[i]); b <= b1; b++) hist[b * 3 + k]++;
    }
  }
  function renderTimeline() {
    if (!hist) return;
    const W = tl.width / DPR, H = tl.height / DPR, top = 4, axis = 16, hh = H - top - axis;
    tctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    tctx.clearRect(0, 0, W, H);
    let max = 1;
    for (let b = 0; b < BINS; b++) max = Math.max(max, hist[b * 3] + hist[b * 3 + 1] + hist[b * 3 + 2]);
    // the window
    const fx = yearToF(S.from) * W, tx = yearToF(S.to) * W;
    tctx.fillStyle = C.brush; tctx.fillRect(S.from === null ? 0 : fx, 0, tx - (S.from === null ? 0 : fx), H - axis + 2);
    for (let b = 0; b < BINS; b++) {
      const [f0, f1] = binF(b);
      const x0 = f0 * W, x1 = f1 * W, gap = x1 - x0 > 4 ? 1 : 0.5;
      let y = top + hh;
      const lo = b === 0 ? -Infinity : T0 + (b - 1) * 10, hi = b === 0 ? T0 - 1 : lo + 9;
      const inside = hi >= (S.from === null ? EARLIEST : S.from) && lo <= S.to;
      for (let k = 0; k < 3; k++) {
        const v = hist[b * 3 + k];
        if (!v) continue;
        const h = v / max * hh;
        tctx.fillStyle = inside ? C.k[k] : C.bar;
        tctx.fillRect(x0 + gap / 2, y - h, Math.max(0.5, x1 - x0 - gap), h);
        y -= h;
      }
    }
    // axis
    tctx.fillStyle = C.muted; tctx.font = "11px system-ui, -apple-system, 'Segoe UI', sans-serif";
    tctx.textBaseline = "top"; tctx.textAlign = "center";
    tctx.fillRect(0, H - axis, W, 1);
    tctx.textAlign = "left"; tctx.fillText("earlier", 0, H - axis + 4); tctx.textAlign = "center";
    let lastX = 40;
    for (const y of [1200, 1400, 1500, 1600, 1700, 1800, 1850, 1900, 1950, 2000]) {
      const x = yearToF(y) * W;
      tctx.fillRect(x, H - axis, 1, 4);
      if (x - lastX < 36) continue;
      tctx.fillText(String(y), Math.max(14, Math.min(W - 14, x)), H - axis + 4);
      lastX = x;
    }
    // handles
    tctx.fillStyle = C.accent;
    for (const x of [S.from === null ? 2 : fx, tx]) {
      tctx.fillRect(x - 1, 0, 2, H - axis + 2);
      tctx.beginPath(); tctx.roundRect(x - 4, (H - axis) / 2 - 9, 8, 18, 3); tctx.fill();
    }
  }
  let tdrag = null;
  tl.addEventListener("pointerdown", (ev) => {
    tl.setPointerCapture(ev.pointerId);
    const W = tl.width / DPR, x = ev.offsetX;
    const fx = S.from === null ? 2 : yearToF(S.from) * W, tx = yearToF(S.to) * W;
    if (Math.abs(x - fx) < 9 && Math.abs(x - fx) <= Math.abs(x - tx)) tdrag = { h: "from" };
    else if (Math.abs(x - tx) < 9) tdrag = { h: "to" };
    else if (x > fx && x < tx) tdrag = { h: "move", x, from: S.from, to: S.to };
    else {
      const y = fToYear(x / W), w = S.to - (S.from === null ? 1000 : S.from);
      if (y === null) setTime(null, S.to);
      else setTime(Math.round(y - w / 2), Math.round(y + w / 2));
      tdrag = { h: "move", x, from: S.from, to: S.to };
    }
  });
  tl.addEventListener("pointermove", (ev) => {
    if (!tdrag) return;
    const W = tl.width / DPR, y = fToYear(Math.max(0, Math.min(1, ev.offsetX / W)));
    if (tdrag.h === "from") setTime(y === null ? null : Math.min(y, S.to), S.to);
    else if (tdrag.h === "to") setTime(S.from, Math.max(y === null ? T0 : y, S.from === null ? T0 : S.from));
    else {
      const y0 = fToYear(tdrag.x / W), d = (y === null || y0 === null) ? 0 : y - y0;
      if (tdrag.from === null) setTime(null, tdrag.to + d);
      else setTime(tdrag.from + d, tdrag.to + d);
    }
  });
  const endT = () => { tdrag = null; };
  tl.addEventListener("pointerup", endT);
  tl.addEventListener("pointercancel", endT);
  tl.addEventListener("keydown", (ev) => {
    const d = ev.shiftKey ? 10 : 1;
    if (ev.key === "ArrowLeft") setTime(S.from === null ? null : S.from - d, S.to - d);
    else if (ev.key === "ArrowRight") setTime(S.from === null ? null : S.from + d, S.to + d);
    else return;
    ev.preventDefault();
  });

  // ---- filters -----------------------------------------------------------------------------------------------
  const fFrom = document.getElementById("f-from"), fTo = document.getElementById("f-to");
  const fArea = document.getElementById("f-area"), fDraw = document.getElementById("f-draw");
  const fMode = document.getElementById("f-mode"), fPlay = document.getElementById("f-play");
  fFrom.placeholder = "earliest";
  function setTime(from, to) {
    if (to > NOW) { if (from !== null) from -= to - NOW; to = NOW; }
    if (from !== null && from < T0 - 1) from = null;
    if (to < T0) to = T0;
    if (from !== null && from > to) from = to;
    S.from = from; S.to = to;
    fFrom.value = from === null ? "" : from; fTo.value = to;
    update(false);
  }
  fFrom.addEventListener("change", () => setTime(fFrom.value === "" ? null : Math.round(+fFrom.value), S.to));
  fTo.addEventListener("change", () => setTime(S.from, Math.round(+fTo.value || NOW)));
  function setArea(area, fit) {
    S.area = area;
    inArea = areaTest();
    const boxOpt = fArea.querySelector('option[value="box"]');
    boxOpt.disabled = !(area && area.type === "box");
    fArea.value = !area ? "" : area.type === "box" ? "box" : "c" + area.i;
    if (fit !== false && area) fitArea();
    update(true);
  }
  fArea.addEventListener("change", () => {
    const v = fArea.value;
    setArea(v === "" ? null : v === "box" ? S.area : { type: "country", i: +v.slice(1) });
  });
  function setDrawing(on) {
    drawing = on;
    fDraw.setAttribute("aria-pressed", on ? "true" : "false");
    cv.classList.toggle("at-drawing", on);
    if (on) cv.focus();
  }
  fDraw.onclick = () => setDrawing(!drawing);
  fMode.addEventListener("change", () => { S.mode = fMode.value; update(false); });
  for (let k = 0; k < 3; k++) {
    document.getElementById("k-" + k).addEventListener("change", (ev) => { S.kinds[k] = ev.target.checked; update(true); });
  }
  for (let k = 0; k < 4; k++) {
    document.getElementById("r-" + k).addEventListener("change", (ev) => { S.rels[k] = ev.target.checked; update(false); });
  }
  let playing = null;
  fPlay.onclick = () => {
    if (playing) { stopPlay(); return; }
    if (S.to >= NOW) setTime(S.from === null ? null : 1700, S.from === null ? S.to - (NOW - 1700) : 1700 + (S.to - S.from));
    fPlay.setAttribute("aria-pressed", "true"); fPlay.textContent = "Pause";
    let last = performance.now(), acc = 0;
    const step = (t) => {
      acc += (t - last) / 1000 * 8; last = t;      // eight years a second
      if (acc >= 1) {
        const d = Math.floor(acc); acc -= d;
        if (S.to + d > NOW) { setTime(S.from === null ? null : S.from + (NOW - S.to), NOW); stopPlay(); return; }
        setTime(S.from === null ? null : S.from + d, S.to + d);
      }
      playing = requestAnimationFrame(step);
    };
    playing = requestAnimationFrame(step);
  };
  function stopPlay() {
    if (playing) cancelAnimationFrame(playing);
    playing = null; fPlay.setAttribute("aria-pressed", "false"); fPlay.textContent = "Play";
  }

  function update(histToo) {
    if (!A) return;
    if (histToo || !hist) computeHist();
    compute();
    render(); renderTimeline(); renderPanel(); renderLegend(); saveSoon();
  }

  // ---- panel -------------------------------------------------------------------------------------------------
  const panel = document.getElementById("panel");
  function timeText() {
    return S.from === null ? `until ${S.to}` : S.from === S.to ? `in ${S.from}` : `${S.from}–${S.to}`;
  }
  function areaText() {
    if (!S.area) return "the whole world";
    return S.area.type === "country" ? A.countries[S.area.i] : "the drawn area";
  }
  function years(i) {
    const s = A.start[i], e = A.end[i], f = A.flags[i], k = A.kind[i];
    if (k === 1 && (f & 2)) return `est. ${s}`;
    if (k === 1 && (f & 1)) return `until ${e}`;
    if (s === e && !f) return String(s);
    return `${f & 1 ? "?" : s}–${f & 2 ? "?" : e}`;
  }
  function selectLink(text, sel, cls) {
    return el("button", { type: "button", class: "at-link" + (cls ? " " + cls : ""), text, onclick: () => select(sel, true) });
  }
  function dot(k) { const d = el("span", { class: "at-dot" }); d.style.background = C.k[k]; return d; }
  function renderPanel() {
    panel.replaceChildren();
    if (S.sel && S.sel.type === "place") return placePanel(S.sel.i);
    if (S.sel && S.sel.type === "entity") return entityPanel(S.sel.i);
    overviewPanel();
  }
  function overviewPanel() {
    const n = V.nE;
    const parts = [0, 1, 2].filter((k) => S.kinds[k]).map((k) => [el("strong", { text: fmt(n[k]) }), " " + plural(n[k], k)]);
    const sum = el("p", { class: "at-sum" });
    parts.forEach((p, i) => { if (i) sum.append(i === parts.length - 1 ? " and " : ", "); sum.append(...p); });
    sum.append(` at ${fmt(V.places.length)} places, ${timeText()}, in ${areaText()}`);
    if (V.nC) sum.append(`, with ${fmt(V.nC)} connections`);
    sum.append(".");
    panel.append(el("h2", { text: "In the selection" }), sum);
    if (!V.places.length) {
      panel.append(el("p", { class: "at-hint", text: "Nothing on the map for this time and area. Widen the time window or the area." }));
      return;
    }
    const tb = el("tbody");
    for (const p of V.places.slice(0, 60)) {
      const tr = el("tr", null, el("td", null, selectLink(A.plabel[p], { type: "place", i: p })));
      for (let k = 0; k < 3; k++) tr.append(el("td", { class: "num", text: V.counts[p * 3 + k] ? fmt(V.counts[p * 3 + k]) : "" }));
      tb.append(tr);
    }
    const head = el("tr", null, el("th", { text: "Place" }));
    ["People", "Org.", "Publ."].forEach((t, k) => head.append(el("th", { class: "num", text: t, title: KIND_PLURAL[k] })));
    panel.append(el("h3", { text: V.places.length > 60 ? `The 60 places with most entities (of ${fmt(V.places.length)})` : "Places" }),
      el("table", null, el("thead", null, head), tb),
      el("p", { class: "at-hint" }, "Select a place on the map or in this list for its entities, and an entity for its places and connections. ",
        el("a", { href: BASE + "about/", text: "How the map is made" })));
  }
  function placePanel(p) {
    const close = el("button", { type: "button", class: "at-btn at-close", text: "Close", onclick: () => select(null) });
    const cname = A.pcountry[p] >= 0 ? A.countries[A.pcountry[p]] : "";
    panel.append(close, el("h2", { text: A.plabel[p] }),
      el("p", { class: "at-hint" }, cname ? `${cname} (today) · ` : "",
        el("a", { href: viewHref(A.pid[p]), text: "View in JudaicaLink" })));
    // the entities at the place in the time window, by kind
    const rows = [[], [], []];
    const seen = new Map();
    for (let q = A.pStart[p]; q < A.pStart[p + 1]; q++) {
      const j = A.pList[q], i = A.plE[j];
      if (!S.kinds[A.kind[i]] || !inTime(j)) continue;
      if (!seen.has(i)) { seen.set(i, []); rows[A.kind[i]].push(i); }
      seen.get(i).push(A.roles[A.plR[j]]);
    }
    if (!seen.size) {
      panel.append(el("p", { class: "at-hint", text: `Nothing here ${timeText()}.` }));
    }
    for (let k = 0; k < 3; k++) {
      if (!rows[k].length) continue;
      rows[k].sort((a, b) => A.start[a] - A.start[b] || A.label[a].localeCompare(A.label[b]));
      const ul = el("ul");
      const show = (from) => {
        for (const i of rows[k].slice(from, from + 100)) {
          ul.append(el("li", null, dot(k), selectLink(A.label[i] || "(no name)", { type: "entity", i }),
            el("span", { class: "at-meta", text: `${[...new Set(seen.get(i))].map((r) => ROLE_LABEL[r]).join(", ")} · ${years(i)}` })));
        }
      };
      show(0);
      panel.append(el("h3", { text: `${fmt(rows[k].length)} ${plural(rows[k].length, k)} ${timeText()}` }), ul);
      if (rows[k].length > 100) {
        let shown = 100;
        const more = el("button", { type: "button", class: "at-btn at-more", text: "Show 100 more" });
        more.onclick = () => { show(shown); shown += 100; if (shown >= rows[k].length) more.remove(); };
        panel.append(more);
      }
    }
    if (V.within[p]) panel.append(el("p", { class: "at-hint", text: `${fmt(V.within[p])} connections between entities of this place.` }));
  }
  function entityPanel(i) {
    const k = A.kind[i];
    const close = el("button", { type: "button", class: "at-btn at-close", text: "Close", onclick: () => select(null) });
    const est = A.flags[i] && k === 0 ? el("span", { class: "at-est", text: ` (life estimated: ${A.raw.lifespan} years from the known year)` }) : null;
    panel.append(close, el("h2", { text: A.label[i] || "(no name)" }),
      el("p", null, dot(k), " ", KIND_ONE[k][0].toUpperCase() + KIND_ONE[k].slice(1) + " · " + years(i), est),
      el("p", null, el("a", { href: viewHref(A.id[i]), text: "View in JudaicaLink" })));
    let visible = false;
    for (let j = A.po[i]; j < A.po[i + 1]; j++) if (inTime(j) && (!inArea || inArea[A.plP[j]])) visible = true;
    if (!visible) {
      panel.append(el("p", { class: "at-hint" }, `Not in the selected time and area. `,
        el("button", { type: "button", class: "at-link", text: `Show ${years(i)}`, onclick: () => {
          setTime(A.start[i] - 1, Math.min(NOW, Math.max(A.end[i], A.start[i]) + 1)); if (S.area) setArea(null, false); fitSelection();
        } })));
    }
    const ul = el("ul");
    for (const j of entityPlaces(i)) {
      const p = A.plP[j], role = A.roles[A.plR[j]];
      let when = "";
      if (A.plY[j]) when = String(A.plY[j]);
      else if (role === "birth" && !(A.flags[i] & 1)) when = String(A.start[i]);
      else if ((role === "death" || role === "burial") && !(A.flags[i] & 2)) when = String(A.end[i]);
      ul.append(el("li", null, selectLink(A.plabel[p], { type: "place", i: p }),
        el("span", { class: "at-meta", text: ROLE_LABEL[role] + (when ? " " + when : "") })));
    }
    panel.append(el("h3", { text: "Places" }), ul);
    const n = A.aStart[i + 1] - A.aStart[i];
    if (n) {
      const cl = el("ul");
      const items = [];
      for (let a = A.aStart[i]; a < A.aStart[i + 1]; a++) {
        const c = A.aList[a], o = A.cA[c] === i ? A.cB[c] : A.cA[c];
        items.push([o, A.relKinds[A.cK[c]]]);
      }
      items.sort((x, y) => x[1].localeCompare(y[1]) || A.start[x[0]] - A.start[y[0]]);
      for (const [o, kind] of items) {
        cl.append(el("li", null, dot(A.kind[o]), selectLink(A.label[o] || "(no name)", { type: "entity", i: o }),
          el("span", { class: "at-meta", text: `${REL_LABEL[kind]} · ${years(o)}` })));
      }
      panel.append(el("h3", { text: `${fmt(n)} connection${n === 1 ? "" : "s"}` }), cl);
    }
  }
  function renderLegend() {
    const lg = document.getElementById("sizes");
    lg.replaceChildren();
    const svgNS = "http://www.w3.org/2000/svg";
    const sizes = [10, 100, 1000].filter((n) => radius(n) < 40);
    const row = el("div");
    for (const n of sizes) {
      const r = radius(n);
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("width", 2 * r + 4); svg.setAttribute("height", 2 * r + 4);
      const c = document.createElementNS(svgNS, "circle");
      c.setAttribute("cx", r + 2); c.setAttribute("cy", r + 2); c.setAttribute("r", r);
      c.setAttribute("fill", "none"); c.setAttribute("stroke", C.muted);
      svg.append(c);
      row.append(svg, fmt(n) + " ");
    }
    lg.append(el("div", { text: "Entities at a place" }), row);
  }

  // ---- selection ---------------------------------------------------------------------------------------------
  function select(sel, fit) {
    S.sel = sel;
    renderPanel(); render(); saveSoon();
    if (fit && sel && sel.type === "entity") {
      // keep the view if all its places are already in it
      const js = entityPlaces(sel.i);
      const off = js.some((j) => { const [x, y] = toScreen(A.px[A.plP[j]], A.py[A.plP[j]]); return x < 20 || y < 20 || x > CW - 20 || y > CH - 20; });
      if (off) fitSelection();
    }
    if (fit && sel && sel.type === "place") {
      const [x, y] = toScreen(A.px[sel.i], A.py[sel.i]);
      if (x < 20 || y < 20 || x > CW - 20 || y > CH - 20) { view.cx = A.px[sel.i]; view.cy = A.py[sel.i]; clampView(); render(); }
    }
  }

  // ---- search ------------------------------------------------------------------------------------------------
  const q = document.getElementById("f-q"), list = document.getElementById("f-q-list");
  let folded = null, pfolded = null, hits = [], active = -1;
  function search(text) {
    const t = fold(text.trim());
    if (t.length < 2) return [];
    if (!folded) { folded = A.label.map((s) => fold(s || "")); pfolded = A.plabel.map((s) => fold(s || "")); }
    const out = [];
    const push = (score, item) => out.push([score, item]);
    for (let p = 0; p < A.P; p++) {
      const at = pfolded[p].indexOf(t);
      if (at >= 0) push((at === 0 ? 0 : 2) - 0.5, { type: "place", i: p });
    }
    for (let i = 0; i < A.N && out.length < 4000; i++) {
      const at = folded[i].indexOf(t);
      if (at >= 0) push(at === 0 ? 0 : (folded[i][at - 1] === " " || folded[i][at - 1] === "," ? 1 : 2), { type: "entity", i });
    }
    out.sort((a, b) => a[0] - b[0] || labelOf(a[1]).length - labelOf(b[1]).length);
    return out.slice(0, 14).map((x) => x[1]);
  }
  const labelOf = (s) => s.type === "place" ? A.plabel[s.i] : A.label[s.i];
  function showHits() {
    list.replaceChildren();
    hits.forEach((h, n) => {
      const meta = h.type === "place" ? "place" : `${KIND_ONE[A.kind[h.i]]} · ${years(h.i)}`;
      const li = el("li", { role: "option", id: "hit-" + n, "aria-selected": n === active ? "true" : "false" },
        h.type === "entity" ? dot(A.kind[h.i]) : null, el("span", { text: labelOf(h) }), el("small", { text: meta }));
      li.addEventListener("mousedown", (ev) => { ev.preventDefault(); choose(n); });
      list.append(li);
    });
    list.hidden = !hits.length;
    q.setAttribute("aria-expanded", hits.length ? "true" : "false");
    q.setAttribute("aria-activedescendant", active >= 0 ? "hit-" + active : "");
  }
  function choose(n) {
    const h = hits[n];
    if (!h) return;
    hits = []; showHits(); q.value = labelOf(h);
    select(h, true);
    if (h.type === "entity") {
      let visible = false;
      for (let j = A.po[h.i]; j < A.po[h.i + 1]; j++) if (inTime(j)) visible = true;
      if (!visible) setTime(A.start[h.i] - 1, Math.min(NOW, A.end[h.i] + 1));
      fitSelection();
    }
  }
  let qTimer = null;
  q.addEventListener("input", () => {
    clearTimeout(qTimer);
    qTimer = setTimeout(() => { if (!A) return; hits = search(q.value); active = -1; showHits(); }, 120);
  });
  q.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") { active = Math.min(hits.length - 1, active + 1); showHits(); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { active = Math.max(-1, active - 1); showHits(); ev.preventDefault(); }
    else if (ev.key === "Enter") { choose(active >= 0 ? active : 0); ev.preventDefault(); }
    else if (ev.key === "Escape") { hits = []; showHits(); }
  });
  q.addEventListener("blur", () => setTimeout(() => { hits = []; showHits(); }, 150));

  // ---- the address keeps the state ---------------------------------------------------------------------------
  let saveTimer = null;
  function saveSoon() { clearTimeout(saveTimer); saveTimer = setTimeout(save, 300); }
  function save() {
    const h = new URLSearchParams();
    h.set("t", `${S.from === null ? "" : S.from}-${S.to}`);
    if (S.area) h.set("a", S.area.type === "country" ? "c:" + BM.countries[S.area.i].c : `b:${S.area.w},${S.area.s},${S.area.e},${S.area.n}`);
    if (!S.kinds.every(Boolean)) h.set("k", S.kinds.map(Number).join(""));
    if (S.mode !== "life") h.set("m", "e");
    if (!S.rels.every(Boolean)) h.set("r", S.rels.map(Number).join(""));
    if (S.sel) h.set("s", (S.sel.type === "place" ? "p:" + A.pid[S.sel.i] : "e:" + A.id[S.sel.i]));
    const [lon, lat] = unproject(view.cx, view.cy);
    h.set("v", `${lon.toFixed(2)},${lat.toFixed(2)},${view.z.toFixed(2)}`);
    history.replaceState(null, "", location.pathname + "#" + h.toString());
  }
  function load() {
    const h = new URLSearchParams(location.hash.slice(1));
    const t = (h.get("t") || "").match(/^(-?\d*)-(-?\d+)$/);
    if (t) { S.from = t[1] === "" ? null : +t[1]; S.to = +t[2]; }
    const a = h.get("a") || "";
    if (a.startsWith("c:")) {
      const i = BM.countries.findIndex((c) => c.c === a.slice(2));
      if (i >= 0) S.area = { type: "country", i };
    } else if (a.startsWith("b:")) {
      const [w, s, e, n] = a.slice(2).split(",").map(Number);
      if ([w, s, e, n].every(Number.isFinite)) S.area = { type: "box", w, s, e, n };
    }
    const k = h.get("k");
    if (k && /^[01]{3}$/.test(k)) S.kinds = [...k].map((c) => c === "1");
    if (h.get("m") === "e") S.mode = "events";
    const r = h.get("r");
    if (r && /^[01]{4}$/.test(r)) S.rels = [...r].map((c) => c === "1");
    const s = h.get("s") || "";
    if (s.startsWith("p:") && A.placeById.has(s.slice(2))) S.sel = { type: "place", i: A.placeById.get(s.slice(2)) };
    if (s.startsWith("e:") && A.byId.has(s.slice(2))) S.sel = { type: "entity", i: A.byId.get(s.slice(2)) };
    const v = (h.get("v") || "").split(",").map(Number);
    if (v.length === 3 && v.every(Number.isFinite)) { const [x, y] = project(v[0], v[1]); S.view = { cx: x, cy: y, z: v[2] }; }
    // ?iri=<an entity page or record IRI> opens the map at that entity (the resolve link of the registry)
    const iri = new URLSearchParams(location.search).get("iri");
    if (iri) {
      const m = iri.match(/^https?:\/\/data\.judaicalink\.org\/data\/ep\/(\d+)$/);
      const id = m ? m[1] : iri;
      if (A.byId.has(id)) S.sel = { type: "entity", i: A.byId.get(id), fit: true };
      else if (A.placeById.has(id)) S.sel = { type: "place", i: A.placeById.get(id), fit: true };
      else S.missing = iri;
    }
  }

  // ---- start -------------------------------------------------------------------------------------------------
  function fillAreas() {
    const used = new Set(A.pcountry);
    const opts = BM.countries.map((c, i) => [c.n, i]).filter(([, i]) => used.has(i));
    for (const [n, i] of opts) fArea.append(el("option", { value: "c" + i, text: n }));
  }
  async function start() {
    readColours();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { readColours(); update(false); });
    const [data, bm] = await Promise.all([
      fetch(app.dataset.src).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch(app.dataset.basemap).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    ]);
    BM = bm; A = decode(data); paths = buildPaths(bm);
    document.getElementById("loading").remove();
    fillAreas();
    if (matchMedia("(max-width: 860px)").matches) document.getElementById("legend").open = false;
    apply();
  }
  function apply() {
    stopPlay();
    Object.assign(S, DEFAULTS());
    load();
    resize();
    inArea = areaTest();
    if (S.view) { view.cx = S.view.cx; view.cy = S.view.cy; view.z = S.view.z; clampView(); }
    else if (S.area) fitArea();
    else fitBounds(-10, 30, 42, 60, 10);
    fFrom.value = S.from === null ? "" : S.from; fTo.value = S.to;
    fMode.value = S.mode;
    fArea.value = !S.area ? "" : S.area.type === "box" ? "box" : "c" + S.area.i;
    if (S.area && S.area.type === "box") fArea.querySelector('option[value="box"]').disabled = false;
    S.kinds.forEach((on, k) => { document.getElementById("k-" + k).checked = on; });
    S.rels.forEach((on, k) => { document.getElementById("r-" + k).checked = on; });
    const sel = S.sel;
    if (sel && sel.fit && sel.type === "entity") {
      let visible = false;
      for (let j = A.po[sel.i]; j < A.po[sel.i + 1]; j++) if (inTime(j)) visible = true;
      if (!visible) { S.from = A.start[sel.i] - 1; S.to = Math.min(NOW, A.end[sel.i] + 1); fFrom.value = S.from; fTo.value = S.to; }
    }
    update(true);
    if (sel && sel.fit) { delete sel.fit; fitSelection(); history.replaceState(null, "", location.pathname + location.hash); save(); }
    if (S.missing) panel.prepend(el("p", { class: "jl-note", text: "This entity is not on the map: the data give it no time or no place with coordinates." }),
      el("p", null, el("a", { href: S.missing.startsWith(D + "/") ? S.missing.slice(D.length) : S.missing, text: "View it in JudaicaLink" })));
  }
  window.addEventListener("resize", resize);
  window.addEventListener("hashchange", () => { if (A) apply(); });
  start().catch((err) => {
    const l = document.getElementById("loading");
    if (l) l.textContent = "The map could not be loaded (" + err.message + ").";
    console.error(err);
  });
})();
