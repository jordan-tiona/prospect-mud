# Lore request queue

Any lane that needs lore it doesn't have adds an entry here instead of inventing it (CLAUDE.md hard rule 7). The Lore lane works through the queue; Jordan approves resolutions.

Format (see `docs/game-plan.md` Section 4):

**IDs are prefixed by the requesting lane** (`LR-DEV-0001`, `LR-TOOLS-0001`, `LR-TESTS-0001`, `LR-REVIEW-0001`), numbered within that lane. Lanes work on separate branches and can't see each other's new entries until merge, so unprefixed numbers collide (LR-0001 and LR-0002 below were both created as LR-0001). Take the next number after the highest existing one for your own lane.

```
## LR-<LANE>-0001: <short title>
- Requested by: dev | tools | tests | playtest-review
- Needed for: <feature, file, or finding>
- What's needed: <specific question or content>
- Blocking: yes | no
- Status: open | drafted | approved | rejected
- Resolution: <bible section or content file, once approved>
```

---

## LR-0001: Civic Office skitter ledger and Iri's pest-log framing
- Requested by: dev
- Needed for: post-quest skitter loop (`world/build_skitter_ledger.py`, `content/npcs/iri_vael.md`'s `## Actions`)
- What's needed: (1) the ledger's room line and `look`/`read` description - currently plain placeholders in `world/build_skitter_ledger.py` (`ROOM_LINE`, `DESC`); the per-player count line is appended by code and isn't part of this. (2) Review the minimal in-world framing in Iri's `## Actions` section: that the office keeps a pest log, that Iri is the one who logs reports, and that she knows Tarin lends out the baton. (3) Whether Tarin should know Iri by name (his `## Actions` now points players to "Iri Vael at the Civic Office").
- Blocking: no
- Status: open
- Resolution:

## LR-0002: Remove Iri Vael's dual-room note
- Requested by: tools
- Needed for: MUD Editor sector format (`docs/mud-editor-sector-format.md` Section 9). Each entity is built in exactly one room, and content-file `room:` metadata no longer drives placement.
- What's needed: Drop "(may also appear in the Residential Courtyard)" from `content/npcs/iri_vael.md`'s `room:` metadata and from any persona prose that implies she's sometimes elsewhere. Project owner has already decided she's in the Civic Office only.
- Blocking: no
- Status: open
- Resolution:
