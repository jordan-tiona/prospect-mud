// MUD editor viewer (milestone 5a): read-only map and panels over the local API.
'use strict';

const BOX_W = 280;
const BOX_H = 124;
const SVG_NS = 'http://www.w3.org/2000/svg';

const state = {
  sectors: [],
  sectorId: null,
  data: null,
  unplaced: [],
  selected: { type: 'overview' },
  view: null, // {x, y, w, h} - the SVG viewBox
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

function approvalChip(file) {
  if (!file) return '<span class="badge-chip err">no content file</span>';
  if (!file.exists) return '<span class="badge-chip err">file missing</span>';
  const approval = file.approval || 'no approval field';
  const cls = approval === 'Approved' ? 'ok' : 'warn';
  const status = file.status ? `<span class="badge-chip">${esc(file.status)}</span>` : '';
  return `<span class="badge-chip ${cls}">${esc(approval)}</span>${status}`;
}

function displayName(id, item) {
  return (item.file && item.file.heading) || item.title || id;
}

// Which room an issue belongs to, from check.py's `where` text.
function issueRoom(issue) {
  const d = state.data;
  let m = /^room (\S+)/.exec(issue.where);
  if (m) return d.rooms[m[1]] ? m[1] : null;
  m = /^entity (\S+)/.exec(issue.where);
  if (m) return d.entities[m[1]]?.room ?? null;
  m = /^exit\[\d+\] (\S+?)->/.exec(issue.where);
  if (m) return d.rooms[m[1]] ? m[1] : null;
  return null;
}

function issuesFor(roomId) {
  return state.data.issues.filter((i) => issueRoom(i) === roomId);
}

function entitiesIn(roomId) {
  return Object.entries(state.data.entities).filter(([, e]) => e.room === roomId);
}

// Every exit leaving a room: forward records and the returns of records pointing here.
function exitsFrom(roomId) {
  const out = [];
  for (const ex of state.data.exits) {
    if (ex.from === roomId) out.push({ key: ex.key, aliases: ex.aliases || [], to: ex.to });
    if (ex.to === roomId && ex.return) out.push({ key: ex.return.key, aliases: ex.return.aliases || [], to: ex.from });
  }
  return out;
}

// ---------------------------------------------------------------- data

async function getJSON(url) {
  const res = await fetch(url, { cache: 'no-store' });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `${res.status} ${res.statusText}`);
  return body;
}

async function load(keepView = false) {
  const errorBox = $('error');
  try {
    state.sectors = (await getJSON('/api/sectors')).sectors;
    if (!state.sectors.includes(state.sectorId)) state.sectorId = state.sectors[0] ?? null;
    if (!state.sectorId) throw new Error('No sector files found under sectors/.');
    state.data = await getJSON(`/api/sector/${state.sectorId}`);
    state.unplaced = (await getJSON('/api/unplaced')).unplaced;
    errorBox.hidden = true;
  } catch (err) {
    errorBox.textContent = `Couldn't load: ${err.message}`;
    errorBox.hidden = false;
    return;
  }
  const sel = state.selected;
  if ((sel.type === 'room' && !state.data.rooms[sel.id]) || (sel.type === 'entity' && !state.data.entities[sel.id])) {
    state.selected = { type: 'overview' };
  }
  renderBar();
  renderMap(keepView);
  renderPanel();
}

// ----------------------------------------------------------------- bar

function renderBar() {
  const picker = $('sector');
  picker.innerHTML = state.sectors.map((s) => `<option${s === state.sectorId ? ' selected' : ''}>${esc(s)}</option>`).join('');

  const issues = state.data.issues;
  const errors = issues.filter((i) => i.level === 'error').length;
  const warnings = issues.filter((i) => i.level === 'warning').length;
  const btn = $('issues-btn');
  btn.textContent = errors || warnings ? `Check: ${errors} error${errors === 1 ? '' : 's'}, ${warnings} warning${warnings === 1 ? '' : 's'}` : 'Check: clean';
  btn.className = `pill ${errors ? 'err' : warnings ? 'warn' : 'ok'}`;

  const m = state.data.manifest;
  const pill = $('manifest');
  const label = { fresh: 'Manifest up to date', stale: 'Manifest stale', not_exported: 'Not exported' }[m.state];
  pill.textContent = label;
  pill.className = `pill static ${m.state === 'fresh' ? 'ok' : m.state === 'stale' ? 'warn' : ''}`;
  pill.title = m.state === 'stale' ? `Changed since the last export:\n${m.changed.join('\n')}` : '';

  $('unplaced-btn').textContent = `Unplaced: ${state.unplaced.length}`;
}

// ----------------------------------------------------------------- map

function roomPositions() {
  const pos = {};
  let fallback = 0;
  for (const [id, room] of Object.entries(state.data.rooms)) {
    if (room.editor && Number.isFinite(room.editor.x) && Number.isFinite(room.editor.y)) {
      pos[id] = { x: room.editor.x, y: room.editor.y };
    } else {
      pos[id] = { x: (fallback % 4) * 560, y: 2000 + Math.floor(fallback / 4) * 430 };
      fallback += 1;
    }
  }
  return pos;
}

// Where the line from a box's centre towards (tx, ty) leaves the box.
function edgePoint(cx, cy, tx, ty) {
  const dx = tx - cx;
  const dy = ty - cy;
  if (!dx && !dy) return { x: cx, y: cy };
  const scale = Math.min(BOX_W / 2 / Math.abs(dx || 1e-9), BOX_H / 2 / Math.abs(dy || 1e-9));
  return { x: cx + dx * Math.min(scale, 1), y: cy + dy * Math.min(scale, 1) };
}

function renderMap(keepView) {
  const map = $('map');
  map.replaceChildren();
  const defs = svg('defs', {}, map);
  const marker = svg('marker', { id: 'arrow', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 8, markerHeight: 8, orient: 'auto-start-reverse' }, defs);
  svg('path', { d: 'M0,0 L10,5 L0,10 z' }, marker);

  const pos = roomPositions();
  const centre = (id) => ({ x: pos[id].x + BOX_W / 2, y: pos[id].y + BOX_H / 2 });
  const exitLayer = svg('g', {}, map);
  const roomLayer = svg('g', {}, map);

  for (const ex of state.data.exits) {
    if (!pos[ex.from] || !pos[ex.to]) continue;
    const a = centre(ex.from);
    const b = centre(ex.to);
    const p = edgePoint(a.x, a.y, b.x, b.y);
    const q = edgePoint(b.x, b.y, a.x, a.y);
    const attrs = { x1: p.x, y1: p.y, x2: q.x, y2: q.y, class: 'exit-line' };
    if (!ex.return) attrs['marker-end'] = 'url(#arrow)';
    svg('line', attrs, exitLayer);
    // Label beside the line's midpoint (offset along its normal) so it doesn't sit on the line.
    const len = Math.hypot(q.x - p.x, q.y - p.y) || 1;
    const nx = -(q.y - p.y) / len;
    const ny = (q.x - p.x) / len;
    const side = nx < 0 ? -1 : 1; // keep labels to the right of vertical lines
    const label = svg('text', {
      x: (p.x + q.x) / 2 + nx * 14 * side, y: (p.y + q.y) / 2 + ny * 14 * side + 5,
      'text-anchor': Math.abs(nx) > 0.5 ? 'start' : 'middle', class: 'exit-label',
    }, exitLayer);
    label.textContent = ex.return ? `${ex.key} / ${ex.return.key}` : `${ex.key} (one-way)`;
  }

  for (const [id, room] of Object.entries(state.data.rooms)) {
    const { x, y } = pos[id];
    const file = room.file;
    const cls = !file || !file.exists ? 'missing' : file.approval === 'Approved' ? '' : 'draft';
    const sel = state.selected;
    const selected = (sel.type === 'room' && sel.id === id)
      || (sel.type === 'entity' && state.data.entities[sel.id]?.room === id);
    const g = svg('g', { class: `room ${cls}${selected ? ' selected' : ''}`, transform: `translate(${x},${y})`, tabindex: 0 }, roomLayer);
    svg('rect', { class: 'box', width: BOX_W, height: BOX_H, rx: 10 }, g);
    const title = svg('text', { x: 16, y: 38, class: 'title' }, g);
    title.textContent = room.title || id;
    const count = entitiesIn(id).length;
    const sub = svg('text', { x: 16, y: 72, class: 'sub' }, g);
    sub.textContent = `${count} placed · ${file && file.exists ? (file.approval || 'no approval') : 'no prose'}`;
    const id_text = svg('text', { x: 16, y: 102, class: 'sub id' }, g);
    id_text.textContent = id;

    const roomIssues = issuesFor(id);
    const worst = roomIssues.some((i) => i.level === 'error') ? 'err' : roomIssues.some((i) => i.level === 'warning') ? 'warn' : null;
    if (worst) {
      svg('circle', { cx: BOX_W - 22, cy: 24, r: 15, class: `badge ${worst}` }, g);
      const n = svg('text', { x: BOX_W - 22, y: 29, 'text-anchor': 'middle', class: 'badge-text' }, g);
      n.textContent = roomIssues.length;
    }
    const choose = () => select({ type: 'room', id });
    g.addEventListener('click', choose);
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter') choose(); });
  }

  if (!keepView || !state.view) fit(pos);
  applyView();
}

function fit(pos = roomPositions()) {
  const xs = Object.values(pos).map((p) => p.x);
  const ys = Object.values(pos).map((p) => p.y);
  if (!xs.length) { state.view = { x: 0, y: 0, w: 1000, h: 800 }; return; }
  const pad = 120;
  const minX = Math.min(...xs) - pad;
  const minY = Math.min(...ys) - pad;
  state.view = { x: minX, y: minY, w: Math.max(...xs) + BOX_W + pad - minX, h: Math.max(...ys) + BOX_H + pad - minY };
}

function applyView() {
  const { x, y, w, h } = state.view;
  $('map').setAttribute('viewBox', `${x} ${y} ${w} ${h}`);
}

function setupPanZoom() {
  const map = $('map');
  let drag = null;
  map.addEventListener('pointerdown', (e) => {
    if (e.target.closest('.room')) return;
    drag = { x: e.clientX, y: e.clientY, view: { ...state.view } };
    map.setPointerCapture(e.pointerId);
    map.classList.add('panning');
  });
  map.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const rect = map.getBoundingClientRect();
    const k = Math.max(drag.view.w / rect.width, drag.view.h / rect.height);
    state.view = { ...drag.view, x: drag.view.x - (e.clientX - drag.x) * k, y: drag.view.y - (e.clientY - drag.y) * k };
    applyView();
  });
  const end = () => { drag = null; map.classList.remove('panning'); };
  map.addEventListener('pointerup', end);
  map.addEventListener('pointercancel', end);
  map.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = map.getBoundingClientRect();
    const v = state.view;
    const k = Math.max(v.w / rect.width, v.h / rect.height);
    // the SVG point under the cursor stays put (approximately, with preserveAspectRatio centring)
    const px = v.x + (e.clientX - rect.left) * k;
    const py = v.y + (e.clientY - rect.top) * k;
    const factor = Math.exp(e.deltaY * 0.0015);
    const w = Math.min(Math.max(v.w * factor, 300), 40000);
    const s = w / v.w;
    state.view = { x: px - (px - v.x) * s, y: py - (py - v.y) * s, w, h: v.h * s };
    applyView();
  }, { passive: false });
}

// --------------------------------------------------------------- panel

function select(selection) {
  const d = state.data;
  if ((selection.type === 'room' && !d.rooms[selection.id]) || (selection.type === 'entity' && !d.entities[selection.id])) {
    selection = { type: 'overview' };
  }
  state.selected = selection;
  // #room=<id> / #entity=<id>: reloads and links keep the selection.
  const hash = ['room', 'entity'].includes(selection.type) ? `#${selection.type}=${encodeURIComponent(selection.id)}` : '';
  if (location.hash !== hash) history.replaceState(null, '', hash || location.pathname);
  renderMap(true);
  renderPanel();
}

function selectionFromHash() {
  const m = /^#(room|entity)=(.+)$/.exec(location.hash);
  return m ? { type: m[1], id: decodeURIComponent(m[2]) } : { type: 'overview' };
}

function renderPanel() {
  const panel = $('panel');
  const s = state.selected;
  const html = s.type === 'room' ? roomPanel(s.id)
    : s.type === 'entity' ? entityPanel(s.id)
    : s.type === 'issues' ? issuesPanel()
    : s.type === 'unplaced' ? unplacedPanel()
    : s.type === 'candidate' ? candidatePanel(s.path)
    : overviewPanel();
  panel.innerHTML = html;
  panel.scrollTop = 0;
  panel.querySelectorAll('[data-go]').forEach((el) => {
    el.addEventListener('click', () => {
      const [type, id] = el.dataset.go.split(':');
      select(type === 'candidate' ? { type, path: decodeURIComponent(id) } : { type, id });
    });
  });
}

const go = (type, id, label) => `<button class="link" type="button" data-go="${type}:${esc(id)}">${esc(label)}</button>`;

function overviewPanel() {
  const d = state.data;
  const rooms = Object.keys(d.rooms).length;
  const entities = Object.keys(d.entities).length;
  const exits = d.exits.reduce((n, e) => n + (e.return ? 2 : 1), 0);
  const errors = d.issues.filter((i) => i.level === 'error').length;
  return `
    <h2>${esc(d.sector_id)}</h2>
    <p class="muted">Sector overview. Click a room on the map to inspect it.</p>
    <dl class="kv">
      <dt>Sector</dt><dd class="mono">${esc(d.sector_id)}</dd>
      <dt>Rooms</dt><dd>${rooms}</dd>
      <dt>Exits</dt><dd>${exits} (one-way records counted once)</dd>
      <dt>Placed entities</dt><dd>${entities}</dd>
      <dt>Check</dt><dd>${d.issues.length ? `${errors} error(s), ${d.issues.length - errors} other` : 'clean'}</dd>
      <dt>Manifest</dt><dd>${esc(d.manifest.state.replace('_', ' '))}</dd>
      <dt>Unplaced content</dt><dd>${state.unplaced.length}</dd>
    </dl>
    ${d.notes ? `<h3>Notes</h3><div class="prose">${prose(d.notes)}</div>` : ''}
    <h3>Rooms</h3>
    <ul class="list">${Object.entries(d.rooms).map(([id, r]) => `<li>${go('room', id, r.title || id)}<span class="kind">${esc(id)}</span></li>`).join('')}</ul>`;
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
  const issues = [...state.data.issues].sort((a, b) => order[a.level] - order[b.level]);
  const m = state.data.manifest;
  const manifest = m.state === 'stale'
    ? `<h3>Manifest</h3><p>Changed since the last export:</p><ul>${m.changed.map((c) => `<li class="path">${esc(c)}</li>`).join('')}</ul>`
    : '';
  return `<h2>Check</h2><p class="muted">The same checks as <code>ops/editor/check.py</code> for this sector.</p>${issueList(issues)}${manifest}`;
}

function roomPanel(id) {
  const room = state.data.rooms[id];
  const file = room.file;
  const sections = file && file.exists ? file.sections : {};
  const exits = exitsFrom(id);
  const here = entitiesIn(id);
  const roomIssues = issuesFor(id);
  return `
    <h2>${esc(room.title || id)}</h2>
    <div class="badges">${approvalChip(file)}<span class="badge-chip">room · ${esc(id)}</span></div>
    <div class="path">${esc(file ? `content/${file.path}` : '(no content file)')}</div>
    ${roomIssues.length ? `<h3>Issues</h3>${issueList(roomIssues)}` : ''}
    ${sections.Glance ? `<h3>Glance</h3><div class="prose">${prose(sections.Glance)}</div>` : ''}
    <h3>Description</h3><div class="prose">${prose(sections.Description)}</div>
    <h3>Exits</h3>
    ${exits.length ? `<ul class="list">${exits.map((e) => `<li><span class="dir">${esc(e.key)}</span>${state.data.rooms[e.to] ? go('room', e.to, state.data.rooms[e.to].title || e.to) : `<span class="badge-chip err">unknown room ${esc(e.to)}</span>`}${e.aliases.length ? `<span class="kind">${esc(e.aliases.join(', '))}</span>` : ''}</li>`).join('')}</ul>` : '<p class="muted">No exits.</p>'}
    <h3>Here (${here.length})</h3>
    ${here.length ? `<ul class="list">${here.map(([eid, e]) => `<li>${go('entity', eid, displayName(eid, e))}<span class="kind">${esc(e.kind)}</span>${approvalChip(e.file)}</li>`).join('')}</ul>` : '<p class="muted">Nothing placed here.</p>'}
    ${room.notes ? `<h3>Notes</h3><div class="prose">${prose(room.notes)}</div>` : ''}`;
}

function sectionsHTML(file, kind) {
  if (!file || !file.exists) return '';
  const sections = Object.entries(file.sections || {});
  if (kind === 'talk_npc') {
    // Personas are long prompt text: show the look description, keep the rest folded.
    const desc = file.fields?.desc;
    const probe = file.fields?.probe_desc;
    return `<h3>Look description</h3><div class="prose">${desc ? prose(desc) : '<p class="muted">None authored (the persona has no <code>desc:</code> field), so players see the default.</p>'}</div>
      <h3>Probe description</h3><div class="prose">${probe ? prose(probe) : '<p class="muted">None authored (no <code>probe_desc:</code> field), so <code>probe</code> shows the look description.</p>'}</div>
      <h3>Persona</h3><details><summary>${sections.length} section(s): ${esc(sections.map(([h]) => h).join(', '))}</summary>
      ${sections.map(([h, body]) => `<h3>${esc(h)}</h3><div class="prose">${prose(body)}</div>`).join('')}</details>`;
  }
  return sections.map(([h, body]) => `<h3>${esc(h)}</h3><div class="prose">${prose(body)}</div>`).join('');
}

function entityPanel(id) {
  const e = state.data.entities[id];
  const room = state.data.rooms[e.room];
  const params = Object.entries(e.params || {});
  return `
    <p>${room ? go('room', e.room, `← ${room.title || e.room}`) : `<span class="muted">room ${esc(e.room)} not found</span>`}</p>
    <h2>${esc(displayName(id, e))}</h2>
    <div class="badges">${approvalChip(e.file)}<span class="badge-chip">${esc(e.kind)} · ${esc(id)}</span></div>
    <div class="path">${esc(e.file ? `content/${e.file.path}` : '(no content file)')}</div>
    ${(e.aliases || []).length || params.length ? `<h3>Structure</h3><dl class="kv">
      ${(e.aliases || []).length ? `<dt>aliases</dt><dd>${esc(e.aliases.join(', '))}</dd>` : ''}
      ${params.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` : ''}
    ${sectionsHTML(e.file, e.kind)}
    ${e.notes ? `<h3>Notes</h3><div class="prose">${prose(e.notes)}</div>` : ''}`;
}

function unplacedPanel() {
  if (!state.unplaced.length) {
    return '<h2>Unplaced content</h2><p class="muted">Every content file is placed in a sector.</p>';
  }
  const groups = {};
  for (const item of state.unplaced) (groups[item.request || ''] ||= []).push(item);
  const keys = Object.keys(groups).sort((a, b) => (a === '') - (b === '') || a.localeCompare(b));
  return `<h2>Unplaced content</h2>
    <p class="muted">Content files no sector uses, grouped by their <code>request:</code> line. Placing comes in milestone 5c.</p>
    ${keys.map((k) => `<h3>${esc(k || 'No request')}</h3><ul class="list">${groups[k].map((item) => `<li>${go('candidate', encodeURIComponent(item.path), item.heading || item.path)}<span class="kind">${esc(item.kind_folder)}</span>${approvalChip(item)}</li>`).join('')}</ul>`).join('')}`;
}

function candidatePanel(path) {
  const item = state.unplaced.find((u) => u.path === path);
  if (!item) return unplacedPanel();
  return `
    <p>${go('unplaced', '', '← Unplaced content')}</p>
    <h2>${esc(item.heading || item.path)}</h2>
    <div class="badges">${approvalChip(item)}${item.request ? `<span class="badge-chip">${esc(item.request)}</span>` : ''}</div>
    <div class="path">content/${esc(item.path)}</div>
    ${sectionsHTML(item, item.kind_folder === 'npcs' ? 'talk_npc' : '')}`;
}

// ---------------------------------------------------------------- init

function init() {
  setupPanZoom();
  $('reload').addEventListener('click', () => load(true));
  $('issues-btn').addEventListener('click', () => select({ type: 'issues' }));
  $('unplaced-btn').addEventListener('click', () => select({ type: 'unplaced' }));
  $('sector').addEventListener('change', (e) => {
    state.sectorId = e.target.value;
    state.selected = { type: 'overview' };
    load(false);
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.closest('input, select, textarea')) return;
    if (e.key === 'f' || e.key === 'F') { fit(); applyView(); }
    if (e.key === 'Escape') select({ type: 'overview' });
  });
  // Pick up edits made elsewhere (Lore, a text editor) when coming back to the tab.
  window.addEventListener('focus', () => load(true));
  state.selected = selectionFromHash();
  load(false);
}

init();
