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
- What's needed: (1) the ledger's room line and `look`/`read` description. Write them in `content/objects/civic_office_skitter_ledger.md` (`## Short Description` and `## Description`) - not in `world/build_skitter_ledger.py`. The game still reads the Python copy until the MUD Editor's `build_sector()` replaces the build scripts, so Dev or Tools copies the approved text across after; editing only one of the two would leave the other stale. The per-player count line is appended by code and isn't part of this. (2) Review the minimal in-world framing in Iri's `## Actions` section: that the office keeps a pest log, that Iri is the one who logs reports, and that she knows Tarin lends out the baton. (3) Whether Tarin should know Iri by name (his `## Actions` now points players to "Iri Vael at the Civic Office"). Parts (2) and (3) are in `## Actions` sections, which are Dev-lane files: write proposed wording into Resolution below instead of editing them, and Dev applies it.
- Blocking: no
- Status: drafted (parts 1-2 written 2026-10-16; owner to approve the ledger text; Dev to apply the trim below)
- Resolution: (1) Ledger text written in `content/objects/civic_office_skitter_ledger.md` (`## Short Description` and `## Description`), still `approval: Draft` until the owner reads it; once approved, **Dev or Tools copy both back to `prospect/world/build_skitter_ledger.py` (`ROOM_LINE`, `DESC`)**. (2) The authored framing now lives in Iri's persona prose as a `## Skitters and the pest log` section (`prompt_version` 13 -> 14), covering the pest log, Iri keeping it, and Tarin lending the baton. **Dev:** in her `## Actions` section, delete the `TODO(lore)` comment and the first paragraph below it ("Skitters - small, six-legged scavenging pests ... it only comes up when they do."), since the persona now says all of that; keep the "Every turn, a separate engine message tells you this player's actual standing in the pest log" paragraph and the `log_dead_skitters_with_iri` bullet unchanged. (3) Owner decided 2026-10-16 that Tarin knows Iri by name, and more broadly that the whole Old Quarter cast know one another; Tarin's `## Actions` reference to "Iri Vael at the Civic Office" stands as written, and the cast-wide awareness is recorded in bible 14.6 and each persona's prose (see the commit "Lore: the Old Quarter cast know one another").

## LR-0002: Remove Iri Vael's dual-room note
- Requested by: tools
- Needed for: MUD Editor sector format (`docs/mud-editor-sector-format.md` Section 9). Each entity is built in exactly one room, and content-file `room:` metadata no longer drives placement.
- What's needed: Drop "(may also appear in the Residential Courtyard)" from `content/npcs/iri_vael.md`'s `room:` metadata and from any persona prose that implies she's sometimes elsewhere. Project owner has already decided she's in the Civic Office only.
- Blocking: no
- Status: approved (2026-10-16, including the Civic Office room edit)
- Resolution: `content/npcs/iri_vael.md` `room:` is now `Civic Office`; `prompt_version` bumped 12 -> 13. Her persona prose never said she was anywhere else ("volunteers at the Civic Office"), so no prose changed there. The only wording that implied otherwise was in the Approved room file `content/rooms/civic_office.md` ("Iri Vael volunteers in the neighborhood and can sometimes be found here"), changed to "Iri Vael volunteers here." That edits Approved content on the strength of the owner's one-room decision; revert it if that goes too far. Reaches the game on the next sector export.

## LR-TOOLS-0001: Review object text moved out of code
- Requested by: tools
- Needed for: MUD Editor export (`docs/mud-editor-sector-format.md` Sections 5-6). Export refuses entities whose content isn't `approval: Approved`, so the whole Elsewhere sector is blocked until these are resolved.
- What's needed: Review the six files in `content/objects/`: `misdelivered_parcel_hint`, `faulty_heating_module_hint`, `gardening_kit`, `planting_bed`, `civic_information_display`, `old_quarter_square_signpost`. Each holds text Dev wrote in Python as a stopgap, moved there word for word by Tools (`moved_from:` in each header). Players have already seen it in playtests. Keep or rewrite each one; the project owner then sets `approval: Approved`. The display and signpost have no `## Description` on purpose: what a look shows is generated by the engine.
- Blocking: yes (MUD Editor export)
- Status: approved (2026-10-16; all six object files now `approval: Approved`)
- Resolution: Reviewed all six in `content/objects/`. Text kept as moved (no copy-back needed): `misdelivered_parcel_hint`, `faulty_heating_module_hint`, `planting_bed`, `civic_information_display`, `old_quarter_square_signpost` (spoke lines checked against `build_rooms.py` `SPOKES`; they match). **Changed: `gardening_kit.md` `## Description` only** (the moved text had the kit both "pulled from" the locker and "kept here"); `## Short Description` unchanged. **Dev or Tools: copy that one `## Description` back** to `prospect/world/build_garden_props.py`. Each file's header `TODO(lore)` line was replaced by a review note; `moved_from:` kept. The Approved `content/rooms/old_quarter_square.md` said "someone has kept the beds tended despite everything else showing its age", contradicting the overgrown bed object and Iri's planting-bed ask; owner chose (2026-10-16) to soften the room line, now "The beds themselves have been let go, overgrown and showing their neglect as plainly as everything else here shows its age." Object and Iri unchanged. Room text reaches the game on the next sector export.

## LR-TOOLS-0002: Add approval metadata to NPC personas
- Requested by: tools
- Needed for: MUD Editor export (`docs/mud-editor-sector-format.md` Section 6). Export requires `approval: Approved` on every placed entity's content, and none of `content/npcs/*.md` has an `approval:` field, so all six talk-capable NPCs block the Elsewhere export.
- What's needed: Add `approval: Approved` (or `Draft`, if any persona isn't actually approved) to the metadata comment of `daven_varek`, `given_marr`, `iri_vael`, `mara_voss`, `tarin_os` and `veska_renn`. Project owner decided 2026-10-16 that personas go through the same approval gate as other content. The persona parser (`world/npc_profile.py`) ignores unknown fields, so adding the field doesn't affect the game. A `status:` field like the room and ambient files have is optional; decide alongside.
- Blocking: yes (MUD Editor export)
- Status: approved (2026-10-16)
- Resolution: Added `status: Provisional` and `approval: Draft` to the metadata comment of all six personas (`daven_varek`, `given_marr`, `iri_vael`, `mara_voss`, `tarin_os`, `veska_renn`), after `prompt_version`. `Provisional` follows bible 14.6's own status line (the cast are "lightweight example profiles", not established NPCs), matching the room files. All six parse unchanged through `world/npc_profile.py`. Owner approved all six on 2026-10-16; every persona is now `approval: Approved`.
