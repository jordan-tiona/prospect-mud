// MUD editor core: pure editing logic over a sector document, no DOM.
// Loaded by the page (window.EditorCore) and by Node's test runner (require).
// Every operation mutates the document it's given and throws an Error with a
// player-readable reason when the edit isn't allowed; the page applies it to a
// copy, so a refused edit changes nothing.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.EditorCore = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const ID_RE = /^[a-z0-9_]+$/;

  const OPPOSITES = {
    north: ['south', 's'], south: ['north', 'n'], east: ['west', 'w'], west: ['east', 'e'],
    northeast: ['southwest', 'sw'], southwest: ['northeast', 'ne'],
    northwest: ['southeast', 'se'], southeast: ['northwest', 'nw'],
    up: ['down', 'd'], down: ['up', 'u'], in: ['out', 'o'], out: ['in', 'i'],
  };
  const SHORT = { n: 'north', s: 'south', e: 'east', w: 'west', ne: 'northeast', sw: 'southwest',
    nw: 'northwest', se: 'southeast', u: 'up', d: 'down' };
  const SHORT_OF = Object.fromEntries(Object.entries(SHORT).map(([k, v]) => [v, k]));

  /** The usual way back for a direction (north -> south, alias s), or null. */
  function opposite(key) {
    const word = SHORT[String(key).trim().toLowerCase()] || String(key).trim().toLowerCase();
    const found = OPPOSITES[word];
    return found ? { key: found[0], aliases: [found[1]] } : null;
  }

  /** Standard short alias for a direction word (north -> n), or none. */
  function shortAliases(key) {
    const short = SHORT_OF[String(key).trim().toLowerCase()];
    return short ? [short] : [];
  }

  function parseAliases(text) {
    const seen = new Set();
    return String(text || '').split(',').map((a) => a.trim()).filter((a) => a && !seen.has(a.toLowerCase()) && seen.add(a.toLowerCase()));
  }

  function clone(doc) {
    return JSON.parse(JSON.stringify(doc));
  }

  function fail(message) {
    throw new Error(message);
  }

  function idTaken(doc, id) {
    return id in doc.rooms || id in doc.entities;
  }

  function checkNewId(doc, id) {
    if (!ID_RE.test(id || '')) fail('IDs use lowercase letters, digits and underscores only.');
    if (idTaken(doc, id)) fail(`The ID "${id}" is already used in this sector.`);
  }

  /** Index of the exit record joining rooms a and b (either direction), or -1. */
  function pairIndex(doc, a, b, exceptIndex = -1) {
    return doc.exits.findIndex((ex, i) => i !== exceptIndex
      && ((ex.from === a && ex.to === b) || (ex.from === b && ex.to === a)));
  }

  // ----------------------------------------------------------------- rooms

  function addRoom(doc, { id, title, content, x = 0, y = 0 }) {
    checkNewId(doc, id);
    if (!String(title || '').trim()) fail('A room needs a title.');
    const room = { title: String(title).trim(), editor: { x: Math.round(x), y: Math.round(y) } };
    if (content) room.content = content;
    doc.rooms[id] = room;
    return doc;
  }

  function setRoom(doc, id, fields) {
    const room = doc.rooms[id] || fail(`No room "${id}".`);
    if ('title' in fields) {
      if (!String(fields.title || '').trim()) fail('A room needs a title.');
      const title = String(fields.title).trim();
      // Remember the old title, so check can find prose that still uses it.
      const same = (a, b) => a.toLowerCase() === b.toLowerCase();
      const former = (room.editor?.former_titles || []).filter((t) => !same(t, title));
      if (room.title && !same(room.title, title) && !former.some((t) => same(t, room.title))) former.push(room.title);
      room.title = title;
      room.editor = { ...(room.editor || {}), former_titles: former };
      if (!former.length) delete room.editor.former_titles;
    }
    if ('content' in fields) {
      if (fields.content) room.content = fields.content;
      else delete room.content;
    }
    if ('notes' in fields) {
      if (fields.notes) room.notes = fields.notes;
      else delete room.notes;
    }
    if ('position' in fields) room.editor = { ...(room.editor || {}), x: Math.round(fields.position.x), y: Math.round(fields.position.y) };
    return doc;
  }

  /** Stop tracking an old title (the prose is fine as it is, or was updated). */
  function forgetFormerTitle(doc, id, title) {
    const room = doc.rooms[id] || fail(`No room "${id}".`);
    const former = (room.editor?.former_titles || []).filter((t) => t !== title);
    if (former.length) room.editor.former_titles = former;
    else if (room.editor) delete room.editor.former_titles;
    return doc;
  }

  /** Removes a room and every exit touching it. Refuses while anything is placed there. */
  function removeRoom(doc, id) {
    if (!doc.rooms[id]) fail(`No room "${id}".`);
    const here = Object.keys(doc.entities).filter((e) => doc.entities[e].room === id);
    if (here.length) fail(`Move or remove what's placed here first (${here.join(', ')}).`);
    doc.exits = doc.exits.filter((ex) => ex.from !== id && ex.to !== id);
    delete doc.rooms[id];
    if (doc.map_anchor === id) delete doc.map_anchor;
    return doc;
  }

  // ------------------------------------------------------------ map grid
  // Grid coordinates are worked out from the anchor and exits (check.py's
  // map_grid); the document holds only the anchor and any pins.

  function setMapAnchor(doc, id) {
    if (!doc.rooms[id]) fail(`No room "${id}".`);
    doc.map_anchor = id;
    return doc;
  }

  /** Pin a room to {x, y, z} (whole numbers), or unpin it with null. */
  function setMapPin(doc, id, pin) {
    const room = doc.rooms[id] || fail(`No room "${id}".`);
    if (pin === null) {
      delete room.map_pin;
      return doc;
    }
    const clean = {};
    for (const axis of ['x', 'y', 'z']) {
      const value = Number(String(pin[axis] ?? '').trim() || NaN);
      if (!Number.isInteger(value)) fail(`A pin needs whole numbers for x, y and z (${axis} is "${pin[axis] ?? ''}").`);
      clean[axis] = value;
    }
    room.map_pin = clean;
    return doc;
  }

  // ----------------------------------------------------------------- exits

  function cleanReturn(back) {
    if (!back) return null;
    if (!String(back.key || '').trim()) fail('The way back needs a key, or make the exit one-way.');
    return { key: String(back.key).trim(), aliases: parseAliases((back.aliases || []).join(',')) };
  }

  /** One record per pair of rooms (owner rule), keyed from `from`'s side. */
  function addExit(doc, { from, to, key, aliases = [], back = null }) {
    if (!doc.rooms[from] || !doc.rooms[to]) fail('Both ends of an exit must be rooms in this sector.');
    if (from === to) fail("An exit can't lead back into the same room.");
    if (!String(key || '').trim()) fail('An exit needs a key (the command players type).');
    if (pairIndex(doc, from, to) !== -1) fail('These rooms are already connected - edit that exit instead (extra words go in its aliases).');
    doc.exits.push({ from, to, key: String(key).trim(), aliases: parseAliases(aliases.join(',')), return: cleanReturn(back) });
    return doc;
  }

  /**
   * Edit exit `index` as seen from `room` (either end). `out` is the exit
   * leaving `room`, `back` the way back (null = one-way). For a one-way record
   * that leads *into* `room`, `out` must be null (there's no exit out of here).
   */
  function setExit(doc, index, room, { out, back }) {
    const ex = doc.exits[index] || fail('No such exit.');
    if (room === ex.from) {
      if (!out || !String(out.key || '').trim()) fail('An exit needs a key (the command players type).');
      ex.key = String(out.key).trim();
      ex.aliases = parseAliases((out.aliases || []).join(','));
      ex.return = cleanReturn(back);
    } else if (room === ex.to) {
      // seen from the far end: "out" is the record's return, "back" its forward exit
      if (!back || !String(back.key || '').trim()) fail('The exit from the other room needs a key.');
      ex.key = String(back.key).trim();
      ex.aliases = parseAliases((back.aliases || []).join(','));
      ex.return = out ? cleanReturn(out) : null;
    } else {
      fail('That exit is not connected to this room.');
    }
    return doc;
  }

  function removeExit(doc, index) {
    if (!doc.exits[index]) fail('No such exit.');
    doc.exits.splice(index, 1);
    return doc;
  }

  /** Exits as seen from one room: [{index, out: {key, aliases}|null, back: {...}|null, other}]. */
  function exitsOf(doc, room) {
    const result = [];
    doc.exits.forEach((ex, index) => {
      if (ex.from === room) {
        result.push({ index, other: ex.to, out: { key: ex.key, aliases: ex.aliases || [] }, back: ex.return || null });
      } else if (ex.to === room) {
        result.push({ index, other: ex.from, out: ex.return || null, back: { key: ex.key, aliases: ex.aliases || [] } });
      }
    });
    return result;
  }

  // -------------------------------------------------------------- entities

  function addEntity(doc, { id, kind, room, content, aliases = [], params = {} }) {
    checkNewId(doc, id);
    if (!doc.rooms[room]) fail('Place it in a room of this sector.');
    if (!kind) fail('Choose what kind of thing it is.');
    const entity = { kind, room };
    if (content) entity.content = content;
    const cleanAliases = parseAliases(aliases.join(','));
    if (cleanAliases.length) entity.aliases = cleanAliases;
    const cleanParams = Object.fromEntries(Object.entries(params).filter(([, v]) => v));
    if (Object.keys(cleanParams).length) entity.params = cleanParams;
    doc.entities[id] = entity;
    return doc;
  }

  function setEntity(doc, id, fields) {
    const entity = doc.entities[id] || fail(`No entity "${id}".`);
    if ('room' in fields) {
      if (!doc.rooms[fields.room]) fail('Place it in a room of this sector.');
      if (fields.room !== entity.room) {
        // Leaving a container behind takes it out; a container's contents move with it.
        delete entity.inside;
        for (const other of Object.values(doc.entities)) if (other.inside === id) other.room = fields.room;
      }
      entity.room = fields.room;
    }
    if ('inside' in fields) {
      if (!fields.inside) delete entity.inside;
      else {
        const container = doc.entities[fields.inside];
        if (!container || fields.inside === id) fail('Put it inside another thing in this sector.');
        if (container.room !== entity.room) fail('Its container has to be in the same room.');
        if (container.inside) fail('That is itself inside something.');
        entity.inside = fields.inside;
      }
    }
    if ('aliases' in fields) {
      const aliases = parseAliases(fields.aliases.join(','));
      if (aliases.length) entity.aliases = aliases;
      else delete entity.aliases;
    }
    if ('params' in fields) {
      const params = Object.fromEntries(Object.entries(fields.params).filter(([, v]) => v));
      if (Object.keys(params).length) entity.params = params;
      else delete entity.params;
    }
    if ('notes' in fields) {
      if (fields.notes) entity.notes = fields.notes;
      else delete entity.notes;
    }
    return doc;
  }

  function removeEntity(doc, id) {
    if (!doc.entities[id]) fail(`No entity "${id}".`);
    delete doc.entities[id];
    // What was inside it stays in the room, loose.
    for (const other of Object.values(doc.entities)) if (other.inside === id) delete other.inside;
    return doc;
  }

  // ------------------------------------------------------- candidate tray

  /** Content paths the document uses (rooms and entities). */
  function usedContent(doc) {
    return new Set([...Object.values(doc.rooms), ...Object.values(doc.entities)].map((x) => x.content).filter(Boolean));
  }

  /**
   * Tray candidates for the open document: the server's unplaced files minus
   * any the unsaved document already uses, plus `released` files the saved
   * sector used but the unsaved document no longer does.
   */
  function trayItems(unplaced, released, doc) {
    const used = usedContent(doc);
    const seen = new Set();
    return [...unplaced, ...released].filter((item) => !used.has(item.path) && !seen.has(item.path) && seen.add(item.path));
  }

  /**
   * Group candidates by their request: line. Requests sort first (by ID), stray
   * files (no request) last; dismissed files are kept apart in each group.
   */
  function groupByRequest(items) {
    const groups = new Map();
    for (const item of items) {
      const key = item.request || '';
      if (!groups.has(key)) groups.set(key, { request: item.request || null, active: [], dismissed: [] });
      groups.get(key)[item.dismissed ? 'dismissed' : 'active'].push(item);
    }
    return [...groups.values()].sort((a, b) => (a.request === null) - (b.request === null)
      || String(a.request).localeCompare(String(b.request)));
  }

  /** The ID a candidate gets: its header's ID field, else its file name. */
  function candidateId(file, idField) {
    const declared = file.fields && file.fields[idField];
    return declared || file.path.split('/').pop().replace(/\.md$/, '');
  }

  /**
   * Place a candidate file: as a room (kind 'room', at x/y, titled `title` or
   * its heading) or as an entity of `kind` in `room`. Draft content can be
   * placed; only export needs approval.
   */
  function placeCandidate(doc, file, { kind, idField, title, room, x = 0, y = 0 }) {
    const id = candidateId(file, idField);
    if (kind === 'room') return addRoom(doc, { id, title: title || file.heading || id, content: file.path, x, y });
    return addEntity(doc, { id, kind, room, content: file.path });
  }

  // --------------------------------------------------------------- history

  /** Undo/redo over JSON snapshots of the document. */
  class History {
    constructor(limit = 200) {
      this.past = [];
      this.future = [];
      this.limit = limit;
    }

    record(doc) {
      this.past.push(JSON.stringify(doc));
      if (this.past.length > this.limit) this.past.shift();
      this.future = [];
    }

    undo(current) {
      if (!this.past.length) return null;
      this.future.push(JSON.stringify(current));
      return JSON.parse(this.past.pop());
    }

    redo(current) {
      if (!this.future.length) return null;
      this.past.push(JSON.stringify(current));
      return JSON.parse(this.future.pop());
    }

    get canUndo() { return this.past.length > 0; }

    get canRedo() { return this.future.length > 0; }
  }

  return {
    ID_RE, opposite, shortAliases, parseAliases, clone, pairIndex, idTaken,
    addRoom, setRoom, forgetFormerTitle, removeRoom, setMapAnchor, setMapPin, addExit, setExit, removeExit, exitsOf,
    addEntity, setEntity, removeEntity, usedContent, trayItems, groupByRequest, candidateId, placeCandidate, History,
  };
});
