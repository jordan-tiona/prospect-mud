# Proposal: `world.build_sector`, building the world from sector manifests

**Status:** Proposal, Tools lane (2026-10-16), **for Dev-lane review**. No game code has changed yet. This is milestone 4 of the MUD Editor (`docs/mud-editor-sector-format.md` Section 7).

**Why Dev review:** it replaces how the world gets built, touches modules that game code imports (`world/build_rooms.py`, `world/actions.py`), and includes one small behaviour change (Section 5). The Tools lane may write `world/build_*.py`, but must not change game behaviour without a Dev-lane review.

## 1. Summary

A new `world/build_sector.py` reads `prospect/world/data/sectors/<id>.json` (written by `ops/editor/export.py`) and creates or updates every room, exit and placed entity in it. Over three steps it replaces the hand-written lists in nine build scripts:
- `build_rooms`, `build_npcs` and `build_ambient`
- `build_quest_props`, `build_noticeboard`, `build_signpost`, `build_garden_props` and `build_skitter_ledger`

`build_skitters` stays as it is, since skitter spawning is mechanics.

Today's guarantees are kept: the build is idempotent, it matches existing objects by tag, and it's run with the server stopped. It adds:
- a **dry run** that reports what would change without touching the database
- **orphan reporting** (Section 3.5)
- one generic code path in place of nine near-duplicate ones

## 2. What depends on the old scripts today

| Dependency | Where | Plan |
|---|---|---|
| Room tag category constant `BUILD_TAG_CATEGORY` | `actions.py`, `chargen.py`, `tutorial.py`, `skitters.py`, `typeclasses/objects.py`, every builder | Keep the constant and its value (`phase1_neighborhood`). It stays importable from `world.build_rooms`. |
| Other tag category constants (`NPC_TAG_CATEGORY`, `QUEST_PROP_TAG_CATEGORY`, ...) | builders, tests | Keep, same values (they're also in `entity_kinds.py`). |
| `build_rooms.ROOMS` (room tag → display name) | `actions.py` `_find_neighborhood_room` (NPC `give_directions`) | Read room titles from the manifest instead. **Behaviour change, see Section 5.** |
| `build_rooms.build()` / `build_npcs.build()` called to set up a world | about 25 test modules, `world/npc_eval.py` | Keep both as thin wrappers over `build_sector` (Section 4, step C), so no test has to change during the switch. |
| Other builders' `build()` | their own `test_build_*.py` | Same: thin wrappers, filtered to their kinds. |

## 3. `build_sector` design

```python
build(sector_id, *, kinds=None, dry_run=False, prune=False) -> BuildReport
```

- **`kinds`:** limits the build to some entity kinds. Rooms and exits are always included, because entities need rooms. This is what lets the old `build_npcs.build()` become `build("elsewhere", kinds={"talk_npc"})`.
- **`dry_run`:** plans everything and writes nothing. The plan and apply steps are separate functions, so the dry run is the same code path as a real build, not a copy of it.
- **`BuildReport`:** lists objects created, updated (with which fields changed), unchanged and orphaned, and prints a summary, like today's "ready" lines.

### 3.1 Rooms

These are matched by tag (`<room_id>`, `phase1_neighborhood`), as today. If no match is found, a room is created with the manifest's typeclass. On every run the build sets `key` (title), `db.desc` and `db.glance`. If an existing room's typeclass differs, it's swapped with `clean_attributes=False`, the pattern `build_quest_props` and `build_noticeboard` already use.

### 3.2 Exits

Each exit gets a new tag (`<from>__<key>`, category `sector_exit`). Today's exits have no tags at all. Matching works like this:

1. Find an exit by its tag.
2. Otherwise, **adopt** an untagged exit in the source room with the same destination (today's `_get_or_create_exit` rule), and tag it.
3. Otherwise, create a new exit.

Then the build sets `key`, `destination` and aliases. Matching by tag means changing an exit's direction in the editor updates the existing exit, instead of creating a new one next to the old.

### 3.3 Entities

These are matched by tag (`<entity_id>`, the kind's existing tag category). The build:
- creates the object in its room if it's missing
- swaps the typeclass if it differs
- moves the object to its room if it's elsewhere (`move_to(quiet=True)`)
- sets `key`, the attributes listed in the manifest, poses and locks

| Manifest field | Applied as |
|---|---|
| `attributes` | `obj.attributes.add(name, value)` for each entry |
| `poses` | `obj.set_ambient_poses(poses)`, only when they've changed, so the pose ticker isn't re-registered on every run |
| `locks` | `obj.locks.add(locks)` |
| `aliases` | see 3.4 |

Talk NPCs get `db.npc_id` from `attributes`, and so are still found by the prompt builder exactly as today.

### 3.4 Removing things the manifest no longer sets

Today's builders only ever *add*: a removed alias or a deleted description stays on the object forever. The new build records what it set on each object in `db.sector_managed`, a dict of `{"attributes": [...], "aliases": [...]}`. On the next run it removes only managed values that the manifest no longer lists. Anything set some other way (by hand, or by a game mechanic) is never touched.

### 3.5 Orphans (`docs/engineering-pitfalls.md` #3 and #4)

Every object the build creates or adopts also gets a sector tag (`elsewhere`, category `sector`). An **orphan** is either:

- an object with this sector's tag whose ID isn't in the manifest, or
- an object in one of `entity_kinds.py`'s tag categories, or an exit in one of this sector's rooms, that isn't in the manifest.

The second rule catches old objects built before sector tags existed. Pitfall #3 is the reason for it: a cleanup tool has to find what's actually in the database, not only what the current config knows about.

Orphans are **reported** on every run. They're deleted only with `prune=True`, and even then:
- a room that still contains a puppeted character or any player-owned object isn't deleted. It's reported as blocked instead;
- player characters, accounts and anything carried by a character are never touched;
- skitters (`skitter_entity` category) are outside sector ownership and are ignored.

### 3.6 Running it

```
evennia stop
evennia shell -c "from world.build_sector import build; build('elsewhere', dry_run=True)"
evennia shell -c "from world.build_sector import build; build('elsewhere')"
evennia start
```

As with every database-writing script, it's run only with the server stopped. If `server/server.pid` exists, the build prints a warning and refuses to run unless `force_live=True` is passed. It also refuses a manifest whose `format_version` it doesn't know.

## 4. Rollout in three steps

**Step A: add `build_sector` next to the old scripts (Tools, after this review).** Nothing in the game calls it yet. Tests, using Evennia's test database:
- build from a small fixture manifest, then check idempotency (a second run changes nothing)
- typeclass swap, exit adoption and re-keying, managed-attribute removal, and orphan reporting and pruning, including a room with a player in it
- `dry_run` writes nothing
- **old vs new:** build Elsewhere with the old scripts, snapshot it, then run `build_sector` over that same database. It must report zero creates and zero orphans, and only the expected updates: adding sector tags and managed-field records. Separately, building from an empty database must produce the same snapshot as the old scripts. That extends the existing `test_sector_manifest.py`.

**Step B: export Elsewhere (owner).** This needs LR-TOOLS-0001 and LR-TOOLS-0002 resolved, so that export stops refusing. The first real `prospect/world/data/sectors/elsewhere.json` gets committed.

**Step C: switch over (Dev-reviewed change, after B).**
- Each old builder's `build()` becomes a thin wrapper: `build_sector.build("elsewhere", kinds={...})`. Its hard-coded lists (`ROOMS`, `SPOKES`, `CHAINS`, `NPCS`, `AMBIENT_*_IDS`, `ROOM_IDS`, `QUEST_PROPS`, and the in-code prose and room lines) are deleted. Constants and return shapes stay, e.g. `build_npcs.build()` still returns `{npc_id: npc}`.
- `actions._find_neighborhood_room` reads titles from the manifest (Section 5).
- Ambient content parsers stop requiring a `room:` metadata field, since placement comes from the sector now.
- Live run: dry run first, then the real build. Then the existing equivalence test is retired in favour of Step A's old-vs-new test.

The wrappers can be removed later, test module by test module (a Tests-lane task). That isn't needed for the switch.

## 5. The one behaviour change: `give_directions` reads rooms from the manifest

**Rule (owner, 2026-10-16): rooms are identified by ID everywhere in the data. Titles are display text and may repeat**, which isn't unusual in MUDs. **`give_directions` deliberately stays name-based**, because players ask for places by name. The model passes the destination's name as free text, and the engine matches it against room titles.

What changes:
- `_find_neighborhood_room` reads the room list (ID and title) from the manifest instead of `build_rooms.ROOMS`. With today's nine rooms, players see no difference.
- Duplicate titles mean a name can match more than one room. **The owner will work out with Dev how to resolve multiple matches, picking the closest one as the room the player meant.** That design belongs to Dev. `build_sector` only has to supply the room list with both IDs and titles, so whatever rule Dev settles on can return a specific room ID.
- **Open question:** may an NPC direct players to every room in the sector, or should there be a per-NPC or per-room limit? Today it's all nine rooms. I'd ship "all rooms in the sector" first.

## 6. Out of scope

- Skitter population and spawn rooms, commitment scenarios, player state, NPC actions.
- Multiple sectors or travel between them: the format reserves a slot for it, nothing more.
- Wandering entities.

## 7. Dev-lane review checklist

1. Managed-attribute removal (3.4): acceptable, or should the build stay add-only like today?
2. Exit adoption rule (3.2): is same source plus same destination safe? Today no room pair has two exits between them.
3. Prune safety rules (3.5): anything else that must never be deleted?
4. Wrappers vs. moving tests to `build_sector` directly in Step C.
5. `give_directions` room list from the manifest, plus the multiple-match rule for duplicate titles (Section 5; owner and Dev).
6. Ambient parser relaxation in Step C: any other code relying on ambient files' `room:` field? (`ops/generate_obsidian.py` does until Obsidian is retired.)
7. Review `prospect/world/entity_kinds.py`, which the Tools lane drafted, and take ownership of it.

## 8. Dev-lane review (2026-10-16)

**Verdict:** approved for Step A, with the changes below. One question (item 5) still needs the owner.

1. **Removing managed attributes: approved.** The only game code that writes `desc` or `room_line` at runtime is for parcels, weapons and skitters (`world/actions.py`, `world/skitters.py`), and none of those belong to a sector. Runtime code never changes aliases. Per-player state for the garden, ledger and noticeboard is stored on the player, not on the object. One condition: an object without `db.sector_managed` (anything built by the old scripts) has its values **recorded on that first run, not removed**.
2. **Exit adoption: approved, with a guard.** If two or more untagged exits share the same source and destination, adopt none of them. Report it as a conflict and create nothing for that exit.
3. **Pruning: add these rules.**
   - **Rooms the engine needs.** Game code finds some rooms by tag:
     - `medical_bay`: chargen spawn, `world/chargen.py`
     - `daven_office`: `typeclasses/objects.py`
     - the skitter spawn rooms: `world/skitters.py`
     - the tutorial rooms: `world/tutorial.py`

     Add a Dev-owned `REQUIRED_ROOM_IDS` list to `entity_kinds.py`. `check.py` reports an error when a sector is missing one of them, so export refuses. Without this, deleting a room in the editor would break chargen without any error, and pruning would then delete the live room.
   - **A room is blocked unless it's empty.** Only delete a room if it holds nothing apart from other orphans being pruned in the same run. Checking only for player-owned objects isn't enough: when Evennia deletes a room, it moves the contents to their `home` or deletes them, and that includes skitters, dropped items and parcels.
   - **A room someone uses as `home` is blocked** (`ObjectDB.objects.filter(db_home=room)`).
4. **Wrappers: agreed.** That includes `build_ambient.apply_all_room_content()` and `build_ambient_entities()`, which tests call directly. Keep the existing return shapes.
5. **Source for `give_directions`.** Dev recommends using all rooms in the NPC's sector, as proposed:
   - The engine still checks every route against the real exits.
   - The persona prompt already limits which places an NPC offers to explain.

   **Owner to confirm** that any exported room automatically becoming a valid destination is the intended rule. Two cleanups for Step C:
   - `_find_neighborhood_room`'s docstring still says "six known rooms".
   - `_find_exit_path`'s `max_depth=4` will need raising once a sector is wider than four hops.
6. **Relaxing the ambient parser: fine.** The only readers of `room:` are `world/build_ambient.py` and `ops/generate_obsidian.py`. Retire the second one in the same step, or teach it to read placements from the sector file.
7. **`entity_kinds.py`: Dev takes ownership.**
   - The tag categories are checked by `test_sector_manifest`.
   - The `quest_prop` lock template matches `build_quest_props`' `lock_string`.
   - `REQUIRED_ROOM_IDS` (item 3) goes here.

**Not on the checklist.** Section 3.3 says to move an entity back to its room when it's somewhere else. That conflicts with Section 3.5's rule that nothing a character carries is ever touched. `GardeningKit` can be picked up, and today `build_garden_props.py` already takes it out of a player's inventory on a rebuild. For consistency: **don't move an entity a character is carrying.** Report it as "held by <character>" instead.
