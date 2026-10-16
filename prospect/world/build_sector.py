"""
Builds a sector's rooms, exits and placed entities from its exported
manifest (prospect/world/data/sectors/<sector_id>.json, written by
ops/editor/export.py). Design and Dev-lane review:
docs/build-sector-proposal.md.

Step A of that proposal: this module sits alongside the old
world/build_*.py scripts, and nothing in the game calls it yet.

Idempotent: objects are matched by tag, so re-running updates in place.
Planning and applying are separate: build() first plans every change
against the current database, then applies the plan (unless dry_run),
so a dry run reports exactly what a real run would do.

Run with the server stopped (from the checkout the live game runs in):
    evennia shell -c "from world.build_sector import build; build('elsewhere', dry_run=True)"
    evennia shell -c "from world.build_sector import build; build('elsewhere')"
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from evennia import create_object, search_tag
from evennia.objects.models import ObjectDB

from world.entity_kinds import EXIT_TYPECLASS, KINDS, REQUIRED_ROOM_IDS, ROOM_KIND

FORMAT_VERSION = 1
MANIFEST_DIR = Path(__file__).resolve().parent / "data" / "sectors"
SERVER_PID = Path(__file__).resolve().parents[1] / "server" / "server.pid"

SECTOR_TAG_CATEGORY = "sector"
EXIT_TAG_CATEGORY = "sector_exit"
MANAGED_ATTRIBUTE = "sector_managed"
CHARACTER_TYPECLASS = "evennia.objects.objects.DefaultCharacter"
ROOM_BASE_TYPECLASS = "evennia.objects.objects.DefaultRoom"


class SectorBuildError(Exception):
    """The manifest can't be built (bad format, live server, missing file)."""


@dataclass
class Desired:
    """What one room, exit or entity should look like after the build."""

    label: str  # "room corner_cafe", for the report
    object_id: str
    tag_category: str
    typeclass: str
    key: str
    sector_id: str
    aliases: list = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    poses: list | None = None
    locks: str | None = None
    location: str | None = None  # room id
    destination: str | None = None  # room id (exits)


@dataclass
class BuildReport:
    sector_id: str
    dry_run: bool
    created: list = field(default_factory=list)
    updated: dict = field(default_factory=dict)  # label -> [changed fields]
    unchanged: list = field(default_factory=list)
    held: list = field(default_factory=list)  # entities a character carries; not moved
    conflicts: list = field(default_factory=list)
    orphans: list = field(default_factory=list)
    pruned: list = field(default_factory=list)
    blocked: list = field(default_factory=list)  # (label, reason) not pruned
    objects: dict = field(default_factory=dict)  # object id -> object (existing ones only in a dry run)

    def summary(self):
        mode = "DRY RUN - nothing written" if self.dry_run else "applied"
        lines = [f"Sector '{self.sector_id}' ({mode}):"]
        lines += [f"  created   {label}" for label in self.created]
        lines += [f"  updated   {label}: {', '.join(fields)}" for label, fields in self.updated.items()]
        lines += [f"  held      {text}" for text in self.held]
        lines += [f"  CONFLICT  {text}" for text in self.conflicts]
        lines += [f"  orphan    {label}" for label in self.orphans]
        lines += [f"  pruned    {label}" for label in self.pruned]
        lines += [f"  blocked   {label}: {reason}" for label, reason in self.blocked]
        lines.append(
            f"  {len(self.created)} created, {len(self.updated)} updated, {len(self.unchanged)} unchanged, "
            f"{len(self.orphans)} orphan(s), {len(self.conflicts)} conflict(s)."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------- manifest


def load_manifest(sector_id):
    path = MANIFEST_DIR / f"{sector_id}.json"
    if not path.is_file():
        raise SectorBuildError(f"No manifest at {path}. Export the sector first (ops/editor/export.py).")
    return json.loads(path.read_text(encoding="utf-8"))


def _desired_from_manifest(manifest, kinds):
    sector_id = manifest["sector_id"]
    rooms = [
        Desired(
            label=f"room {room_id}",
            object_id=room_id,
            tag_category=room["tag_category"],
            typeclass=room["typeclass"],
            key=room["title"],
            sector_id=sector_id,
            attributes={"desc": room["desc"], "glance": room["glance"]},
        )
        for room_id, room in manifest["rooms"].items()
    ]
    exits = [
        Desired(
            label=f"exit {ex['id']}",
            object_id=ex["id"],
            tag_category=EXIT_TAG_CATEGORY,
            typeclass=EXIT_TYPECLASS,
            key=ex["key"],
            sector_id=sector_id,
            aliases=list(ex["aliases"]),
            location=ex["from"],
            destination=ex["to"],
        )
        for ex in manifest["exits"]
    ]
    entities = [
        Desired(
            label=f"{entity['kind']} {entity_id}",
            object_id=entity_id,
            tag_category=entity["tag_category"],
            typeclass=entity["typeclass"],
            key=entity["key"],
            sector_id=sector_id,
            aliases=list(entity.get("aliases", [])),
            attributes=dict(entity.get("attributes", {})),
            poses=entity.get("poses"),
            locks=entity.get("locks"),
            location=entity["room"],
        )
        for entity_id, entity in manifest["entities"].items()
        if kinds is None or entity["kind"] in kinds
    ]
    return rooms, exits, entities


# ------------------------------------------------------------- comparison


def _tagged(object_id, category):
    return list(search_tag(key=object_id, category=category))


def _held(obj):
    """True if something other than a room holds obj (a character's inventory)."""
    return obj.location is not None and obj.location.location is not None


def _managed(obj):
    return obj.attributes.get(MANAGED_ATTRIBUTE)


def _desired_managed(desired):
    return {"attributes": sorted(desired.attributes), "aliases": sorted(a.lower() for a in desired.aliases)}


def _changes(obj, desired, room_objects):
    """Field names that differ between obj and desired. `room_objects` maps
    room id -> existing room object (or None if it's created in this run)."""
    changes = []
    if obj.typeclass_path != desired.typeclass:
        changes.append("typeclass")
    if obj.key != desired.key:
        changes.append("key")

    managed = _managed(obj)
    current_aliases = set(obj.aliases.all())
    wanted_aliases = {a.lower() for a in desired.aliases}
    stale_aliases = set(managed["aliases"]) - wanted_aliases if managed else set()
    if wanted_aliases - current_aliases or stale_aliases & current_aliases:
        changes.append("aliases")

    for name, value in desired.attributes.items():
        if obj.attributes.get(name) != value:
            changes.append(f"attr:{name}")
    if managed:
        for name in set(managed["attributes"]) - set(desired.attributes):
            if obj.attributes.has(name):
                changes.append(f"remove attr:{name}")

    if desired.poses is not None and obj.attributes.get("ambient_poses") != desired.poses:
        changes.append("poses")
    if desired.locks:
        for part in desired.locks.split(";"):
            if obj.locks.get(part.split(":", 1)[0]) != part:
                changes.append("locks")
                break

    if desired.location is not None and not _held(obj):
        target = room_objects.get(desired.location)
        if target is None or obj.location != target:
            changes.append("location")
    if desired.destination is not None:
        target = room_objects.get(desired.destination)
        if target is None or obj.destination != target:
            changes.append("destination")

    if not obj.tags.get(desired.object_id, category=desired.tag_category):
        changes.append("tag")
    if not obj.tags.get(desired.sector_id, category=SECTOR_TAG_CATEGORY):
        changes.append("sector tag")
    if managed != _desired_managed(desired):
        changes.append("managed record")
    return changes


def _apply(obj, desired, rooms):
    """Make obj match desired. `rooms` maps room id -> room object (all exist by now)."""
    if obj.typeclass_path != desired.typeclass:
        obj.swap_typeclass(desired.typeclass, clean_attributes=False)
    if obj.key != desired.key:
        obj.key = desired.key

    managed = _managed(obj)
    wanted_aliases = {a.lower() for a in desired.aliases}
    current_aliases = set(obj.aliases.all())
    for alias in desired.aliases:
        if alias.lower() not in current_aliases:
            obj.aliases.add(alias)
    if managed:  # first run on an old-script object only records (Dev review)
        for alias in (set(managed["aliases"]) - wanted_aliases) & current_aliases:
            obj.aliases.remove(alias)

    for name, value in desired.attributes.items():
        if obj.attributes.get(name) != value:
            obj.attributes.add(name, value)
    if managed:
        for name in set(managed["attributes"]) - set(desired.attributes):
            obj.attributes.remove(name)

    if desired.poses is not None and obj.attributes.get("ambient_poses") != desired.poses:
        obj.set_ambient_poses(desired.poses)
    if desired.locks:
        obj.locks.add(desired.locks)

    if desired.location is not None and not _held(obj) and obj.location != rooms[desired.location]:
        obj.move_to(rooms[desired.location], quiet=True, move_type="teleport")
    if desired.destination is not None and obj.destination != rooms[desired.destination]:
        obj.destination = rooms[desired.destination]

    obj.tags.add(desired.object_id, category=desired.tag_category)
    obj.tags.add(desired.sector_id, category=SECTOR_TAG_CATEGORY)
    obj.attributes.add(MANAGED_ATTRIBUTE, _desired_managed(desired))


# ------------------------------------------------------------------ plan


@dataclass
class _Step:
    desired: Desired
    obj: object | None  # None = create
    changes: list


def _plan(rooms, exits, entities, report):
    room_objects = {}
    steps = []
    claimed = set()  # ids of existing objects this build owns

    def plan(desired, obj):
        if obj is None:
            steps.append(_Step(desired, None, ["created"]))
            return
        claimed.add(obj.id)
        changes = _changes(obj, desired, room_objects)
        if desired.location is not None and _held(obj) and room_objects.get(desired.location) != obj.location:
            report.held.append(f"{desired.label} is held by {obj.location.key} - left there")
        steps.append(_Step(desired, obj, changes))

    for desired in rooms:
        matches = _tagged(desired.object_id, desired.tag_category)
        if len(matches) > 1:
            report.conflicts.append(f"{desired.label}: {len(matches)} rooms carry this tag - skipped")
            continue
        room_objects[desired.object_id] = matches[0] if matches else None
        plan(desired, room_objects[desired.object_id])

    wanted_exit_ids = {d.object_id for d in exits}
    for desired in exits:
        matches = _tagged(desired.object_id, EXIT_TAG_CATEGORY)
        if len(matches) > 1:
            report.conflicts.append(f"{desired.label}: {len(matches)} exits carry this tag - skipped")
            continue
        if matches:
            plan(desired, matches[0])
            continue
        source, target = room_objects.get(desired.location), room_objects.get(desired.destination)
        if source is None or target is None:
            plan(desired, None)  # a room is new this run, so no existing exit can match
            continue
        # Adopt an exit with the same destination that's untagged (old scripts)
        # or tagged with an id no longer in the manifest (its key changed).
        candidates = [
            exi
            for exi in source.exits
            if exi.destination == target
            and not set(exi.tags.get(category=EXIT_TAG_CATEGORY, return_list=True)) & wanted_exit_ids
        ]
        if len(candidates) > 1:
            report.conflicts.append(
                f"{desired.label}: {len(candidates)} exits from {source.key} to {target.key} could be "
                "adopted - none adopted, none created"
            )
            continue
        plan(desired, candidates[0] if candidates else None)

    for desired in entities:
        matches = _tagged(desired.object_id, desired.tag_category)
        if len(matches) > 1:
            report.conflicts.append(f"{desired.label}: {len(matches)} objects carry this tag - skipped")
            continue
        plan(desired, matches[0] if matches else None)

    return steps, room_objects, claimed


def _is_room(obj):
    return obj.is_typeclass(ROOM_BASE_TYPECLASS, exact=False)


def _find_orphans(manifest, claimed, room_objects, kinds):
    """Objects this sector owns that the manifest no longer lists. That means
    sector-tagged objects, untagged objects in a category this build manages
    (built by the old scripts before sector tags existed), and unclaimed exits
    in this sector's rooms. It scans the database, not just the manifest
    (docs/engineering-pitfalls.md #3). With a `kinds` filter, entities of other
    kinds are left to the call that builds them."""
    sector_id = manifest["sector_id"]
    room_categories = {room["tag_category"] for room in manifest["rooms"].values()} or {ROOM_KIND["tag_category"]}
    entity_categories = {k["tag_category"] for name, k in KINDS.items() if kinds is None or name in kinds}

    candidates = {
        obj.id: obj
        for obj in ObjectDB.objects.filter(db_tags__db_key=sector_id, db_tags__db_category=SECTOR_TAG_CATEGORY)
    }
    for category in room_categories | entity_categories | {EXIT_TAG_CATEGORY}:
        for obj in ObjectDB.objects.filter(db_tags__db_category=category).distinct():
            if not obj.tags.get(category=SECTOR_TAG_CATEGORY, return_list=True):
                candidates.setdefault(obj.id, obj)
    for room in room_objects.values():
        if room is not None:
            for exi in room.exits:
                candidates.setdefault(exi.id, exi)

    orphans = []
    for obj in candidates.values():
        if obj.id in claimed:
            continue
        sectors = obj.tags.get(category=SECTOR_TAG_CATEGORY, return_list=True)
        if sectors and sector_id not in sectors:
            continue  # another sector's object
        if not _is_room(obj) and obj.destination is None:
            categories = {category for _key, category in obj.tags.all(return_key_and_category=True)}
            if not categories & entity_categories:
                continue  # an entity kind this call isn't building
        orphans.append(obj)
    return sorted(orphans, key=lambda o: o.id)


def _label(obj):
    tags = [t for t in obj.tags.all(return_key_and_category=True) if t[1] != SECTOR_TAG_CATEGORY]
    tag = f"{tags[0][0]}/{tags[0][1]}" if tags else "untagged"
    return f"{obj.key} ({obj.dbref}, {tag})"


def _prune(orphans, sector_id, report):
    """Delete orphans, except anything a player or character could lose (Dev review)."""
    required = set(REQUIRED_ROOM_IDS.get(sector_id, []))
    pruning = {obj.id for obj in orphans}
    rooms, others = [], []
    for obj in orphans:
        if obj.has_account or obj.is_typeclass(CHARACTER_TYPECLASS, exact=False):
            report.blocked.append((_label(obj), "a character - never pruned"))
            pruning.discard(obj.id)
        elif _held(obj):
            report.blocked.append((_label(obj), f"held by {obj.location.key}"))
            pruning.discard(obj.id)
        elif _is_room(obj):
            rooms.append(obj)
        else:
            others.append(obj)

    blocked_rooms = []
    for room in rooms:
        room_tags = set(room.tags.all())
        reason = None
        if room_tags & required:
            reason = "required by game code (REQUIRED_ROOM_IDS)"
        elif any(item.id not in pruning for item in room.contents):
            reason = "not empty"
        elif ObjectDB.objects.filter(db_home=room).exclude(id__in=pruning).exists():
            reason = "something uses it as home"
        if reason:
            report.blocked.append((_label(room), reason))
            blocked_rooms.append(room)
    for room in blocked_rooms:
        rooms.remove(room)

    for obj in others + rooms:
        report.pruned.append(_label(obj))
        obj.delete()


# ----------------------------------------------------------------- build


def _server_is_running():
    return SERVER_PID.is_file()


def build(sector_id, *, kinds=None, dry_run=False, prune=False, force_live=False, manifest=None):
    """Build or update a sector from its manifest. Returns a BuildReport.

    kinds:      limit entities to these kind names (rooms and exits always build).
    dry_run:    plan and report only; write nothing.
    prune:      delete orphans (reported either way), within the safety rules.
    force_live: allow writing while server/server.pid exists. Don't.
    manifest:   a manifest dict instead of the exported file (tests).
    """
    manifest = manifest if manifest is not None else load_manifest(sector_id)
    if manifest.get("format_version") != FORMAT_VERSION:
        raise SectorBuildError(f"Unknown manifest format_version {manifest.get('format_version')!r}.")
    if manifest.get("sector_id") != sector_id:
        raise SectorBuildError(f"Manifest is for sector {manifest.get('sector_id')!r}, not {sector_id!r}.")
    if not dry_run and _server_is_running() and not force_live:
        raise SectorBuildError(
            "The game server looks live (server/server.pid exists). Stop it first - writing the database "
            "under a running server is unsafe. A dry run is fine."
        )
    kinds = set(kinds) if kinds is not None else None

    report = BuildReport(sector_id=sector_id, dry_run=dry_run)
    rooms, exits, entities = _desired_from_manifest(manifest, kinds)
    steps, room_objects, claimed = _plan(rooms, exits, entities, report)
    orphans = _find_orphans(manifest, claimed, room_objects, kinds)
    report.orphans = [_label(obj) for obj in orphans]

    for step in steps:
        if step.obj is None:
            report.created.append(step.desired.label)
        elif step.changes:
            report.updated[step.desired.label] = step.changes
        else:
            report.unchanged.append(step.desired.label)
        if step.obj is not None:
            report.objects[step.desired.object_id] = step.obj

    if dry_run:
        print(report.summary())
        return report

    # Rooms first (exits and entities need them), then exits, then entities -
    # the order _plan() produced.
    built_rooms = {room_id: obj for room_id, obj in room_objects.items() if obj is not None}
    for step in steps:
        desired, obj = step.desired, step.obj
        if obj is None:
            obj = create_object(
                desired.typeclass,
                key=desired.key,
                location=built_rooms.get(desired.location) if desired.location else None,
                destination=built_rooms.get(desired.destination) if desired.destination else None,
            )
        if desired.label.startswith("room "):
            built_rooms[desired.object_id] = obj
        if step.changes:
            _apply(obj, desired, built_rooms)
        report.objects[desired.object_id] = obj

    if prune and report.conflicts:
        # An unadopted exit in a conflict is also an orphan; pruning it would
        # leave the room pair with no exit at all.
        report.blocked += [(label, "not pruned: resolve the conflicts first") for label in report.orphans]
    elif prune:
        _prune(orphans, sector_id, report)
    print(report.summary())
    return report
