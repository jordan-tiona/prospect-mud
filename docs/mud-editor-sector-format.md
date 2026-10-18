# MUD Editor: sector format and export manifest

**Status:** Format agreed with the project owner (2026-10-16), Tools lane. Implemented: `ops/editor/check.py` and `ops/editor/export.py`; `sectors/elsewhere/sector.json` (imported once from the old build scripts, now owned by the editor); the Elsewhere manifest `prospect/world/data/sectors/elsewhere.json`; and `world/build_sector.py`, which every `world/build_*.py` now wraps (Steps A-C of `docs/build-sector-proposal.md`). Editor UI (`python ops/editor/serve.py`, http://127.0.0.1:8765): 5a (viewer), 5b (structure editing, Save with saved-version history and autosaves, Export) and 5c (candidate tray, Section 8.1) are built. Saving writes only `sectors/<id>/sector.json`, plus its gitignored `.history/` (previous versions, last 20) and `.autosave/` (`latest.json` a few seconds after each change, plus a copy every 5 minutes, last 5). Dismissing a tray candidate writes `sectors/_dismissed.json`. See `ops/editor/store.py`.

**Background:** bible §18, "Planned content-authoring tool". This spec is the data model for that tool. It does not approve any lore and doesn't change how prose is authored.

## 1. Three kinds of data, three owners

| Kind | Examples | Lives in | Edited by |
|---|---|---|---|
| **Prose** | Room glance/description, NPC personas, ambient poses, object descriptions, NPC/object display names | `content/**/*.md` (the format it has today) | Lore lane / project owner, as Markdown. **The editor only reads it, never writes it.** |
| **Structure** | Which rooms make up a sector, room titles, exits, where entities are placed, editor map layout | `sectors/<sector_id>/sector.json` (new) | Project owner, in the editor |
| **Mechanics** | Typeclasses, lock funcs, commitment scenarios, skitter spawning, NPC actions | Game code | Dev lane. Sector files can only *name* mechanics from an allowlist (Section 5). They can't define them. |

Engine-authored runtime state, such as per-player quest state, skitter kills and NPC memory, isn't part of either format.

## 2. Terms

- **Sector:** a self-contained map that can be crossed entirely by walking its exits, with no teleport. All of Elsewhere is one sector. Each future habitat, or an area of Prospect's surface, would be its own sector. The sector ID is organisational. Any in-world name or description of the place is still Lore's.
- **Room:** a location in a sector. Its **title** belongs to the sector file (owner's call in the editor). Its glance and description come from `content/rooms/<room_id>.md`.
- **Exit:** a directed connection between two rooms in the same sector, normally recorded as a pair with its return exit.
- **Entity:** anything placed in a room: talk-capable NPCs, ambient NPCs, objects. Each one has a **kind** from the allowlist.
- **Inter-sector travel** (lifts to the docks, ferries, surface access) is **out of scope**. Section 9 reserves a place for it.

## 3. Files

```
sectors/<sector_id>/sector.json            # editor source of truth for structure (committed)
prospect/world/data/sectors/<sector_id>.json  # export manifest, generated, committed, never hand-edited
prospect/world/entity_kinds.py              # Dev-owned allowlist of entity kinds (Section 5)
```

One file per sector for now. Elsewhere today is 9 rooms and about 17 entities, and one JSON file stays comfortable well into the hundreds. If merge conflicts start to matter, it can split per room later without changing the manifest.

Both files are JSON: UTF-8, 2-space indent, keys sorted where order doesn't matter, and a trailing newline. That way the editor's rewrites produce minimal git diffs. JSON has no comments, so notes go in `notes` fields.

## 4. `sector.json` schema (format_version 1)

The example uses current real data only.

```json
{
  "format_version": 1,
  "sector_id": "elsewhere",
  "notes": "",
  "rooms": {
    "old_quarter_square": {
      "title": "Old Quarter Square",
      "content": "rooms/old_quarter_square.md",
      "editor": {"x": 0, "y": 0},
      "notes": ""
    },
    "corner_cafe": {
      "title": "Corner Café",
      "content": "rooms/corner_cafe.md",
      "editor": {"x": 0, "y": -200}
    }
  },
  "exits": [
    {
      "from": "old_quarter_square", "to": "corner_cafe",
      "key": "north", "aliases": ["n"],
      "return": {"key": "south", "aliases": ["s"]}
    }
  ],
  "entities": {
    "mara_voss": {
      "kind": "talk_npc",
      "room": "corner_cafe",
      "content": "npcs/mara_voss.md"
    },
    "square_noticeboard": {
      "kind": "ambient_object",
      "room": "old_quarter_square",
      "content": "ambient/objects/square_noticeboard.md"
    },
    "misdelivered_parcel_hint": {
      "kind": "quest_prop",
      "room": "corner_cafe",
      "content": "objects/misdelivered_parcel_hint.md",
      "params": {"visibility": "commitment_hint_visible", "commitment_type": "deliver_parcel"}
    }
  }
}
```

Rules:

- **IDs** (`[a-z0-9_]+`) are unique per sector across rooms and entities. They double as the Evennia tag that matches an existing database object, so **an ID never changes once built**. Renaming happens in prose or the title, not the ID. **Titles and display names don't need to be unique.** Data that refers to a room or entity (exits, placement, tags, the manifest) uses the ID (owner decision, 2026-10-16). Players and NPCs still talk about places by name: `give_directions` matches names, and resolving duplicate names is a Dev-lane design (`docs/build-sector-proposal.md` Section 5).
- **`content`** is a path relative to `content/`. It's optional while prose doesn't exist yet. The editor shows such an entity as "awaiting prose" and export reports it.
- **Exits:** every exit is one record. `"return": null` marks an intentional one-way exit, and a missing `return` is a validation error. That rules out the accidental one-way drift that hand-kept `SPOKES`/`CHAINS` lists allow. The hub-and-spoke assumption in `build_rooms.py` goes away, and every connection is explicit.
- **One connection per pair of rooms (owner decision, 2026-10-16).** At most one exit record may join two given rooms, in either direction. A record already covers both ways through `return`, and extra command words ("door" alongside "north") are `aliases`. Two one-way records pointing at each other count as a second connection: write one record with a `return` instead. `check` reports a violation as `duplicate_room_pair`, an error, so export refuses it. If exits ever get their own mechanics (locks, conditions) and two genuinely different routes between the same rooms are wanted, put a small room on the second route, or revisit this rule deliberately.
- **`editor`** holds map layout and other editor-only data (a room's `former_titles`, Section 8). Export strips it.
- **`params`** may only contain keys that the entity's kind declares (Section 5).
- **`aliases`** (optional) are extra words players can use to refer to an entity, e.g. the gardening kit's `["kit", "gardening kits"]`. Like exit aliases, they're structure, not prose.
- **Display names** of NPCs and objects aren't stored here. They come from the content file's `# Heading`, as `build_ambient.py` already does. Talk NPCs' first-name alias is derived the same way `build_npcs.py` does it today.

## 5. Entity kinds (Dev-owned allowlist)

`prospect/world/entity_kinds.py` defines each kind as plain data:
- typeclass
- tag category (so existing database objects keep matching)
- which content sections it needs
- which `params` it accepts and their allowed values

The editor and the exporter read it without importing the game (`world_model.literals()` parses the literal assignments). A new kind, or a new allowed value such as a new lock func, is a Dev-lane change. The editor can only choose from what exists.

Kinds needed to cover today's world:

| Kind | Typeclass | Tag category (existing) | Prose from | Today built by |
|---|---|---|---|---|
| `room` (implicit) | `typeclasses.rooms.Room` | `phase1_neighborhood` | `## Glance`, `## Description` | `build_rooms.py` + `build_ambient.py` |
| `talk_npc` | `typeclasses.npcs.TalkativeNPC` | `phase1_npcs` | persona heading + `desc` metadata | `build_npcs.py` |
| `ambient_npc` | `typeclasses.npcs.NPC` | `phase1_ambient` | heading, `## Poses`, `## Description` | `build_ambient.py` |
| `ambient_object` | `typeclasses.objects.RoomObject` | `phase1_ambient` | heading, `## Short Description`, `## Description` | `build_ambient.py` |
| `quest_prop` | `typeclasses.objects.CommitmentHintObject` | `quest_prop` | *currently in code* | `build_quest_props.py` |
| `revision_display` | `typeclasses.objects.RevisionDisplayObject` | `noticeboard_prop` | *currently in code* | `build_noticeboard.py` |
| `signpost` | `typeclasses.objects.SignpostObject` | `signpost_prop` | *currently in code* | `build_signpost.py` |
| `skitter_ledger` | `typeclasses.objects.SkitterLedgerObject` | `skitter_ledger_prop` | *currently in code* | `build_skitter_ledger.py` |
| `gardening_kit` | `typeclasses.objects.GardeningKit` | `garden_prop` | *currently in code* | `build_garden_props.py` |
| `planting_bed` | `typeclasses.objects.PlantingBed` | `garden_prop` | *currently in code* | `build_garden_props.py` |

**Prose that's currently in code** (quest-prop, garden-prop, noticeboard and signpost text) has to move into `content/` before those entities can be exported, because export requires Approved content for every entity (Section 6). The sector file itself never carries prose. **Ownership (decided 2026-10-16):**
- **Dev** owns the object's mechanics and states what text it needs, via a `docs/lore-requests.md` entry.
- **Lore** owns the words players read.
- **Tools** places the object and links its content.

For the text already in code, Tools moves it **verbatim** into content files marked `approval: Draft`, with no rewording, and files one lore request for Lore review and owner approval. From then on, new objects don't carry player-facing text in Python.

Text the engine **generates at runtime** stays in Dev-owned code: the signpost's computed route, and the café display's per-player revision. Only static descriptions and room lines move.

**Signpost `SPOKE_LINES`** duplicate what the exits already say. Deriving them from exits and room titles would be a behaviour change, so it goes to the Dev lane and isn't part of this work.

**Skitters** aren't placed entities. The eligible spawn rooms (`world/skitters.py`'s `ELIGIBLE_ROOM_TAGS`) are mechanics. The editor may later *show* them as read-only overlay data.

## 6. Export manifest

`prospect/world/data/sectors/<sector_id>.json` is what the engine builds from. It's generated by the editor's export (also runnable from the command line), committed to git, and never hand-edited. It's flat and fully resolved:

- `format_version`, `sector_id`, and `sources`: a SHA-256 of `sector.json` and of every content file used. There's no timestamp, so an export with no changes produces an identical file. The sector file is hashed without its editor-only fields, so moving a map box doesn't make the manifest stale. Text is hashed with LF line endings, so Windows checkouts produce the same hashes.
- `rooms`: id, title, typeclass, tag category, desc, glance.
- `exits`: expanded into one-way records `{id, from, to, key, aliases}`. The ID is `<from>__<key>`, which is unique because a room can't have two exits with the same key.
- `entities`: id, kind, typeclass, tag category, room, key, aliases, and `attributes` (the `db.*` values to set: `desc`, `room_line`, `spoke_lines`, `npc_id`, as each kind needs; every non-NPC object also gets `in_glance`, from its content file's `glance: show | hide` metadata line or else its kind's `glance` default, LR-LORE-0005; NPCs with a `## Emotes` section get `emotes`, LR-LORE-0006), plus `poses` for ambient NPCs and resolved `locks` for kinds with a lock template.

Prose is parsed with the game's own content parsers (`world/room_content.py`, `world/ambient_content.py`, `world/npc_profile.py`). They're plain Python that doesn't need Evennia, so the manifest's text matches exactly what the game would read. If those parsers are stricter than `check`, export reports the failure as a `parse_error` and refuses.

**Prose is copied into the manifest** (approved text only, HTML comments stripped). The manifest's git diff is then exactly "what changes in the live world", and building doesn't read `content/` at all. Talk NPC personas are the exception: the prompt builder keeps reading `content/npcs/*.md` at runtime as it does today. The manifest only places the NPC and carries its `desc`.

The trade-off is that a Lore edit to a room description reaches the game only after a re-export. That's deliberate: **export is the publish step.** `check` reports a manifest as stale when its `sources` hashes no longer match. Tests don't fail on staleness, so Lore-lane commits never break the test suite.

### Export validation

Export runs the same checks as the read-only `check` command and **refuses to write** on errors:

- **Errors:**
  - unknown kind or param
  - a `room`/`from`/`to` that points at a missing room
  - an exit with no `return` key
  - duplicate IDs
  - two exits from one room with the same key or alias
  - a content file that's referenced but missing, or whose header ID doesn't match
  - a content file with no metadata
- **Approval gate (error):** every room and entity in the sector must point at a content file whose header is `approval: Approved`. A missing `content` reference, a missing file or a non-Approved file blocks the export. So does any other metadata line whose value starts with `Draft`, such as `probe_description: Draft (LR-DEV-0001, ...)`: an approved file can still carry a section or field awaiting approval (`draft_field`). A placeholder reaching the game always means content that was never requested from Lore, so it should never ship silently (owner decision, 2026-10-16). The editor's "awaiting prose" list shows what to request.
- **Warnings:**
  - `TODO(lore)` text that would reach players
  - content files no sector uses
  - rooms with no exits

## 7. Building from the manifest (needs Dev-lane review)

The hand-written lists in `build_rooms.py`, `build_npcs.py`, `build_ambient.py`, `build_quest_props.py`, `build_noticeboard.py`, `build_signpost.py` and `build_garden_props.py` get replaced by one `world.build_sector.build("<sector_id>")`:

- It creates or updates by tag, as today, keeping the existing tag categories so nothing already built is duplicated.
- It's idempotent, and it prints what it created, updated or left unchanged.
- It handles removals (per `docs/engineering-pitfalls.md`, reset tools that only know current config):
  - Any object carrying one of this sector's tag categories that's missing from the manifest gets reported as an **orphan**.
  - Orphans are only deleted with an explicit `prune=True`.
  - Exits are matched by their manifest ID tag, not by destination alone, so changing an exit's direction doesn't leave the old one behind.
- It's run with the server stopped, as all database-writing scripts are today.
- `build_skitters.py` stays as it is. It's mechanics.

**Migration guarantee (done):** the first `elsewhere` manifest came from a one-off importer (since retired) that reads today's build-script lists and content files. `prospect/world/test_sector_manifest.py` runs the old scripts in Evennia's test database and asserts that the manifest describes exactly what they build: rooms, exits, entities, attributes, locks and tags, with nothing extra on either side. That test passes as of milestone 3. Once `build_sector()` exists, it also builds from the manifest and compares the two. The old scripts are removed only after that passes.

## 8. Lore lane interaction

- Lore keeps writing `content/` Markdown exactly as now and never edits sector files or manifests.
- A new content file that no sector references shows up in the editor as **unplaced**. The owner places it.
- The editor's map is the read-only view of layout and exits for Lore too: open it and don't Save. It replaced the Obsidian vault (`ops/generate_obsidian.py` and the generated `maps/`), retired 2026-10-16.

### 8.1 Batch requests: request, pick, place (owner workflow, agreed 2026-10-16)

The owner builds out an area by asking Lore for a batch of candidates, then choosing and wiring up the ones they want in the editor:

1. **Request.** The owner files a batch lore request (`docs/lore-requests.md`, batch variant): what kind of content, how many, the area, and any constraints. Example: "10 rooms in an area".
2. **Candidates.** Lore delivers ordinary content files in the usual folders (`content/rooms/`, `content/ambient/npcs/`, ...), each `approval: Draft`, with a `request: LR-...` line in the metadata header. Lore chooses the file names, which become the IDs (`[a-z0-9_]+`, never changed once built). A room's `# Heading`, if present, is only the editor's *suggested* title; the owner sets the real one.
3. **Room descriptions don't mention directions.** No "a doorway to the north": the game lists exits itself, and the owner decides the layout after the prose is written. Batch requests say so by default. If a particular room's prose does need to fit its final layout, the owner sends a follow-up request after placing it.
4. **Pick.** The editor's tray shows unplaced content grouped by `request:`. Placing a candidate adds it to `sector.json` as a room or entity. **Draft content can be placed**, so an area can be laid out and checked before anything is approved. Only export requires approval (Section 6).
5. **Dismiss.** Rejected candidates can be dismissed from the tray. The editor never writes content files, so dismissals go in an editor-owned list (`sectors/_dismissed.json`, content paths). Deleting a rejected file is a separate git action for the owner, whenever they choose.
6. **Connect, approve, export.** The owner wires exits in the editor, approval is set in each content file's header (not by the editor), then the owner exports.

**In the editor (milestone 5c, built):** the **Tray** button lists every content file in a kind's folder that no sector uses, grouped by `request:` (requests first, then stray files with no request), with each file's approval and first lines.
- *Place* puts a room candidate near the middle of the map, titled with its heading until the owner changes it. An entity candidate opens a form to choose its room (the room last looked at, by default) and its kind (from the allowlist kinds that read that folder). The ID is the file's header ID (`room_id`, `npc_id`, ...), or its file name if the header has none, and `check` then reports the mismatch. Placing is an ordinary edit: undoable, and written on Save. Removing a placed room or entity puts its file straight back in the tray.
- *Dismiss* (or *Dismiss all* for a request) writes `sectors/_dismissed.json` at once, with no Save needed. It's a sorted list of content paths, committed with the sector files. Dismissed files sit in a folded *Dismissed* list with *Restore*. If a dismissed file is later deleted, its entry shows there as "file deleted" with *Clear*, and `check` notes it as `stale_dismissal` (info).
- `check`'s `unused_content` warning now covers only stray files. A file with a `request:` line, or one on the dismiss list, isn't warned about.
- If the owner changes a room title, `check` warns (`old_title`) about content files whose player-visible text still mentions the old title. It doesn't touch them. The editor keeps a renamed room's old titles in `editor.former_titles` (editor-only, so export ignores it), so the warning lasts until the prose is updated or the owner clicks *Forget* next to the old title. A mention inside a current title that contains the old one ("Square" in "Old Quarter Square") doesn't count, and neither does an old title that another room has now.

## 9. Reserved / out of scope for format_version 1

- Inter-sector links (a future `"portals"` list naming a room in another sector, with travel mechanics owned by Dev).
- **Wandering entities.** Every entity is built in exactly one `room`. Content files' `room:` metadata no longer drives placement, so Iri's "may also appear in the Residential Courtyard" note has no effect and is due to be removed from her persona by the Lore lane. A future kind could add a list of rooms for an entity to move between, owned by Dev.
- Sub-areas within a sector (e.g. grouping the Old Quarter's rooms) as editor-only labels. They're easy to add under `editor` later if wanted.
- Engine runtime state, NPC actions, commitment scenarios.

## 10. Open questions for the project owner

1. ~~Unapproved prose at export.~~ **Decided 2026-10-16: export blocks.** See Section 6.
2. ~~Moving in-code prose.~~ **Decided 2026-10-16:** Tools moves it verbatim as Draft, and Lore reviews it. See Section 5.
3. ~~Iri's dual-room note.~~ **Decided 2026-10-16: one room per entity.** Wandering entities are a future want (Section 9).
4. ~~Directory names.~~ **Decided 2026-10-16:** `sectors/` sits at the top level of the `prospect-mud` repo, next to `content/`, and the manifest goes in `prospect/world/data/sectors/` (engine input).
