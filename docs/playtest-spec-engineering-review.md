# Engineering Review — Initial Playtest Design Spec

**Reviewing:** `docs/prospect-initial-playtest-design-spec.md` (2026-10-14 draft)
**Reviewer:** Claude Code
**Scope of this document:** answers to the nine questions in the spec's §12, grounded in what the codebase actually contains today. No code written yet. Flags open design decisions rather than resolving them unilaterally, per CLAUDE.md.

## Status (2026-10-14)

Rooms/route, the signpost, chargen, and the Given/Daven personas (§1, §2, §7) are now implemented and tested, per the project owner's direction on exit choices and the `give_directions` assignment. Combat/login-stasis (§4, §6) are still open; Quest 1/2 (§3) haven't been started.

## Headline finding

This spec is a big step up from every prior phase, and the gap is uneven. Quests 1 and 2 are mostly *extension* of infrastructure that already exists and is well-tested (`world/commitments.py`, `world/actions.py`, the hint-object/lock pattern). Character creation, login/stasis, and — especially — Quest 3's shared-mob combat are **entirely new subsystems** with no prior art in this codebase to extend. CLAUDE.md's current "out of scope" list explicitly names combat, inventory progression, and persistent character identity as things *not* to build unless asked. This spec is the project owner asking — but CLAUDE.md itself still reads as if phase 1's boundaries hold, which will read as contradictory to anyone (including me, in a future session with no memory of this conversation) who checks it before touching this work. **Recommend updating CLAUDE.md's "Phase 1 prototype scope" section once this spec is approved**, so it reflects the current approved scope instead of a stale phase boundary. That's a documentation question, not one I'm deciding here.

---

## 1. Character creation / account identity — IMPLEMENTED

Built as `commands/chargen.py` (`CmdScriptedCreate`, overloading Evennia's default `create` in `UnloggedinCmdSet`) plus `world/chargen.py` for the pure validation/application logic. Not an EvMenu: Evennia's unlogged-in commands support a `yield`-based generator pattern (the stock `create` command already uses one `yield` for its y/n confirmation) that turns out to be the right tool for a fully linear, narrated Q&A — this flow chains several `yield` prompts in sequence (name → sex → species → review/confirm, looping back to the top on "no" → password → confirm password), then calls `Account.create()` to do the actual account/character creation (reusing its existing username/password validation rather than reimplementing it) and finally logs the session in, which triggers Evennia's own default auto-puppet-and-look.

**Settled:** species is a validated field, constrained to the seven canon peoples (`world/chargen.py`'s `SPECIES_CHOICES`), accepted by name or list number — not free text. Sex is validated to male/female. Both are stored as `db.species`/`db.sex` on the Character, set once via `apply_identity()` right after creation.

Passwords are typed in plain text into the prompt (same as Evennia's own default `create <name> <password>`, which has no masking either — this doesn't regress anything) and go straight into `Account.create()`; they never reach `world/conversation_log.py` or any NPC-facing code path. Tests: `world/test_chargen.py` (species/sex validators, identity application, Medical Bay placement).

## 2. Room graph / route — IMPLEMENTED

`world/build_rooms.py` extended with three new rooms and, per the project owner's 2026-10-14 direction choices: Old Quarter Square → **northeast** → Lift Concourse (moved off its original up/down — envisioned as the base of the elevator up to the low/no-gravity docking area, so "up" no longer describes *reaching* it from the square), Lift Concourse → **up** → Medical Bay, Square → **southwest** → Old Quarter Street, Street → **north** → Daven's Office. A new `CHAINS` list in that module handles connections off a non-hub room (Lift Concourse→Medical Bay, Street→Office), alongside the existing hub-and-spoke `SPOKES`. `world/build_ambient.py`'s `ROOM_IDS` got the three new tags so their (currently Draft) content auto-applies once approved, same as the original six.

**Settled:** a signpost, not a notice board — `typeclasses.objects.SignpostObject` (new), built by `world/build_signpost.py` (new), placed in Old Quarter Square. Its route to Daven's Office is computed dynamically via the same BFS (`world/actions.py`'s `_find_exit_path`) `give_directions` already uses, so it can't drift from the real map; only the "what's this way" one-liners for the square's other spokes are hand-authored flavor. Tests: `world/test_build_rooms.py`, `world/test_build_signpost.py` (including a test that severs the real exit and confirms the signpost's claimed route disappears with it).

## 3. Quest/commitment infrastructure — how much is reusable

This is the strongest part of the existing codebase for this spec. `world/commitments.py`'s generic lifecycle (`propose_commitment` → `accept_commitment`/`decline_commitment` → `report_commitment_outcome`/`accept_handoff`, with per-scenario `ScenarioConfig` entries in `SCENARIOS`) already supports exactly Quest 1's shape: Mara proposes, a real object changes hands, Tarin is a second holder, completion is checked against real state, not dialogue. `deliver_parcel`'s existing scenario (Mara proposes, Tarin *or* Veska holds/completes, with a real locked `Parcel` object per `_create_parcel_for`/`_actor_has_correct_parcel`) is nearly the exact shape of "fetch faulty module, hand to Tarin, get replacement, return to Mara" — Quest 1 should be a new `ScenarioConfig` entry plus two new item-flavored validators in `world/actions.py`, not new infrastructure.

Quest 2 (locker → gardening kit → use-on-planting-bed) is also mostly covered by existing patterns: a real, gettable object (unlike `Parcel`, which is deliberately locked against drop/give) in a known room, and a "use X on Y" validated action — `world/actions.py` has no existing "use item on room object" validator, but the shape (an action name the NPC's persona doesn't even need to grant, since the player is acting on the world, not talking to Iri) is new but small, and the completion check (kit was used on the bed) still plugs into `fulfill_commitment_with_precondition` the same way the parcel's physical-possession check does.

Quest 3 (combat) is the one quest that **does not fit this model at all** — see §5 below. It isn't a commitment between a player and an NPC's engine-recorded state; it's a shared, concurrent, global-entity system with none of commitments.py's per-player assumptions.

## 4. Combat / shared mob visibility

Confirmed: no combat system exists anywhere in `prospect/` — no `combat`, `attack`, `hp`, `health`, or `damage` handling, no existing shared/global entity typeclass. This is net-new.

The per-player visibility mechanic the spec wants for skitters, though, is **not** new in kind — `server/conf/lockfuncs.py`'s `commitment_hint_visible` lock function already does exactly this pattern (`view`/`search` locks gated on a per-looker commitment state, used by `world/build_quest_props.py`'s hint objects). A skitter's visibility lock can follow the same shape: gated on whether the looker has Tarin's hunting eligibility flag, rather than on commitment state. That reuse is genuine and should hold.

What's new and needs real design attention before I write anything:
- A **shared global entity** is a different lifecycle from anything commitments.py models — per-player attributes (`actor.db`) can't represent "this one skitter, which both Alice and Bob can see, just died." It needs its own typeclass and a small amount of server-global state (a Script, most likely, tracking the ~2 active skitter instances and their rooms), not player-attribute storage.
- Concurrent-attack dedup ("kills count once... cannot duplicate rewards") needs an explicit lock or state-check at the moment of a kill being credited, not just "first attack wins" — two players attacking the same tick is a real race in Evennia's single-threaded command-execution model, but respawn-and-despawn timing across players needs its own test coverage, which doesn't exist yet for anything like this.
- "Not in the defeated creature's room, not in an inaccessible one" needs the same real-exit-graph BFS already written for `give_directions`/the notice-board route, reused for valid spawn-room selection.

This is genuinely the biggest unknown in the spec. I'd want to scope it as its own small design doc (parallel to `docs/phase2-quest-prototype-design.md`) before writing it, the same way every commitment scenario got one.

## 5. Command normalization / aliases

Partially exists, informally. There's no generalized alias/normalization layer — `prospect/commands/` has `say.py`, `look.py`, `admin.py` as explicit custom commands; everything else (movement, `get`, `examine`) is still Evennia's own default command set (`commands/default_cmdsets.py` just assembles the defaults plus these additions), which already handles a fair amount of the table in spec §7 (`l`/`look`, `n`/`north`, `get`/`take`) via Evennia's built-in aliasing. `world/speech_format.py`'s `normalize_speech` is the one existing precedent for "normalize varied player phrasing before it reaches engine logic," but it's scoped to speech punctuation/question detection, not command verbs. "use kit on planting bed" and "attack skitter"/"kill skitter"/"hit skitter with baton" style free-form targeting syntax doesn't exist and will need new command classes (parallel to `say.py`'s `CmdSay` override) rather than relying on default Evennia command matching, which doesn't parse "use X on Y" or "VERB TARGET with ITEM" shapes out of the box.

## 6. Login/logout/stasis

**Confirmed against Evennia's own source** (`evennia/objects/objects.py`): `at_post_unpuppet` is a no-op (`pass`) by default, so a disconnected character's body genuinely just sits in its room, listed and interactable, until something overrides that — not a bug, an intentional default for games that want linkdead bodies to stay vulnerable/visible, but not what this spec wants. Still net-new, not yet built: an `at_post_unpuppet`/`at_disconnect` override to apply the "stasis" presentation (brief message, then remove from room listing and `who`, store last location) and a lock or flag blocking targeting/damage on a disconnected character. That last part is a hard dependency on whatever Quest 3's combat system ends up checking before allowing an attack, so this and §4 still need to be designed together, not sequentially.

## 7. NPC content / reuse — IMPLEMENTED

`Mara`, `Tarin`, `Iri` all have real persona files (`content/npcs/*.md`) with populated `## Actions` sections — these are extensible for Quest 1/2, as discussed in §3. `Given Marr` (`content/npcs/given_marr.md`) and `Daven Varek` (`content/npcs/daven_varek.md`) are now written, transcribed from `docs/prospect-playtest-new-characters-and-rooms.md` into the standard persona format - not invented here. Given has no NPC-specific action (just the shared `remember_fact`); per the project owner's 2026-10-14 call, `give_directions` went to Daven rather than Given, with its destination list extended to all nine rooms. Both are wired into `world/build_npcs.py`.

## 8. Logging / consent

`world/conversation_log.py` already logs full prompt, model ID, prompt version, and a `review_status`/`annotations` field reserved for human curation per design-bible 14.7 — and already deliberately excludes the API key. It does **not** yet have any password-adjacent field to exclude, because nothing currently sends anything password-like near an NPC or a log — chargen must keep it that way (per the spec's own explicit requirement), meaning the chargen flow should go through Evennia's own `set_password`/account layer directly and never pass through `conversation_log.log_turn` or any NPC-facing code path at all. Player consent/retention policy for bringing in outside testers is a project-owner/legal-style decision, not an engineering one — flagging it rather than answering it.

## 9. New local content needing approval

Per the spec's own §12.9 and CLAUDE.md's authored-content rule: Given, Daven, the Medical Bay, the street, Daven's office, the gardening kit/locker, the skitters (name/appearance/biology — spec itself notes origin is undecided and flags the "not native to Prospect" constraint), and the weapon are all new in-world content requiring project-owner approval before any persona/room-description file is written. Everything else (Mara, Tarin, Iri's existing personas and the six original rooms) is already-approved content to extend, not replace, consistent with the spec's own §2 instruction to reuse rather than replace.

---

## Suggested sequencing (not a plan — flagging dependency order only)

1. CLAUDE.md scope update (quick, blocks nothing else but should happen first so later sessions aren't confused).
2. Rooms + notice-board route (small, no new design decisions, builds on #2/#3 above).
3. Quest 1 and 2 as new commitment scenarios (biggest reuse, least risk).
4. Chargen (self-contained, no dependency on combat).
5. Login/stasis + combat visibility together (§4/§6 share the "can this character be targeted" check).
6. Combat itself last — it's the one piece needing its own design doc before implementation, the same way every commitment scenario got one.

Happy to turn any of these into an actual implementation plan once you've had a chance to weigh in — especially on the chargen species/sex vocabulary question (§1) and whether Quest 3 gets its own scoping doc before code (§4).
