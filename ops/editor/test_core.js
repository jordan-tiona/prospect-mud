// Tests for the MUD editor's pure editing logic (static/core.js).
// Run from the repo root:  node --test ops/editor/test_core.js
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('./static/core.js');

function sector() {
  return {
    format_version: 1,
    sector_id: 'test',
    rooms: { a: { title: 'A', editor: { x: 0, y: 0 } }, b: { title: 'B', editor: { x: 500, y: 0 } } },
    exits: [{ from: 'a', to: 'b', key: 'east', aliases: ['e'], return: { key: 'west', aliases: ['w'] } }],
    entities: { thing: { kind: 'ambient_object', room: 'a', content: 'ambient/objects/thing.md' } },
  };
}

test('opposite directions, short forms included', () => {
  assert.deepEqual(core.opposite('north'), { key: 'south', aliases: ['s'] });
  assert.deepEqual(core.opposite('NE'), { key: 'southwest', aliases: ['sw'] });
  assert.deepEqual(core.opposite('up'), { key: 'down', aliases: ['d'] });
  assert.equal(core.opposite('enter shop'), null);
  assert.deepEqual(core.shortAliases('northwest'), ['nw']);
});

test('aliases parse from comma text, trimmed and de-duplicated', () => {
  assert.deepEqual(core.parseAliases(' door, Door ,gate,, '), ['door', 'gate']);
});

test('rooms: add, retitle, move, refuse bad or taken IDs', () => {
  const doc = sector();
  core.addRoom(doc, { id: 'c', title: ' C ', x: 10.6, y: -3.2 });
  assert.deepEqual(doc.rooms.c, { title: 'C', editor: { x: 11, y: -3 } });
  assert.throws(() => core.addRoom(doc, { id: 'Bad Id', title: 'x' }), /lowercase/);
  assert.throws(() => core.addRoom(doc, { id: 'thing', title: 'x' }), /already used/);
  assert.throws(() => core.addRoom(doc, { id: 'd', title: '  ' }), /title/);
  core.setRoom(doc, 'c', { title: 'Sea', position: { x: 40, y: 50 } });
  assert.deepEqual(doc.rooms.c, { title: 'Sea', editor: { x: 40, y: 50 } });
});

test('placeholder rooms have no content until it is set', () => {
  const doc = sector();
  core.addRoom(doc, { id: 'c', title: 'C' });
  assert.equal('content' in doc.rooms.c, false);
  core.setRoom(doc, 'c', { content: 'rooms/c.md' });
  assert.equal(doc.rooms.c.content, 'rooms/c.md');
  core.setRoom(doc, 'c', { content: '' });
  assert.equal('content' in doc.rooms.c, false);
});

test('removing a room takes its exits, but not while things are placed there', () => {
  const doc = sector();
  assert.throws(() => core.removeRoom(doc, 'a'), /thing/);
  core.removeRoom(doc, 'b');
  assert.deepEqual(doc.exits, []);
  assert.equal('b' in doc.rooms, false);
});

test('one connection per pair of rooms, either direction', () => {
  const doc = sector();
  assert.throws(() => core.addExit(doc, { from: 'b', to: 'a', key: 'door' }), /already connected/);
  core.addRoom(doc, { id: 'c', title: 'C' });
  core.addExit(doc, { from: 'b', to: 'c', key: 'up', aliases: ['u'], back: { key: 'down', aliases: ['d'] } });
  assert.equal(doc.exits.length, 2);
  assert.throws(() => core.addExit(doc, { from: 'c', to: 'c', key: 'x' }), /same room/);
  assert.throws(() => core.addExit(doc, { from: 'a', to: 'c', key: ' ' }), /key/);
});

test('editing an exit from either end updates the one record', () => {
  const doc = sector();
  core.setExit(doc, 0, 'a', { out: { key: 'north', aliases: ['n'] }, back: { key: 'south', aliases: ['s'] } });
  assert.deepEqual(doc.exits[0], { from: 'a', to: 'b', key: 'north', aliases: ['n'], return: { key: 'south', aliases: ['s'] } });
  core.setExit(doc, 0, 'b', { out: { key: 'down', aliases: [] }, back: { key: 'up', aliases: [] } });
  assert.deepEqual(doc.exits[0], { from: 'a', to: 'b', key: 'up', aliases: [], return: { key: 'down', aliases: [] } });
  core.setExit(doc, 0, 'a', { out: { key: 'up', aliases: [] }, back: null });
  assert.equal(doc.exits[0].return, null);
});

test('exits as seen from each end', () => {
  const doc = sector();
  assert.deepEqual(core.exitsOf(doc, 'a'), [{ index: 0, other: 'b', out: { key: 'east', aliases: ['e'] }, back: { key: 'west', aliases: ['w'] } }]);
  assert.deepEqual(core.exitsOf(doc, 'b')[0].out, { key: 'west', aliases: ['w'] });
  doc.exits[0].return = null;
  assert.equal(core.exitsOf(doc, 'b')[0].out, null); // one-way into b: no way out of b here
});

test('entities: place, move, edit, remove', () => {
  const doc = sector();
  core.addEntity(doc, { id: 'hint', kind: 'quest_prop', room: 'b', content: 'objects/hint.md',
    aliases: ['note'], params: { visibility: 'commitment_hint_visible', commitment_type: '' } });
  assert.deepEqual(doc.entities.hint, { kind: 'quest_prop', room: 'b', content: 'objects/hint.md',
    aliases: ['note'], params: { visibility: 'commitment_hint_visible' } });
  core.setEntity(doc, 'hint', { room: 'a', aliases: [], params: {} });
  assert.deepEqual(doc.entities.hint, { kind: 'quest_prop', room: 'a', content: 'objects/hint.md' });
  assert.throws(() => core.setEntity(doc, 'hint', { room: 'nowhere' }), /room/);
  core.removeEntity(doc, 'hint');
  assert.equal('hint' in doc.entities, false);
});

test('undo and redo walk snapshots; a new edit clears redo', () => {
  const history = new core.History();
  let doc = sector();
  history.record(doc);
  doc = core.setRoom(core.clone(doc), 'a', { title: 'Renamed' });
  const undone = history.undo(doc);
  assert.equal(undone.rooms.a.title, 'A');
  const redone = history.redo(undone);
  assert.equal(redone.rooms.a.title, 'Renamed');
  history.record(redone);
  assert.equal(history.canRedo, false);
  assert.equal(history.canUndo, true);
});
