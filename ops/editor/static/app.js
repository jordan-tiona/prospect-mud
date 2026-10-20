// MUD editor page (milestones 5a-5c): map, panels, structure editing and the candidate tray.
// Editing logic lives in core.js; this file is DOM, drawing and talking to serve.py.
'use strict';

const core = window.EditorCore;
const BOX_W = 280;
const BOX_H = 124;
const SNAP = 10;
const SVG_NS = 'http://www.w3.org/2000/svg';
const TOKEN = document.querySelector('meta[name="editor-token"]').content;

const state = {
  sectors: [],
  sectorId: null,
  server: null, // last /api/sector view: sector, version, files, manifest, kinds, autosave
  doc: null, // the editable sector document
  baseVersion: null, // sector.json version the doc was loaded/saved from
  dirty: false,
  history: new core.History(),
  issues: [],
  problems: [],
  grid: {}, // room id -> [x, y, z], worked out by check.py (map_grid); off-map rooms are absent
  unplaced: [], // /api/unplaced: content files no saved sector uses (each with request, dismissed)
  dismissed: [], // every path on the dismiss list
  dismissedMissing: [], // dismissed paths whose file has been deleted
  lastRoom: null, // the room most recently looked at, the default for placing an entity
  selected: { type: 'overview' },
  view: null,
  banner: null, // {kind: 'info'|'warn'|'err', html, transient}
  conflict: false,
  editingExit: null, // index of the exit whose edit form is open
};

const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------- helpers

function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function svg(tag, attrs = {}, parent = null) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}

// Plain prose -> paragraphs and "- " lists. Everything is escaped: no Markdown engine.
function prose(text) {
  if (!text) return '<p class="muted">(empty)</p>';
  return text.split(/\n\s*\n/).map((block) => {
    const lines = block.split('\n').map((l) => l.trim()).filter(Boolean);
    if (lines.length && lines.every((l) => l.startsWith('- '))) {
      return `<ul>${lines.map((l) => `<li>${esc(l.slice(2))}</li>`).join('')}</ul>`;
    }
    return `<p>${esc(lines.join(' '))}</p>`;
  }).join('');
}

function fileFor(path) {
  if (!path) return null;
  return state.server.files[path] || state.unplaced.find((u) => u.path === path) || { path, exists: false };
}

function approvalChip(file) {
  if (!file) return '<span class="badge-chip warn">awaiting prose</span>';
  if (!file.exists) return '<span class="badge-chip err">file missing</span>';
  const approval = file.approval || 'no approval field';
  const cls = approval === 'Approved' ? 'ok' : 'warn';
  const status = file.status ? `<span class="badge-chip">${esc(file.status)}</span>` : '';
  return `<span class="badge-chip ${cls}">${esc(approval)}</span>${status}`;
}

function entityName(id, entity) {
  return fileFor(entity.content)?.heading || id;
}

function roomTitle(id) {
  return state.doc.rooms[id]?.title || id;
}

// Which room an issue belongs to, from check.py's `where` text.
function issueRoom(issue) {
  const d = state.doc;
  let m = /^room (\S+)/.exec(issue.where);
  if (m) return d.rooms[m[1]] ? m[1] : null;
  m = /^entity (\S+)/.exec(issue.where);
  if (m) return d.entities[m[1]]?.room ?? null;
  m = /^exit\[\d+\] (\S+?)->/.exec(issue.where);
  if (m) return d.rooms[m[1]] ? m[1] : null;
  return null;
}

/** A room's grid cell as "(x,y,z)", or "off map" (docs/gmcp.md, "Map coordinates"). */
function gridLabel(id) {
  const cell = state.grid[id];
  return cell ? `(${cell.join(',')})` : 'off map';
}

function issuesFor(roomId) {
  return state.issues.filter((i) => issueRoom(i) === roomId);
}

function entitiesIn(roomId) {
  return Object.entries(state.doc.entities).filter(([, e]) => e.room === roomId);
}

function selectedRoom() {
  const s = state.selected;
  if (s.type === 'room') return s.id;
  if (s.type === 'entity') return state.doc.entities[s.id]?.room ?? null;
  return null;
}

// Files the saved sector uses but the unsaved document no longer does: back in the tray.
function released() {
  const used = core.usedContent(state.doc);
  return Object.values(state.server.files).filter((f) => f && f.exists && !used.has(f.path)).map((f) => ({
    ...f, kind_folder: f.path.split('/').slice(0, -1).join('/'), request: f.fields?.request || null, dismissed: state.dismissed.includes(f.path),
  }));
}

/** Tray candidates for the open document; dismissed ones only when asked. */
function candidates({ dismissed = false } = {}) {
  return core.trayItems(state.unplaced, released(), state.doc).filter((f) => dismissed || !f.dismissed);
}

function candidateFile(path) {
  return core.trayItems(state.unplaced, released(), state.doc).find((f) => f.path === path) || null;
}

function isRoomFile(file) {
  return file.kind_folder === state.server.room.content_dir;
}

/** First lines a player would read, for the tray list. */
function preview(file) {
  const s = file.sections || {};
  const text = (s.Glance || s['Short Description'] || s.Description || file.fields?.desc || '').replace(/\s+/g, ' ');
  return text.length > 150 ? `${text.slice(0, 147)}…` : text;
}

function applyTray(data) {
  state.unplaced = data.unplaced;
  state.dismissed = data.dismissed || [];
  state.dismissedMissing = data.dismissed_missing || [];
}

function kindsForFolder(folder) {
  return Object.entries(state.server.kinds).filter(([, k]) => k.content_dir === folder).map(([name]) => name);
}

// ------------------------------------------------------------- network

async function api(method, url, body) {
  const options = { method, cache: 'no-store', headers: {} };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.headers['X-Editor-Token'] = TOKEN;
    options.body = JSON.stringify(body);
  }
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  return { status: res.status, ok: res.ok, data };
}

async function getJSON(url) {
  const res = await api('GET', url);
  if (!res.ok) throw new Error(res.data.error || `HTTP ${res.status}`);
  return res.data;
}

// --------------------------------------------------------------- loading

/** Load from disk. With unsaved edits (and no force), only refresh files and watch for a disk change. */
async function load({ resetView = false, force = false } = {}) {
  try {
    state.sectors = (await getJSON('/api/sectors')).sectors;
    if (!state.sectors.includes(state.sectorId)) state.sectorId = state.sectors[0] ?? null;
    if (!state.sectorId) throw new Error('No sector files found under sectors/.');
    const view = await getJSON(`/api/sector/${state.sectorId}`);
    applyTray(await getJSON('/api/unplaced'));
    $('error').hidden = true;
    if (state.dirty && !force) {
      state.server = { ...view, sector: state.server.sector, files: { ...state.server.files, ...view.files } };
      state.conflict = view.version !== state.baseVersion;
      if (state.conflict) showConflict();
    } else {
      applyServerView(view);
      state.history = new core.History();
      if (view.autosave) offerAutosave(view.autosave);
    }
  } catch (err) {
    $('error').textContent = `Couldn't load: ${err.message}`;
    $('error').hidden = false;
    return;
  }
  render({ resetView });
}

function applyServerView(view) {
  state.server = view;
  state.doc = core.clone(view.sector);
  state.baseVersion = view.version;
  state.issues = view.issues;
  state.problems = [];
  state.grid = view.grid || {};
  state.dirty = false;
  state.conflict = false;
  const sel = state.selected;
  if ((sel.type === 'room' && !state.doc.rooms[sel.id]) || (sel.type === 'entity' && !state.doc.entities[sel.id])) {
    state.selected = { type: 'overview' };
  }
}

function offerAutosave(info) {
  const when = info.saved_at ? new Date(info.saved_at * 1000).toLocaleString() : 'earlier';
  const warning = info.base_matches ? '' : ' <strong>sector.json has changed since then</strong>, so restoring would undo those changes.';
  state.banner = {
    kind: info.base_matches ? 'info' : 'warn',
    html: `Unsaved changes from ${esc(when)} were autosaved.${warning}
      <button type="button" data-action="restore-autosave">Restore them</button>
      <button type="button" data-action="discard-autosave">Discard</button>`,
  };
}

function showConflict() {
  state.banner = {
    kind: 'err',
    html: `<strong>sector.json changed on disk</strong> since you loaded it (another session, or a git pull), so saving is blocked.
      Your edits are kept in the autosave.
      <button type="button" data-action="reload-discard">Reload from disk</button>`,
  };
}

// --------------------------------------------------------------- editing

let checkTimer = null;
let autosaveTimer = null;

/** Apply an edit to a copy of the document; a refused edit changes nothing. */
function edit(fn) {
  const next = core.clone(state.doc);
  try {
    fn(next);
  } catch (err) {
    flash('warn', esc(err.message));
    return false;
  }
  state.history.record(state.doc);
  state.doc = next;
  changed();
  return true;
}

function changed() {
  state.dirty = JSON.stringify(state.doc) !== JSON.stringify(state.server.sector);
  render();
  clearTimeout(checkTimer);
  checkTimer = setTimeout(liveCheck, 350);
  clearTimeout(autosaveTimer);
  if (state.dirty) autosaveTimer = setTimeout(autosaveNow, 3000);
}

async function liveCheck() {
  const res = await api('POST', `/api/sector/${state.sectorId}/check`, { sector: state.doc });
  if (!res.ok) return;
  state.issues = res.data.issues;
  state.problems = res.data.problems;
  state.grid = res.data.grid || {};
  render();
}

async function autosaveNow() {
  if (!state.dirty) return;
  const res = await api('POST', `/api/sector/${state.sectorId}/autosave`, { sector: state.doc, base_version: state.baseVersion });
  if (res.ok) $('autosave-note').textContent = `Autosaved ${new Date().toLocaleTimeString()}`;
}

function undo() {
  const prev = state.history.undo(state.doc);
  if (prev) { state.doc = prev; changed(); }
}

function redo() {
  const next = state.history.redo(state.doc);
  if (next) { state.doc = next; changed(); }
}

async function save() {
  if (!state.dirty || state.conflict) return;
  clearTimeout(autosaveTimer);
  const res = await api('POST', `/api/sector/${state.sectorId}/save`, { sector: state.doc, base_version: state.baseVersion });
  if (res.status === 409) {
    state.conflict = true;
    showConflict();
  } else if (res.status === 422) {
    flash('err', `Not saved: ${esc((res.data.problems || [res.data.error]).join('; '))}`);
  } else if (res.ok) {
    applyServerView(res.data.view);
    applyTray(await getJSON('/api/unplaced'));
    $('autosave-note').textContent = '';
    flash('info', 'Saved.');
  } else {
    flash('err', `Save failed: ${esc(res.data.error || res.status)}`);
  }
  render();
}

async function exportSector() {
  if (state.dirty) return;
  const res = await api('POST', `/api/sector/${state.sectorId}/export`, {});
  if (res.ok) {
    applyServerView(res.data.view);
    flash('info', `Exported to <span class="path">${esc(res.data.path)}</span>. The game picks it up on the next rebuild (world.build_sector, with the server stopped).`);
  } else if (res.status === 422) {
    flash('err', `Export refused: ${res.data.errors.length} error(s), listed under Check.`);
    select({ type: 'issues' });
    return;
  } else {
    flash('err', `Export failed: ${esc(res.data.error || res.status)}`);
  }
  render();
}

/** Dismiss candidates from the tray (or restore them). Writes sectors/_dismissed.json at once; no Save needed. */
async function setDismissed(paths, dismissed) {
  const res = await api('POST', '/api/dismiss', { paths, dismissed });
  if (!res.ok) {
    flash('err', `Couldn't ${dismissed ? 'dismiss' : 'restore'}: ${esc((res.data.problems || [res.data.error]).join('; '))}`);
    return;
  }
  applyTray(res.data);
  render();
}

let flashTimer = null;

function flash(kind, html) {
  state.banner = { kind, html, transient: true };
  clearTimeout(flashTimer);
  if (kind === 'info') {
    flashTimer = setTimeout(() => { if (state.banner?.transient) { state.banner = null; renderBanner(); } }, 6000);
  }
  renderBanner();
}

// ----------------------------------------------------------------- render

function render({ resetView = false } = {}) {
  renderBar();
  renderBanner();
  renderMap(resetView);
  renderPanel();
}

function renderBar() {
  $('sector').innerHTML = state.sectors.map((s) => `<option${s === state.sectorId ? ' selected' : ''}>${esc(s)}</option>`).join('');
  const errors = state.issues.filter((i) => i.level === 'error').length;
  const warnings = state.issues.filter((i) => i.level === 'warning').length;
  const btn = $('issues-btn');
  btn.textContent = errors || warnings ? `Check: ${errors} error${errors === 1 ? '' : 's'}, ${warnings} warning${warnings === 1 ? '' : 's'}` : 'Check: clean';
  btn.className = `pill ${errors ? 'err' : warnings ? 'warn' : 'ok'}`;

  const m = state.server.manifest;
  const pill = $('manifest');
  pill.textContent = { fresh: 'Manifest up to date', stale: 'Manifest stale', not_exported: 'Not exported' }[m.state];
  pill.className = `pill static ${m.state === 'fresh' ? 'ok' : m.state === 'stale' ? 'warn' : ''}`;
  pill.title = m.state === 'stale' ? `Changed since the last export:\n${m.changed.join('\n')}` : '';
  const waiting = candidates().length;
  $('tray-btn').textContent = `Tray: ${waiting}`;
  $('tray-btn').className = `pill${state.selected.type === 'tray' || state.selected.type === 'candidate' ? ' on' : ''}`;

  $('undo').disabled = !state.history.canUndo;
  $('redo').disabled = !state.history.canRedo;
  const saveBtn = $('save');
  saveBtn.disabled = !state.dirty || state.conflict;
  saveBtn.textContent = state.dirty ? 'Save' : 'Saved';
  saveBtn.className = state.dirty ? 'primary' : '';
  const exportBtn = $('export');
  exportBtn.disabled = state.dirty;
  exportBtn.title = state.dirty ? 'Save first: export uses the saved sector file' : 'Check, then write the game manifest';
  document.title = `${state.dirty ? '• ' : ''}MUD Editor`;
}

function renderBanner() {
  const box = $('banner');
  const b = state.banner;
  box.hidden = !b;
  if (!b) return;
  box.className = `banner ${b.kind}`;
  box.innerHTML = `<span>${b.html}</span>${b.transient ? '<button type="button" class="link" data-action="dismiss-banner">Dismiss</button>' : ''}`;
}

// ------------------------------------------------------------------- map

function roomPositions() {
  const pos = {};
  let fallback = 0;
  for (const [id, room] of Object.entries(state.doc.rooms)) {
    if (room.editor && Number.isFinite(room.editor.x) && Number.isFinite(room.editor.y)) {
      pos[id] = { x: room.editor.x, y: room.editor.y };
    } else {
      pos[id] = { x: (fallback % 4) * 560, y: 2000 + Math.floor(fallback / 4) * 430 };
      fallback += 1;
    }
  }
  return pos;
}

function boxHeight(id) {
  const exits = core.exitsOf(state.doc, id).length;
  return BOX_H + Math.min(Math.max(0, exits - 4) * 8, 64); // busy rooms get a longer edge for their lines
}

// Where the line from a box's centre towards (tx, ty) leaves a box of size w x h.
function edgePoint(cx, cy, tx, ty, w, h) {
  const dx = tx - cx;
  const dy = ty - cy;
  if (!dx && !dy) return { x: cx, y: cy };
  const scale = Math.min(w / 2 / Math.abs(dx || 1e-9), h / 2 / Math.abs(dy || 1e-9));
  return { x: cx + dx * Math.min(scale, 1), y: cy + dy * Math.min(scale, 1) };
}

function renderMap(resetView) {
  const map = $('map');
  map.replaceChildren();
  const defs = svg('defs', {}, map);
  const marker = svg('marker', { id: 'arrow', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 8, markerHeight: 8, orient: 'auto-start-reverse' }, defs);
  svg('path', { d: 'M0,0 L10,5 L0,10 z' }, marker);

  const pos = roomPositions();
  const heights = Object.fromEntries(Object.keys(state.doc.rooms).map((id) => [id, boxHeight(id)]));
  const centre = (id) => ({ x: pos[id].x + BOX_W / 2, y: pos[id].y + heights[id] / 2 });
  const focus = selectedRoom();
  const exitLayer = svg('g', {}, map);
  const roomLayer = svg('g', {}, map);
  const labelLayer = svg('g', {}, map); // above rooms, so a long exit's label is never hidden

  for (const ex of state.doc.exits) {
    if (!pos[ex.from] || !pos[ex.to]) continue;
    const a = centre(ex.from);
    const b = centre(ex.to);
    const p = edgePoint(a.x, a.y, b.x, b.y, BOX_W, heights[ex.from]);
    const q = edgePoint(b.x, b.y, a.x, a.y, BOX_W, heights[ex.to]);
    const touches = focus && (ex.from === focus || ex.to === focus);
    const mode = focus ? (touches ? ' hl' : ' dim') : '';
    const attrs = { x1: p.x, y1: p.y, x2: q.x, y2: q.y, class: `exit-line${mode}` };
    if (!ex.return) attrs['marker-end'] = 'url(#arrow)';
    svg('line', attrs, exitLayer);

    const len = Math.hypot(q.x - p.x, q.y - p.y) || 1;
    const nx = -(q.y - p.y) / len;
    const ny = (q.x - p.x) / len;
    const side = nx < 0 ? -1 : 1; // keep labels to the right of vertical lines
    const g = svg('g', { class: `exit-label${mode}` }, labelLayer);
    const label = svg('text', {
      x: (p.x + q.x) / 2 + nx * 16 * side, y: (p.y + q.y) / 2 + ny * 16 * side + 5,
      'text-anchor': Math.abs(nx) > 0.5 ? 'start' : 'middle',
    }, g);
    label.textContent = ex.return ? `${ex.key} / ${ex.return.key}` : `${ex.key} (one-way)`;
    const box = label.getBBox();
    g.insertBefore(svg('rect', { x: box.x - 4, y: box.y - 2, width: box.width + 8, height: box.height + 4, rx: 4 }), label);
  }

  for (const [id, room] of Object.entries(state.doc.rooms)) {
    const { x, y } = pos[id];
    const file = fileFor(room.content);
    const cls = !file ? 'placeholder' : !file.exists ? 'missing' : file.approval === 'Approved' ? '' : 'draft';
    const g = svg('g', { class: `room ${cls}${focus === id ? ' selected' : ''}`, transform: `translate(${x},${y})`, tabindex: 0, 'data-room': id }, roomLayer);
    svg('rect', { class: 'box', width: BOX_W, height: heights[id], rx: 10 }, g);
    svg('text', { x: 16, y: 38, class: 'title' }, g).textContent = room.title || id;
    const status = !file ? 'awaiting prose' : file.exists ? (file.approval || 'no approval') : 'file missing';
    svg('text', { x: 16, y: 72, class: 'sub' }, g).textContent = `${entitiesIn(id).length} placed · ${status}`;
    svg('text', { x: 16, y: 102, class: 'sub id' }, g).textContent = `${id} · ${gridLabel(id)}`;

    const roomIssues = issuesFor(id);
    const worst = roomIssues.some((i) => i.level === 'error') ? 'err' : roomIssues.some((i) => i.level === 'warning') ? 'warn' : null;
    if (worst) {
      svg('circle', { cx: BOX_W - 22, cy: 24, r: 15, class: `badge ${worst}` }, g);
      svg('text', { x: BOX_W - 22, y: 29, 'text-anchor': 'middle', class: 'badge-text' }, g).textContent = roomIssues.length;
    }
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter') select({ type: 'room', id }); });
  }

  if (resetView || !state.view) fit(pos);
  applyView();
}

function fit(pos = roomPositions()) {
  const ids = Object.keys(pos);
  if (!ids.length) { state.view = { x: -500, y: -400, w: 1000, h: 800 }; return; }
  const pad = 120;
  const minX = Math.min(...ids.map((i) => pos[i].x)) - pad;
  const minY = Math.min(...ids.map((i) => pos[i].y)) - pad;
  const maxX = Math.max(...ids.map((i) => pos[i].x)) + BOX_W + pad;
  const maxY = Math.max(...ids.map((i) => pos[i].y)) + BOX_H + 64 + pad;
  state.view = { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

function applyView() {
  const { x, y, w, h } = state.view;
  $('map').setAttribute('viewBox', `${x} ${y} ${w} ${h}`);
}

/** Screen point -> SVG user coordinates (exact, via the SVG's own transform). */
function toSvg(map, clientX, clientY) {
  const pt = map.createSVGPoint();
  pt.x = clientX;
  pt.y = clientY;
  return pt.matrixTransform(map.getScreenCTM().inverse());
}

function setupMapInput() {
  const map = $('map');
  let drag = null;
  map.addEventListener('pointerdown', (e) => {
    const roomEl = e.target.closest('.room');
    if (roomEl) {
      const id = roomEl.dataset.room;
      drag = { kind: 'room', id, el: roomEl, start: toSvg(map, e.clientX, e.clientY), origin: { ...roomPositions()[id] }, moved: false };
    } else {
      drag = { kind: 'pan', x: e.clientX, y: e.clientY, view: { ...state.view } };
      map.classList.add('panning');
    }
    try { map.setPointerCapture(e.pointerId); } catch { /* synthetic or already-released pointer */ }
  });
  map.addEventListener('pointermove', (e) => {
    if (!drag) return;
    if (drag.kind === 'pan') {
      const rect = map.getBoundingClientRect();
      const k = Math.max(drag.view.w / rect.width, drag.view.h / rect.height);
      state.view = { ...drag.view, x: drag.view.x - (e.clientX - drag.x) * k, y: drag.view.y - (e.clientY - drag.y) * k };
      applyView();
      return;
    }
    const now = toSvg(map, e.clientX, e.clientY);
    const dx = now.x - drag.start.x;
    const dy = now.y - drag.start.y;
    if (!drag.moved && Math.hypot(dx, dy) < 4) return;
    drag.moved = true;
    drag.to = { x: Math.round((drag.origin.x + dx) / SNAP) * SNAP, y: Math.round((drag.origin.y + dy) / SNAP) * SNAP };
    drag.el.setAttribute('transform', `translate(${drag.to.x},${drag.to.y})`);
  });
  const end = () => {
    if (!drag) return;
    const d = drag;
    drag = null;
    map.classList.remove('panning');
    if (d.kind !== 'room') return;
    if (d.moved && d.to) edit((doc) => core.setRoom(doc, d.id, { position: d.to }));
    else select({ type: 'room', id: d.id });
  };
  map.addEventListener('pointerup', end);
  map.addEventListener('pointercancel', end);
  map.addEventListener('wheel', (e) => {
    e.preventDefault();
    const v = state.view;
    const at = toSvg(map, e.clientX, e.clientY);
    const w = Math.min(Math.max(v.w * Math.exp(e.deltaY * 0.0015), 300), 40000);
    const s = w / v.w;
    state.view = { x: at.x - (at.x - v.x) * s, y: at.y - (at.y - v.y) * s, w, h: v.h * s };
    applyView();
  }, { passive: false });
}

// ----------------------------------------------------------------- panel

function select(selection) {
  const d = state.doc;
  if ((selection.type === 'room' && !d.rooms[selection.id]) || (selection.type === 'entity' && !d.entities[selection.id])) {
    selection = { type: 'overview' };
  }
  const sameItem = selection.type === state.selected.type && selection.id === state.selected.id
    && selection.path === state.selected.path;
  state.selected = selection;
  if (selection.type === 'room') state.lastRoom = selection.id;
  if (selection.type === 'entity') state.lastRoom = d.entities[selection.id].room;
  state.editingExit = null;
  const hash = ['room', 'entity'].includes(selection.type) ? `#${selection.type}=${encodeURIComponent(selection.id)}` : '';
  if (location.hash !== hash) history.replaceState(null, '', hash || location.pathname);
  renderBar();
  renderMap(false);
  renderPanel(!sameItem);
}

function selectionFromHash() {
  const m = /^#(room|entity)=(.+)$/.exec(location.hash);
  return m ? { type: m[1], id: decodeURIComponent(m[2]) } : { type: 'overview' };
}

function renderPanel(toTop = false) {
  const panel = $('panel');
  const s = state.selected;
  if ((s.type === 'room' && !state.doc.rooms[s.id]) || (s.type === 'entity' && !state.doc.entities[s.id])) {
    s.type = 'overview'; // removed (or undone away) while it was open
  }
  const scroll = panel.scrollTop;
  panel.innerHTML = s.type === 'room' ? roomPanel(s.id)
    : s.type === 'entity' ? entityPanel(s.id)
    : s.type === 'issues' ? issuesPanel()
    : s.type === 'tray' ? trayPanel()
    : s.type === 'candidate' ? candidatePanel(s.path)
    : overviewPanel();
  panel.scrollTop = toTop ? 0 : scroll;
}

const go = (type, id, label) => `<button class="link" type="button" data-go="${type}:${esc(id)}">${esc(label)}</button>`;

function options(list, selected) {
  return list.map(([value, label]) => `<option value="${esc(value)}"${value === selected ? ' selected' : ''}>${esc(label)}</option>`).join('');
}

function overviewPanel() {
  const d = state.doc;
  const exits = d.exits.reduce((n, e) => n + (e.return ? 2 : 1), 0);
  const errors = state.issues.filter((i) => i.level === 'error').length;
  const roomFiles = candidates().filter(isRoomFile);
  return `
    <h2>${esc(d.sector_id)}</h2>
    <p class="muted">Sector overview. Click a room on the map to edit it; drag rooms to move them.</p>
    <dl class="kv">
      <dt>Rooms</dt><dd>${Object.keys(d.rooms).length}</dd>
      <dt>Exits</dt><dd>${exits}</dd>
      <dt>Placed entities</dt><dd>${Object.keys(d.entities).length}</dd>
      <dt>Map anchor</dt><dd>${d.map_anchor && d.rooms[d.map_anchor] ? go('room', d.map_anchor, roomTitle(d.map_anchor)) : 'none (set one in a room’s Map grid)'}</dd>
      <dt>Check</dt><dd>${state.issues.length ? `${errors} error(s), ${state.issues.length - errors} other` : 'clean'}</dd>
      <dt>Manifest</dt><dd>${esc(state.server.manifest.state.replace('_', ' '))}</dd>
    </dl>
    <h3>Add a room</h3>
    <form class="form" data-form="add-room">
      <label>Prose <select name="content">${options([['', '— none yet (placeholder; request prose later) —'], ...roomFiles.map((f) => [f.path, `${f.heading || f.path} (${f.approval || 'no approval'})`])], '')}</select></label>
      <label>ID <input name="id" placeholder="lowercase_with_underscores" required></label>
      <label>Title <input name="title" placeholder="What players see" required></label>
      <div class="actions"><button type="submit" class="primary">Add room</button></div>
      <p class="muted small">With prose chosen, the ID must match the file's <code>room_id</code>. A placeholder blocks export until Lore delivers prose.</p>
    </form>
    <h3>Sector notes</h3>
    <textarea data-field="sector-notes" rows="3" placeholder="Editor-only notes (never reach the game)">${esc(d.notes || '')}</textarea>
    <h3>Rooms</h3>
    <ul class="list">${Object.entries(d.rooms).map(([id, r]) => `<li>${go('room', id, r.title || id)}<span class="kind">${esc(id)}</span>${r.content ? '' : '<span class="badge-chip warn">awaiting prose</span>'}</li>`).join('')}</ul>`;
}

function issueList(issues) {
  if (!issues.length) return '<p class="muted">No issues.</p>';
  return issues.map((i) => {
    const room = issueRoom(i);
    const where = room ? go('room', room, i.where) : esc(i.where);
    return `<div class="issue ${esc(i.level)}"><span class="code">${esc(i.level)} · ${esc(i.code)}</span><br>${where}: ${esc(i.message)}</div>`;
  }).join('');
}

function issuesPanel() {
  const order = { error: 0, warning: 1, info: 2 };
  const issues = [...state.issues].sort((a, b) => order[a.level] - order[b.level]);
  const m = state.server.manifest;
  const manifest = m.state === 'stale'
    ? `<h3>Manifest</h3><p>Changed since the last export:</p><ul>${m.changed.map((c) => `<li class="path">${esc(c)}</li>`).join('')}</ul>`
    : '';
  const problems = state.problems.length ? `<h3>Can't be saved yet</h3><ul>${state.problems.map((p) => `<li>${esc(p)}</li>`).join('')}</ul>` : '';
  return `<h2>Check</h2><p class="muted">The same checks as <code>ops/editor/check.py</code>, run on ${state.dirty ? 'your unsaved edits' : 'the saved sector'}.</p>${problems}${issueList(issues)}${manifest}`;
}

function exitForm(room, row) {
  const out = row ? row.out : null;
  const back = row ? row.back : null;
  const others = Object.keys(state.doc.rooms).filter((r) => r !== room && core.pairIndex(state.doc, room, r) === -1);
  const oneWay = row ? !out || !back : false;
  return `
    <form class="form exit-form" data-form="${row ? 'edit-exit' : 'add-exit'}"${row ? ` data-index="${row.index}" data-back-touched="1"` : ''}>
      ${row ? `<p><strong>${esc(roomTitle(room))}</strong> ↔ <strong>${esc(roomTitle(row.other))}</strong></p>`
    : `<label>To <select name="to">${options(others.map((r) => [r, `${roomTitle(r)} (${r})`]), others[0])}</select></label>`}
      <div class="row">
        <label>Way out (command) <input name="out_key" value="${esc(out?.key || '')}" placeholder="north"></label>
        <label>Aliases <input name="out_aliases" value="${esc((out?.aliases || []).join(', '))}" placeholder="n"${row ? ' data-touched="1"' : ''}></label>
      </div>
      <div class="row">
        <label>Way back <input name="back_key" value="${esc(back?.key || '')}" placeholder="south"></label>
        <label>Aliases <input name="back_aliases" value="${esc((back?.aliases || []).join(', '))}" placeholder="s"></label>
      </div>
      <label class="check"><input type="checkbox" name="one_way"${oneWay ? ' checked' : ''}> One-way (leave the unused side empty)</label>
      <div class="actions">
        <button type="submit" class="primary">${row ? 'Apply' : 'Add exit'}</button>
        ${row ? '<button type="button" data-action="cancel-exit">Cancel</button>' : ''}
      </div>
    </form>`;
}

function roomPanel(id) {
  const room = state.doc.rooms[id];
  const file = fileFor(room.content);
  const sections = file && file.exists ? file.sections : {};
  const rows = core.exitsOf(state.doc, id);
  const here = entitiesIn(id);
  const roomIssues = issuesFor(id);
  const roomDir = state.server.room.content_dir;
  const matchingProse = candidates().filter((u) => u.kind_folder === roomDir && u.fields?.room_id === id);
  const placeable = candidates().filter((u) => u.kind_folder !== roomDir && kindsForFolder(u.kind_folder).length);
  const canAddExit = state.editingExit === null && Object.keys(state.doc.rooms).some((r) => r !== id && core.pairIndex(state.doc, id, r) === -1);
  return `
    <h2>${esc(room.title || id)}</h2>
    <div class="badges">${approvalChip(file)}<span class="badge-chip">room · ${esc(id)}</span></div>
    <div class="path">${esc(room.content ? `content/${room.content}` : 'No prose yet: request it from Lore (docs/lore-requests.md).')}</div>
    ${roomIssues.length ? `<h3>Issues</h3>${issueList(roomIssues)}` : ''}
    <h3>Title</h3>
    <input data-field="room-title" value="${esc(room.title || '')}">
    ${(room.editor?.former_titles || []).length ? `<p class="small muted">Formerly: ${room.editor.former_titles.map((t) => `<span class="former">${esc(t)}
      <button type="button" class="link" data-action="forget-title" data-title="${esc(t)}" title="Stop warning about prose that uses this title">Forget</button></span>`).join(' · ')}
      <br>Check warns about prose that still uses an old title.</p>` : ''}
    ${!room.content && matchingProse.length ? `<p class="small">Prose for this ID has arrived: <select data-field="room-content">${options([['', 'choose…'], ...matchingProse.map((f) => [f.path, `${f.path} (${f.approval || 'no approval'})`])], '')}</select></p>` : ''}
    ${room.content ? '<p class="small"><button type="button" class="link" data-action="unlink-prose">Detach prose</button> <span class="muted">(makes this a placeholder again; the file is untouched)</span></p>' : ''}
    ${sections.Glance ? `<h3>Glance</h3><div class="prose">${prose(sections.Glance)}</div>` : ''}
    ${file ? `<h3>Description</h3><div class="prose">${prose(sections.Description)}</div>` : ''}
    ${mapGridHTML(id, room)}
    <h3>Exits (${rows.length})</h3>
    ${rows.length ? `<ul class="list">${rows.map((row) => (state.editingExit === row.index ? `<li class="editing">${exitForm(id, row)}</li>` : `
      <li><span class="dir">${row.out ? esc(row.out.key) : '<span class="muted">(in only)</span>'}</span>
        ${state.doc.rooms[row.other] ? go('room', row.other, roomTitle(row.other)) : `<span class="badge-chip err">unknown room ${esc(row.other)}</span>`}
        <span class="kind">${row.out && row.out.aliases.length ? esc(row.out.aliases.join(', ')) : ''}${!row.back || !row.out ? ' · one-way' : ''}</span>
        <span class="spacer"></span>
        <button type="button" class="link" data-action="edit-exit" data-index="${row.index}">Edit</button>
        <button type="button" class="link danger" data-action="remove-exit" data-index="${row.index}">Remove</button>
      </li>`)).join('')}</ul>` : '<p class="muted">No exits.</p>'}
    ${canAddExit ? `<details class="add"><summary>Add an exit</summary>${exitForm(id, null)}</details>` : ''}
    <h3>Here (${here.length})</h3>
    ${here.length ? `<ul class="list">${here.map(([eid, e]) => `<li>${go('entity', eid, entityName(eid, e))}<span class="kind">${esc(e.kind)}</span>${approvalChip(fileFor(e.content))}</li>`).join('')}</ul>` : '<p class="muted">Nothing placed here.</p>'}
    ${placeable.length ? `<details class="add" data-place><summary>Place something here</summary>
      <form class="form" data-form="place-entity">
        <label>Content <select name="content">${options(placeable.map((f) => [f.path, `${f.heading || f.path} — ${f.kind_folder} (${f.approval || 'no approval'})`]), placeable[0].path)}</select></label>
        <label>Kind <select name="kind">${options(kindsForFolder(placeable[0].kind_folder).map((k) => [k, k]), '')}</select></label>
        <div class="actions"><button type="submit" class="primary">Place</button></div>
        <p class="muted small">The ID comes from the content file. The ${go('tray', '', 'tray')} groups candidates by request.</p>
      </form></details>` : ''}
    <h3>Notes</h3>
    <textarea data-field="room-notes" rows="3" placeholder="Editor-only notes (never reach the game)">${esc(room.notes || '')}</textarea>
    <h3>Remove</h3>
    <button type="button" class="danger" data-action="remove-room">Remove this room</button>
    <p class="muted small">Also removes its exits. Refused while anything is placed here. The prose file is never deleted.</p>`;
}

function mapGridHTML(id, room) {
  const anchor = state.doc.map_anchor === id;
  const pin = room.map_pin;
  const how = pin ? 'pinned' : anchor ? 'the anchor' : state.grid[id] ? 'worked out from the exits' : '';
  const cell = state.grid[id] || [];
  return `
    <h3>Map grid</h3>
    <p><strong>${esc(gridLabel(id))}</strong>${how ? ` <span class="muted">· ${esc(how)}</span>` : ''}</p>
    <form class="form" data-form="map-pin">
      <div class="row three">
        ${['x', 'y', 'z'].map((axis, i) => `<label>${axis} <input name="${axis}" inputmode="numeric" value="${esc(String(pin ? pin[axis] : cell[i] ?? ''))}"></label>`).join('')}
      </div>
      <div class="actions">
        <button type="submit">${pin ? 'Move pin' : 'Pin here'}</button>
        ${pin ? '<button type="button" data-action="unpin">Unpin</button>' : ''}
        ${anchor ? '' : '<button type="button" data-action="make-anchor">Make this the anchor</button>'}
      </div>
    </form>
    <p class="muted small">Each compass exit is one grid step (up/down change z), counted from the anchor at (0,0,0). Pin a room only where that rule doesn't fit; it then counts from the pin.</p>`;
}

function sectionsHTML(file, kind) {
  if (!file || !file.exists) return '';
  const sections = Object.entries(file.sections || {});
  if (kind === 'talk_npc') {
    // Personas are long prompt text: show the look and probe descriptions, keep the rest folded.
    const desc = file.fields?.desc;
    const probe = file.fields?.probe_desc;
    return `<h3>Look description</h3><div class="prose">${desc ? prose(desc) : '<p class="muted">None authored (the persona has no <code>desc:</code> field), so players see the default.</p>'}</div>
      <h3>Probe description</h3><div class="prose">${probe ? prose(probe) : '<p class="muted">None authored (no <code>probe_desc:</code> field), so <code>probe</code> shows the look description.</p>'}</div>
      <h3>Persona</h3><details><summary>${sections.length} section(s): ${esc(sections.map(([h]) => h).join(', '))}</summary>
      ${sections.map(([h, body]) => `<h3>${esc(h)}</h3><div class="prose">${prose(body)}</div>`).join('')}</details>`;
  }
  return sections.map(([h, body]) => `<h3>${esc(h)}</h3><div class="prose">${prose(body)}</div>`).join('');
}

/** Container-kind entities in a room (not inside anything), excluding `except`. */
function containersIn(room, except) {
  return Object.entries(state.doc.entities).filter(([c, ce]) => c !== except && ce.room === room && !ce.inside
    && state.server.kinds[ce.kind]?.container);
}

function entityPanel(id) {
  const e = state.doc.entities[id];
  const file = fileFor(e.content);
  const kind = state.server.kinds[e.kind] || { params: {} };
  const params = Object.entries(kind.params);
  return `
    <p>${go('room', e.room, `← ${roomTitle(e.room)}`)}</p>
    <h2>${esc(entityName(id, e))}</h2>
    <div class="badges">${approvalChip(file)}<span class="badge-chip">${esc(e.kind)} · ${esc(id)}</span></div>
    <div class="path">${esc(e.content ? `content/${e.content}` : '(no content file)')}</div>
    <h3>Room</h3>
    <select data-field="entity-room">${options(Object.entries(state.doc.rooms).map(([r, room]) => [r, `${room.title || r} (${r})`]), e.room)}</select>
    ${containersIn(e.room, id).length || e.inside ? `<h3>Inside</h3>
    <select data-field="entity-inside">${options([['', '(loose in the room)'], ...containersIn(e.room, id).map(([c, ce]) => [c, `${entityName(c, ce)} (${c})`])], e.inside || '')}</select>` : ''}
    <h3>Aliases</h3>
    <input data-field="entity-aliases" value="${esc((e.aliases || []).join(', '))}" placeholder="extra words players can use, comma-separated">
    ${params.length ? `<h3>Settings</h3><dl class="kv form-kv">${params.map(([name, spec]) => `
      <dt>${esc(name)}${spec.required ? ' *' : ''}</dt>
      <dd><select data-param="${esc(name)}">${options([['', spec.required ? 'choose…' : '(none)'], ...spec.values.map((v) => [v, v])], (e.params || {})[name] || '')}</select></dd>`).join('')}</dl>
      <p class="muted small">Values come from Dev's allowlist (prospect/world/entity_kinds.py).</p>` : ''}
    ${sectionsHTML(file, e.kind)}
    <h3>Notes</h3>
    <textarea data-field="entity-notes" rows="3" placeholder="Editor-only notes (never reach the game)">${esc(e.notes || '')}</textarea>
    <h3>Remove</h3>
    <button type="button" class="danger" data-action="remove-entity">Remove from sector</button>
    <p class="muted small">The content file stays; it shows up under Unplaced.</p>`;
}

function trayRow(item) {
  const room = isRoomFile(item);
  const placeBtn = room
    ? `<button type="button" class="link" data-action="place-room" data-path="${esc(item.path)}" title="Add as a room near the middle of the map">Place</button>`
    : `<button type="button" class="link" data-go="candidate:${esc(encodeURIComponent(item.path))}" title="Choose a room and kind">Place…</button>`;
  return `<li class="cand">
      <div class="cand-head">${go('candidate', encodeURIComponent(item.path), item.heading || item.path)}
        <span class="kind">${esc(item.kind_folder)}</span>${approvalChip(item)}
        <span class="spacer"></span>${placeBtn}
        <button type="button" class="link danger" data-action="dismiss" data-path="${esc(item.path)}">Dismiss</button></div>
      ${preview(item) ? `<div class="cand-preview">${esc(preview(item))}</div>` : ''}
    </li>`;
}

function trayPanel() {
  const groups = core.groupByRequest(candidates({ dismissed: true }));
  const active = groups.filter((g) => g.active.length);
  const dismissed = groups.flatMap((g) => g.dismissed);
  const intro = `<h2>Candidate tray</h2>
    <p class="muted">Content files no sector uses yet, grouped by their <code>request:</code> line. Placing adds one to this
    sector (Draft is fine; only export needs approval) and takes effect when you Save. Dismissing takes it out of the tray
    straight away (it goes in <code>sectors/_dismissed.json</code>); the file itself is never touched.</p>`;
  const body = active.length ? active.map((g) => `
    <div class="tray-group">
      <h3>${esc(g.request || 'No request (stray files)')} <span class="kind">${g.active.length} waiting</span>
        ${g.request && g.active.length > 1 ? `<button type="button" class="link danger" data-action="dismiss-group" data-request="${esc(g.request)}">Dismiss all ${g.active.length}</button>` : ''}</h3>
      <ul class="list">${g.active.map(trayRow).join('')}</ul>
    </div>`).join('') : '<p class="muted">Nothing waiting: every content file is placed or dismissed.</p>';
  const gone = state.dismissedMissing;
  const restore = dismissed.length || gone.length ? `
    <details class="add"><summary>Dismissed (${dismissed.length + gone.length})</summary>
      <ul class="list">${dismissed.map((item) => `<li>${go('candidate', encodeURIComponent(item.path), item.heading || item.path)}
        <span class="kind">${esc(item.request || item.kind_folder)}</span><span class="spacer"></span>
        <button type="button" class="link" data-action="restore" data-path="${esc(item.path)}">Restore</button></li>`).join('')}
      ${gone.map((path) => `<li><span class="path">${esc(path)}</span><span class="badge-chip">file deleted</span><span class="spacer"></span>
        <button type="button" class="link" data-action="restore" data-path="${esc(path)}">Clear</button></li>`).join('')}</ul>
    </details>` : '';
  return intro + body + restore;
}

function candidatePanel(path) {
  const item = candidateFile(path);
  if (!item) return trayPanel();
  const room = isRoomFile(item);
  const kinds = room ? [] : kindsForFolder(item.kind_folder);
  const idField = room ? state.server.room.id_field : state.server.kinds[kinds[0]]?.id_field;
  const id = core.candidateId(item, idField);
  const taken = core.idTaken(state.doc, id);
  const roomIds = Object.keys(state.doc.rooms);
  const here = state.doc.rooms[state.lastRoom] ? state.lastRoom : roomIds[0];
  let place;
  if (item.dismissed) {
    place = '<p class="muted">Dismissed. Restore it to place it.</p><button type="button" data-action="restore" data-path="' + esc(item.path) + '">Restore to the tray</button>';
  } else if (taken) {
    place = `<p class="issue error">The ID <code>${esc(id)}</code> is already used in this sector, so this can't be placed. Lore chose the file name; ask for a rename, or dismiss it.</p>`;
  } else if (room) {
    place = `<form class="form" data-form="place-candidate" data-path="${esc(item.path)}">
        <label>Title <input name="title" value="${esc(item.heading || id)}" required></label>
        <div class="actions"><button type="submit" class="primary">Place as a room</button></div>
        <p class="muted small">The heading is only a suggestion; the title is yours. Then connect it with exits.</p>
      </form>`;
  } else if (!kinds.length) {
    place = '<p class="muted">No entity kind reads from this folder, so it can\'t be placed (a Dev-lane allowlist change).</p>';
  } else if (!roomIds.length) {
    place = '<p class="muted">Add a room first.</p>';
  } else {
    place = `<form class="form" data-form="place-candidate" data-path="${esc(item.path)}">
        <label>Room <select name="room">${options(roomIds.map((r) => [r, `${roomTitle(r)} (${r})`]), here)}</select></label>
        <label>Kind <select name="kind">${options(kinds.map((k) => [k, k]), kinds[0])}</select></label>
        <div class="actions"><button type="submit" class="primary">Place</button></div>
      </form>`;
  }
  return `
    <p>${go('tray', '', '← Tray')}</p>
    <h2>${esc(item.heading || item.path)}</h2>
    <div class="badges">${approvalChip(item)}${item.request ? `<span class="badge-chip">${esc(item.request)}</span>` : ''}<span class="badge-chip">${esc(room ? 'room' : item.kind_folder)} · ${esc(id)}</span></div>
    <div class="path">content/${esc(item.path)}</div>
    <h3>Place</h3>
    ${place}
    ${item.dismissed ? '' : `<p class="small"><button type="button" class="link danger" data-action="dismiss" data-path="${esc(item.path)}">Dismiss from the tray</button></p>`}
    ${sectionsHTML(item, item.kind_folder === 'npcs' ? 'talk_npc' : '')}`;
}

// ------------------------------------------------------------ panel input

function exitFromForm(form) {
  const f = new FormData(form);
  const side = (k, a) => (String(f.get(k) || '').trim() ? { key: String(f.get(k)).trim(), aliases: core.parseAliases(f.get(a)) } : null);
  const out = side('out_key', 'out_aliases');
  const back = side('back_key', 'back_aliases');
  if (!f.get('one_way') && (!out || !back)) throw new Error('Fill in both ways, or tick One-way.');
  return { out, back, to: f.get('to') };
}

function setupPanelInput() {
  const panel = $('panel');

  panel.addEventListener('click', (e) => {
    const goEl = e.target.closest('[data-go]');
    if (goEl) {
      const [type, id] = goEl.dataset.go.split(':');
      select(type === 'candidate' ? { type, path: decodeURIComponent(id) } : { type, id });
      return;
    }
    const act = e.target.closest('[data-action]');
    if (!act) return;
    const id = state.selected.id;
    const index = Number(act.dataset.index);
    switch (act.dataset.action) {
      case 'edit-exit': state.editingExit = index; renderPanel(); break;
      case 'cancel-exit': state.editingExit = null; renderPanel(); break;
      case 'remove-exit': {
        const ex = state.doc.exits[index];
        if (confirm(`Remove the exit between ${roomTitle(ex.from)} and ${roomTitle(ex.to)}?`)) edit((doc) => core.removeExit(doc, index));
        break;
      }
      case 'unlink-prose': edit((doc) => core.setRoom(doc, id, { content: '' })); break;
      case 'make-anchor': edit((doc) => core.setMapAnchor(doc, id)); break;
      case 'unpin': edit((doc) => core.setMapPin(doc, id, null)); break;
      case 'forget-title': edit((doc) => core.forgetFormerTitle(doc, id, act.dataset.title)); break;
      case 'place-room': placeRoomCandidate(act.dataset.path); break;
      case 'dismiss': setDismissed([act.dataset.path], true); break;
      case 'restore': setDismissed([act.dataset.path], false); break;
      case 'dismiss-group': {
        const paths = candidates().filter((f) => f.request === act.dataset.request).map((f) => f.path);
        if (confirm(`Dismiss all ${paths.length} remaining candidate(s) for ${act.dataset.request}? (Restore brings them back.)`)) setDismissed(paths, true);
        break;
      }
      case 'remove-room': {
        const n = core.exitsOf(state.doc, id).length;
        if (confirm(`Remove ${roomTitle(id)}${n ? ` and its ${n} exit(s)` : ''} from the sector? (Undo brings it back until you save.)`)
          && edit((doc) => core.removeRoom(doc, id))) select({ type: 'overview' });
        break;
      }
      case 'remove-entity': {
        const entity = state.doc.entities[id];
        if (confirm(`Remove ${entityName(id, entity)} from the sector? Its content file stays.`)
          && edit((doc) => core.removeEntity(doc, id))) select({ type: 'room', id: entity.room });
        break;
      }
      default:
    }
  });

  // Single-field edits apply when the field is left (or on change, for selects).
  panel.addEventListener('change', (e) => {
    const el = e.target;
    const id = state.selected.id;
    const field = el.dataset.field;
    if (el.dataset.param) {
      const params = { ...(state.doc.entities[id].params || {}), [el.dataset.param]: el.value };
      edit((doc) => core.setEntity(doc, id, { params }));
    } else if (field === 'room-title') edit((doc) => core.setRoom(doc, id, { title: el.value }));
    else if (field === 'room-content') { if (el.value) edit((doc) => core.setRoom(doc, id, { content: el.value })); }
    else if (field === 'room-notes') edit((doc) => core.setRoom(doc, id, { notes: el.value }));
    else if (field === 'entity-room') edit((doc) => core.setEntity(doc, id, { room: el.value }));
    else if (field === 'entity-inside') edit((doc) => core.setEntity(doc, id, { inside: el.value }));
    else if (field === 'entity-aliases') edit((doc) => core.setEntity(doc, id, { aliases: core.parseAliases(el.value) }));
    else if (field === 'entity-notes') edit((doc) => core.setEntity(doc, id, { notes: el.value }));
    else if (field === 'sector-notes') edit((doc) => { if (el.value) doc.notes = el.value; else delete doc.notes; });
    else if (el.name === 'content' && el.form?.dataset.form === 'add-room') prefillRoomFromProse(el.form);
    else if (el.name === 'content' && el.form?.dataset.form === 'place-entity') fillKinds(el.form);
  });

  // Typing a direction pre-fills the way back, until the way back is edited by hand.
  panel.addEventListener('input', (e) => {
    const el = e.target;
    const form = el.form;
    if (!form || !form.classList.contains('exit-form')) return;
    if (el.name === 'back_key' || el.name === 'back_aliases') form.dataset.backTouched = '1';
    if (el.name === 'out_aliases') el.dataset.touched = '1';
    if (el.name === 'out_key') {
      if (!form.elements.out_aliases.dataset.touched) form.elements.out_aliases.value = core.shortAliases(el.value).join(', ');
      if (!form.dataset.backTouched) {
        const opp = core.opposite(el.value);
        form.elements.back_key.value = opp ? opp.key : '';
        form.elements.back_aliases.value = opp ? opp.aliases.join(', ') : '';
      }
    }
  });

  panel.addEventListener('submit', (e) => {
    e.preventDefault();
    const form = e.target;
    const id = state.selected.id;
    try {
      if (form.dataset.form === 'add-room') {
        const f = new FormData(form);
        const v = state.view;
        const { x, y } = freeSpot(v.x + v.w / 2 - BOX_W / 2, v.y + v.h / 2 - BOX_H / 2);
        const newId = String(f.get('id')).trim();
        if (edit((doc) => core.addRoom(doc, { id: newId, title: f.get('title'), content: f.get('content') || undefined, x, y }))) {
          select({ type: 'room', id: newId });
        }
      } else if (form.dataset.form === 'map-pin') {
        const f = new FormData(form);
        edit((doc) => core.setMapPin(doc, id, { x: f.get('x'), y: f.get('y'), z: f.get('z') }));
      } else if (form.dataset.form === 'add-exit') {
        const { out, back, to } = exitFromForm(form);
        if (!out) throw new Error('A new exit needs a way out of this room.');
        edit((doc) => core.addExit(doc, { from: id, to, key: out.key, aliases: out.aliases, back }));
      } else if (form.dataset.form === 'edit-exit') {
        const index = Number(form.dataset.index);
        const { out, back } = exitFromForm(form);
        state.editingExit = null;
        if (!edit((doc) => core.setExit(doc, index, id, { out, back }))) { state.editingExit = index; }
      } else if (form.dataset.form === 'place-candidate') {
        const f = new FormData(form);
        const file = candidateFile(form.dataset.path);
        if (!file) throw new Error('That file is no longer in the tray.');
        if (isRoomFile(file)) {
          placeRoomCandidate(file.path, f.get('title'));
        } else {
          const kind = f.get('kind');
          const newId = core.candidateId(file, state.server.kinds[kind].id_field);
          if (edit((doc) => core.placeCandidate(doc, file, { kind, idField: state.server.kinds[kind].id_field, room: f.get('room') }))) {
            select({ type: 'entity', id: newId });
          }
        }
      } else if (form.dataset.form === 'place-entity') {
        const f = new FormData(form);
        const file = candidateFile(f.get('content'));
        const kind = f.get('kind');
        const spec = state.server.kinds[kind];
        const newId = file?.fields?.[spec?.id_field];
        if (!newId) throw new Error(`That file has no ${spec?.id_field || 'id'} field, so it can't be placed.`);
        if (edit((doc) => core.addEntity(doc, { id: newId, kind, room: id, content: file.path }))) select({ type: 'entity', id: newId });
      }
    } catch (err) {
      flash('warn', esc(err.message));
    }
  });
}

/** The free spot nearest (x, y) where a new room's box overlaps no other, rings outward. */
function freeSpot(x, y) {
  const taken = Object.values(roomPositions());
  const stepX = BOX_W + 60;
  const stepY = BOX_H + 120;
  const clear = (px, py) => taken.every((p) => Math.abs(p.x - px) >= BOX_W + 40 || Math.abs(p.y - py) >= BOX_H + 100);
  for (let ring = 0; ring < 12; ring++) {
    for (let dx = -ring; dx <= ring; dx++) {
      for (let dy = -ring; dy <= ring; dy++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== ring) continue;
        const px = Math.round((x + dx * stepX) / SNAP) * SNAP;
        const py = Math.round((y + dy * stepY) / SNAP) * SNAP;
        if (clear(px, py)) return { x: px, y: py };
      }
    }
  }
  return { x: Math.round(x / SNAP) * SNAP, y: Math.round(y / SNAP) * SNAP };
}

/** Add a room candidate at a free spot near the middle of the view, then show it. */
function placeRoomCandidate(path, title) {
  const file = candidateFile(path);
  if (!file) return;
  const idField = state.server.room.id_field;
  const v = state.view;
  const { x, y } = freeSpot(v.x + v.w / 2 - BOX_W / 2, v.y + v.h / 2 - BOX_H / 2);
  if (edit((doc) => core.placeCandidate(doc, file, { kind: 'room', idField, title, x, y }))) {
    select({ type: 'room', id: core.candidateId(file, idField) });
  }
}

function prefillRoomFromProse(form) {
  const file = candidateFile(form.elements.content.value);
  if (!file) return;
  form.elements.id.value = file.fields?.room_id || '';
  if (file.heading && !form.elements.title.value) form.elements.title.value = file.heading;
}

function fillKinds(form) {
  const file = candidateFile(form.elements.content.value);
  const kinds = file ? kindsForFolder(file.kind_folder) : [];
  form.elements.kind.innerHTML = options(kinds.map((k) => [k, k]), kinds[0]);
}

// ------------------------------------------------------------------ init

function init() {
  setupMapInput();
  setupPanelInput();
  $('reload').addEventListener('click', () => {
    if (state.dirty && !confirm('Discard your unsaved edits and reload from disk? (They stay in the autosave.)')) return;
    load({ force: true });
  });
  $('issues-btn').addEventListener('click', () => select({ type: 'issues' }));
  $('tray-btn').addEventListener('click', () => select({ type: 'tray' }));
  $('undo').addEventListener('click', undo);
  $('redo').addEventListener('click', redo);
  $('save').addEventListener('click', save);
  $('export').addEventListener('click', exportSector);
  $('sector').addEventListener('change', (e) => {
    if (state.dirty && !confirm('Switch sectors and leave your unsaved edits? (They stay in the autosave.)')) {
      e.target.value = state.sectorId;
      return;
    }
    state.sectorId = e.target.value;
    state.selected = { type: 'overview' };
    load({ resetView: true, force: true });
  });
  $('banner').addEventListener('click', async (e) => {
    const act = e.target.closest('[data-action]')?.dataset.action;
    if (act === 'dismiss-banner') { state.banner = null; renderBanner(); }
    if (act === 'discard-autosave') {
      await api('POST', `/api/sector/${state.sectorId}/autosave/discard`, {});
      state.banner = null;
      renderBanner();
    }
    if (act === 'restore-autosave') {
      const saved = (await getJSON(`/api/sector/${state.sectorId}/autosave`)).sector;
      state.banner = null;
      if (saved) { state.history.record(state.doc); state.doc = saved; changed(); }
    }
    if (act === 'reload-discard') {
      state.banner = null;
      load({ force: true });
    }
  });
  document.addEventListener('keydown', (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); save(); return; }
    if (e.target.closest('input, select, textarea')) return;
    if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); (e.shiftKey ? redo : undo)(); return; }
    if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); return; }
    if (e.key === 'f' || e.key === 'F') { fit(); applyView(); }
    if (e.key === 'Escape') select({ type: 'overview' });
  });
  window.addEventListener('beforeunload', (e) => {
    if (state.dirty) { e.preventDefault(); e.returnValue = ''; }
  });
  // Pick up edits made elsewhere (Lore, a text editor) when coming back to the tab.
  window.addEventListener('focus', () => load());
  state.selected = selectionFromHash();
  load({ resetView: true });
}

init();
