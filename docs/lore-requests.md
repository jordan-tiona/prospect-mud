# Lore request queue

Any lane that needs lore it doesn't have adds an entry here instead of inventing it (CLAUDE.md hard rule 7). The Lore lane works through the queue; Jordan approves resolutions.

Format (see `docs/game-plan.md` Section 4):

**IDs are prefixed by the requesting lane** (`LR-OWNER-0001`, `LR-DEV-0001`, `LR-TOOLS-0001`, `LR-TESTS-0001`, `LR-REVIEW-0001`), numbered within that lane. Lanes work on separate branches and can't see each other's new entries until merge, so unprefixed numbers collide (LR-0001 and LR-0002 below were both created as LR-0001). Take the next number after the highest existing one for your own lane.

```
## LR-<LANE>-0001: <short title>
- Requested by: owner | dev | tools | tests | playtest-review
- Needed for: <feature, file, or finding>
- What's needed: <specific question or content>
- Blocking: yes | no
- Status: open | drafted | approved | rejected
- Resolution: <bible section or content file, once approved>
```

**Batch requests** (MUD editor, `docs/mud-editor-sector-format.md` Section 8.1) ask for several candidates to choose from rather than one specific answer. Use the same fields, plus:

```
- Batch: <count> <rooms | ambient NPCs | objects | ...> for <area>
- Constraints: <anything specific; room descriptions don't mention directions or exits unless stated here>
```

Lore delivers each candidate as a Draft content file in its usual folder, with `request: LR-<LANE>-<n>` in its metadata header. The editor groups candidates by that line. The owner places the ones they want and dismisses the rest; unchosen candidates aren't rejections of the request.

---

## LR-0001: Civic Office skitter ledger and Iri's pest-log framing
- Requested by: dev
- Needed for: post-quest skitter loop (`world/build_skitter_ledger.py`, `content/npcs/iri_vael.md`'s `## Actions`)
- What's needed: (1) the ledger's room line and `look`/`read` description. Write them in `content/objects/civic_office_skitter_ledger.md` (`## Short Description` and `## Description`) - not in `world/build_skitter_ledger.py`. The game still reads the Python copy until the MUD Editor's `build_sector()` replaces the build scripts, so Dev or Tools copies the approved text across after; editing only one of the two would leave the other stale. The per-player count line is appended by code and isn't part of this. (2) Review the minimal in-world framing in Iri's `## Actions` section: that the office keeps a pest log, that Iri is the one who logs reports, and that she knows Tarin lends out the baton. (3) Whether Tarin should know Iri by name (his `## Actions` now points players to "Iri Vael at the Civic Office"). Parts (2) and (3) are in `## Actions` sections, which are Dev-lane files: write proposed wording into Resolution below instead of editing them, and Dev applies it.
- Blocking: no
- Status: approved (2026-10-16; part 2 trim applied by Dev; pest-log text approved; Dev/Tools key/alias/test follow-ups below still to apply)
- Resolution: (1) Text written in `content/objects/civic_office_skitter_ledger.md`, redrafted 2026-10-16 after the owner's note that the log should be **electronic**: the heading is now `# a pest log` (was `# a ledger`), the room line is "A small screen at the end of the counter shows the office's pest log.", and the description is a screen listing names and reported counts that Iri enters. Owner approved 2026-10-16; the file is `approval: Approved`. **Dev or Tools:** copy `## Short Description` and `## Description` to `prospect/world/build_skitter_ledger.py` (`ROOM_LINE`, `DESC`); change that script's `create_object(..., key="a ledger")` to the new heading; give the entity aliases such as `["log", "screen"]` in `sectors/elsewhere/sector.json` (Tools) so `look log` / `read log` work; and update `prospect/world/test_build_skitter_ledger.py`, which does `read ledger`. Nothing else in code conflicts: `SkitterLedgerObject`'s appended line ("Under your name: N skitters logged.") and the engine-state messages in `world/skitters.py` already say "pest log", not "ledger"; identifiers (`object_id`, `LEDGER_PROP_ID`, the typeclass name) can keep the word. (2) The authored framing now lives in Iri's persona prose as a `## Skitters and the pest log` section (`prompt_version` 13 -> 14), covering the pest log, Iri keeping it, and Tarin lending the baton. **Dev:** in her `## Actions` section, delete the `TODO(lore)` comment and the first paragraph below it ("Skitters - small, six-legged scavenging pests ... it only comes up when they do."), since the persona now says all of that; keep the "Every turn, a separate engine message tells you this player's actual standing in the pest log" paragraph and the `log_dead_skitters_with_iri` bullet unchanged. (3) Owner decided 2026-10-16 that Tarin knows Iri by name, and more broadly that the whole Old Quarter cast know one another; Tarin's `## Actions` reference to "Iri Vael at the Civic Office" stands as written, and the cast-wide awareness is recorded in bible 14.6 and each persona's prose (see the commit "Lore: the Old Quarter cast know one another").

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

## LR-DEV-0001: PROBE descriptions, and teaching PROBE in the Medical Bay tannoy
- Requested by: dev
- Needed for: the new `probe <thing>` command (`prospect/commands/probe.py`, owner-approved design 2026-10-16). `look <thing>` is unchanged; `probe` shows a longer, closer description. Until one is written, `probe` shows the `look` text, so nothing is broken meanwhile.
- What's needed:
  1. **Probe descriptions** - a longer, closer look than the existing `## Description`, for what's placed in Elsewhere:
     - Ambient objects (`content/ambient/objects/`) and objects (`content/objects/`): a new `## Probe Description` section after `## Description`. For the pest log, civic display, signpost and planting bed, `probe` shows their per-player `look` text for now, so they can be skipped.
     - Ambient NPCs (`content/ambient/npcs/`): the same `## Probe Description` section.
     - Talk NPCs (`content/npcs/`, all six): a `probe_desc:` line in the metadata comment, next to `desc:` - **not** a body section, since the persona body is sent to the model.
     Any object or NPC can be left without one. No out-of-character hints in the text (owner, 2026-10-16); extra detail lines such as condition or size will come from the engine later.
  2. **Tannoy wording** - the Medical Bay tannoy (`prospect/world/tutorial.py`, `_ROOM_TANNOYS`, still `TODO(lore)`) now has a placeholder clause teaching PROBE alongside SAY, directions and LOOK. Final wording for the whole announcement, including PROBE, is still the owner's to write or approve.
- Blocking: no
- Status: approved (2026-10-16). Tannoy wording approved by the owner and applied by Dev 2026-10-16; the probe texts and the four new `desc:` lines approved by the owner 2026-10-16, and their per-field Draft flags removed from the files' metadata. **Tools:** re-export Elsewhere so the probe text reaches the manifest.
- Resolution: (1) **Probe descriptions** drafted 2026-10-16 as a `## Probe Description` section after `## Description` in `content/ambient/objects/` (`civic_services_board`, `concourse_arrival_directory`, `square_noticeboard`, `workshop_parts_tray`), `content/objects/` (`faulty_heating_module_hint`, `misdelivered_parcel_hint`, `gardening_kit`) and `content/ambient/npcs/` (all three); and as a `probe_desc:` metadata line for all six talk NPCs in `content/npcs/`. Mara, Tarin, Iri and Veska had no `desc:` line at all (so `look` showed Evennia's default), and the owner agreed 2026-10-16 to draft a short `desc:` for those four alongside the `probe_desc:`. The pest log, civic display, signpost and planting bed are skipped as requested. No physical detail is written for the engineered peoples (Mara, Given, the courtyard neighbor, the courier) or for Aevyrin facial anatomy (Veska): bible 5.5-5.7 and 5.3 mark those Provisional/Unresolved, and the owner chose 2026-10-16 to keep them out until the planned worldbuilding session on the peoples; those entries describe clothes, posture, manner and what the person is doing. Each new section/line carried a `... Draft (LR-DEV-0001 ...)` flag in its file's metadata comment until the owner approved them all on 2026-10-16; the flags are now removed. (2) **Tannoy wording** (Dev-lane file `prospect/world/tutorial.py`, `_ROOM_TANNOYS["medical_bay"]`; Dev applies once approved). Proposed replacement for the whole announcement, adding the `tannoy` repeat command (`commands/tannoy.py`) since a player who missed it has no other way to learn it exists:

  > A tannoy near the ceiling crackles to life: "Attention, new arrivals. To talk to someone, type SAY and then what you want to say. To move, type a direction, such as NORTH or SOUTHWEST. To look at something you can see, type LOOK and then its name. To study it more closely, type PROBE and then its name. To hear this again, type TANNOY."

## LR-TOOLS-0003: Remove stray direction lines from the square noticeboard
- Requested by: tools
- Needed for: `content/ambient/objects/square_noticeboard.md`, shown live on `look noticeboard` in Old Quarter Square.
- What's needed: Its `## Description` ends with a `--------------------------` separator and five direction lines ("North: Corner Café", "South: Residential Courtyard", "East: Maintenance Workshop", "West: Civic Office", "Up: Lift Concourse"). They look like leftover drafting notes, and players see them. "Up" is also wrong now: the Lift Concourse is northeast of the square. Remove everything from the separator down, keeping the paragraph above it, and per spec 8.1 don't mention directions in the description. Then re-approve. Players see the change after the next export and rebuild.
- Blocking: no
- Status: approved (2026-10-16)
- Resolution: Removed the separator and the five direction lines from `content/ambient/objects/square_noticeboard.md`'s `## Description`; the paragraph above them is unchanged. No new prose was written, so the file stays `approval: Approved` on the strength of its existing approval. Directions in the square come from the exits and the signpost (`content/objects/old_quarter_square_signpost.md`), not this board. Reaches players after the next export and rebuild.
