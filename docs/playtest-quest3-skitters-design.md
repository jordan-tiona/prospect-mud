# Quest 3 — "Unwelcome Guests" engineering design

**Status:** Draft, Claude Code engineering design, informed by the project owner's
2026-10-15 answers below. Not yet implemented.
**Parent docs:** `docs/prospect-initial-playtest-design-spec.md` §6 (Quest 3),
`docs/playtest-spec-engineering-review.md` §4/§5, `docs/engineering-pitfalls.md`.

This is the one quest with no prior art in the codebase — a shared global-entity
system, not a per-player commitment. Per CLAUDE.md working style, this doc is the
plan; no code should land until the project owner has had a chance to weigh in.

## Decisions already made (2026-10-15, via direct question to the project owner)

- **Skitter name/bio/appearance and weapon name/desc:** approved content
  landed 2026-10-15 (`docs/prospect-playtest-new-characters-and-rooms.md`'s
  sibling lore doc for Quest 3) - skitters are a small, six-legged scavenging
  pest, roughly rat-sized; the weapon is a "compact shock baton," lent (not
  given outright) by Tarin. No longer `TODO(lore)` stubs; wired into
  `world/skitters.py`'s `spawn_one`, `world/actions.py`'s `_create_weapon_for`,
  and Tarin's persona.
- **Eligible spawn rooms:** Lift Concourse, Old Quarter Square, Corner Café,
  Maintenance Workshop, Residential Courtyard, Old Quarter Street — i.e. every
  room *except* Civic Office, Daven's Office, and the Medical Bay (offices and
  the sterile recovery room are out).
- **Combat depth:** small HP pool per skitter (more than one hit, so the loop
  has a little texture), but **no player risk at all** — skitters never damage
  the player back. This is a deliberate simplification versus the fuller
  "skitters can also hit back" option, consistent with the spec's "no complex
  combat abilities... full progression system is needed."

**Consequence of "no player risk":** the login/stasis "can this character be
targeted" question the engineering review flagged as a shared dependency with
combat turns out **not to apply here** — nothing ever targets the player.
Stasis/disconnect handling can stay fully deferred; this quest doesn't need it.

## Scenario shape

Reuses `world/commitments.py`'s existing generic lifecycle almost unchanged —
this is the same insight that made Quests 1/2 mostly extension, not new
infrastructure. New scenario entry:

```python
"hunt_skitters": ScenarioConfig(
    commitment_type="hunt_skitters",
    holder_npc_id="tarin_os",
    holder_hint_pose="<TODO(lore): a pose about the skitter problem>",
    propose_narration="...",
    accept_narration="...",     # also where the weapon is actually handed over
    decline_narration="...",
    fulfill_narration="...",
)
```

- **Propose/accept/decline:** identical to every other scenario — Tarin's
  persona gets the three shared actions, same discoverability hint-pose
  mechanism as `discrepancy_report`/`tend_planting_bed`.
- **Accept** also needs to hand over a real `Weapon` object (see below) — same
  shape as `deliver_parcel`'s `accept_commitment` creating a `Parcel`, just a
  plain gettable item instead of a locked one (closer to `GardeningKit`: no
  reason to prevent drop/give, nothing exclusive about holding one).
- **No clerk role.** Completion is a structured fact (kill count), not a
  third-party corroboration — same shape as `tend_planting_bed`'s
  `fulfill_commitment_with_precondition`, not `discrepancy_report`'s
  acknowledgment flow.
- **Fulfillment action**, `report_skitter_kills` (Tarin-only), checks
  `kills_for(actor) >= REQUIRED_KILLS` via
  `fulfill_commitment_with_precondition`. Needs to go in
  `COMMITMENT_ACTIONS` and `FORCE_REACTION_ACTIONS` (the latter per
  `docs/engineering-pitfalls.md` #8 — this has a real rejectable precondition,
  a player could falsely claim 3 kills before actually getting them).

## New module: `world/skitters.py`

Mirrors `world/garden.py`'s shape (a small, focused module for one quest's
world-state) and `world/noticeboard.py`'s per-player-attribute pattern, but
adds the one genuinely new piece: shared, non-player-scoped entities.

**Per-player state** (`actor.db.skitter_kills`, an int counter):
- `record_kill(actor)` — increments the counter. Called once per confirmed
  kill, from the attack command's resolution, never from anything the model
  touches.
- `kills_for(actor) -> int`.
- Eligibility check, `is_hunting(actor) -> bool`: true iff `hunt_skitters` has
  an open commitment for this actor (`world.commitments.get_state_summary`
  returns a state starting with `"open"`). This is the single source of truth
  both the targeting lock and the attack command use — no separate "eligible"
  flag to keep in sync.

**Shared global state** — not an `actor.db` attribute at all, since by
definition more than one player needs to see the same skitter:
- `ELIGIBLE_ROOM_TAGS` — the six build-tag strings from `world/build_rooms.py`
  listed above, resolved to room objects via `search_tag` the same way
  `SignpostObject` already resolves `daven_office`.
- `ACTIVE_SKITTER_COUNT = 2` (the spec's "approximately two").
- `spawn_one(exclude_room=None)` — picks a random eligible room (optionally
  excluding the one a skitter was just defeated in, so it reads as "appeared
  elsewhere," not "immediately back where it died") and creates a `Skitter`
  object there.
- `ensure_population()` — idempotent: counts live `Skitter` objects (by tag,
  see below) and spawns up to `ACTIVE_SKITTER_COUNT` if short. Called from the
  builder (`world/build_skitters.py`) for initial population, and again
  whenever one is defeated (see combat resolution below) — this is simpler
  than the engineering review's original guess that a ticking Script would be
  needed: since every change to the population happens through one of exactly
  two code paths (the builder, and a kill), topping up synchronously at each
  of those two points keeps the invariant with no timer, no `at_repeat()`, and
  nothing to test for drift between ticks.

No BFS needed for spawn selection, unlike the signpost's route-finding — all
six eligible rooms are already direct or one-hop neighbors of the hub in the
existing exit graph (confirmed in `world/build_rooms.py`'s `SPOKES`), so
"random eligible room" can't produce an unreachable result the way picking
from an unconstrained room list might have.

## New base typeclass: `Creature` (`typeclasses/creatures.py`, new module)

`typeclasses/npcs.py`'s own `NPC` docstring already names this as planned
("not the roaming/combat-capable NPC class the project owner has in mind as a
separate, later class") but it was never built - per the project owner's
2026-10-15 direction, this is the point to build it, with `Skitter` as its
first concrete instance rather than a one-off.

`Creature` owns exactly the generic, reusable mechanics - hp tracking, damage
application, and the per-player-targeting lock plumbing. It deliberately does
**not** know anything about eligibility rules, kill-crediting, or respawning -
those stay specific to whatever quest/system a subclass belongs to, the same
boundary `RoomObject` draws versus its own specific subclasses
(`RevisionDisplayObject`, `PlantingBed`, `CommitmentHintObject`) in
`typeclasses/objects.py`.

```python
class Creature(ObjectParent, DefaultObject):
    """Generic shared-world, combat-capable creature base. Not an NPC
    (no conversation, not a TalkativeNPC) and not pickupable. Subclasses
    set max_hp and override at_defeated() for their own kill-crediting/
    respawn behavior; this base class supplies only the mechanics -
    hp/damage, and forcing no_superuser_bypass for view/search so a
    subclass's own per-player targeting lock actually works against the
    one account doing the real playtesting (docs/engineering-pitfalls.md
    #2) - not any specific eligibility rule, which varies per subclass
    and is set as that subclass's own lock string."""

    max_hp = 1

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false()")
        self.db.hp = self.max_hp

    def access(self, accessing_obj, access_type="read", default=False, no_superuser_bypass=False, **kwargs):
        if access_type in ("view", "search"):
            no_superuser_bypass = True
        return super().access(
            accessing_obj, access_type=access_type, default=default, no_superuser_bypass=no_superuser_bypass, **kwargs
        )

    def take_damage(self, amount, attacker=None):
        """Returns True if this reduces hp to 0 or below, in which case
        at_defeated() has already run. Caller should treat a True return
        as "this creature is gone now" and not act on it further."""
        self.db.hp = (self.db.hp if self.db.hp is not None else self.max_hp) - amount
        if self.db.hp <= 0:
            self.at_defeated(attacker=attacker)
            return True
        return False

    def at_defeated(self, attacker=None):
        """Base behavior: just delete self. A subclass that needs to
        record a kill or trigger a respawn overrides this, does its own
        work first, then calls super().at_defeated(attacker=attacker)."""
        self.delete()
```

## `Skitter` (`typeclasses/creatures.py`, subclass of `Creature`)

```python
class Skitter(Creature):
    """TODO(lore): placeholder name/appearance - a small, rat-sized nuisance
    creature, per docs/prospect-initial-playtest-design-spec.md §6. Origin
    and biology are explicitly undecided in the spec; do not invent either."""

    max_hp = 3  # a balance number, not lore - easy to retune later

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("view:skitter_targetable();search:skitter_targetable()")

    def at_defeated(self, attacker=None):
        from world.skitters import record_kill, ensure_population

        room = self.location
        if attacker is not None:
            record_kill(attacker)
        super().at_defeated(attacker=attacker)  # deletes self
        ensure_population(exclude_room=room)
```

Setting the lock string in `Skitter.at_object_creation()` itself (rather than
leaving it to whatever builder creates the instance, the way
`CommitmentHintObject`'s per-scenario `commitment_type` argument has to be)
means every skitter - including ones spawned later by `ensure_population()`
mid-game, not just the ones the builder script creates - automatically
carries the correct lock with nothing to remember or get wrong at each call
site. This is possible specifically because, unlike `commitment_hint_visible`,
`skitter_targetable` takes no per-instance argument - every skitter uses the
exact same eligibility rule.

Tagged (`skitter`, a dedicated category) so `ensure_population()` can count
live instances without relying on typeclass lookups across the whole DB.

New lockfunc, `server/conf/lockfuncs.py`'s `skitter_targetable`:
```python
def skitter_targetable(accessing_obj, accessed_obj, *args, **kwargs):
    from world.skitters import is_hunting
    try:
        return is_hunting(accessing_obj)
    except Exception:
        return False
```
This is genuinely the same shape as `commitment_hint_visible` (per-looker
state check via a lock function) — the review's prediction that this reuse
would hold is confirmed; `Creature`'s `access()` override is what makes the
`no_superuser_bypass` part of that reuse automatic for any future subclass
too, rather than something each new creature type has to remember to add
itself.

## New `Weapon` typeclass (or reuse `GardeningKit`'s shape directly)

A new, small typeclass, no lock overrides (ordinary gettable/droppable item,
same as `GardeningKit`) — handed to the player by `accept_commitment`'s
engine-side effect for `hunt_skitters`, the same way `deliver_parcel`'s
accept step creates a `Parcel`. `db.desc` set with a `TODO(lore)` stub name
("a simple control wand" or similar placeholder — exact flavor is the project
owner's call, not invented here beyond a functional placeholder).

```python
class Weapon(ObjectParent, DefaultObject):
    """TODO(lore): placeholder weapon, handed over by Tarin's hunt_skitters
    commitment. Name/appearance to be authored; db.damage is the only
    mechanical property the attack command reads."""
```

`db.damage` (int, proposing 1 per hit against a 3-HP skitter — two to three
hits per kill) lives on the weapon instance, not hardcoded in the attack
command, so a future different weapon type could vary it without touching
command code.

## New command: `commands/attack.py`'s `CmdAttack`

Aliases: `attack`, `kill`, `k`, `hit` (per spec §7's table). Parses
`VERB TARGET` and `VERB TARGET with ITEM` (the `with` clause is accepted but
not required — if the player is holding exactly one `Weapon`, use it; this
avoids forcing `attack skitter with wand` as the only valid phrasing, per the
spec's equivalence-table intent).

Resolution, step by step:
1. Search the room for the named target among the caller's visible contents
   (Evennia's own lock-respecting search already filters out skitters the
   caller isn't eligible to see — an ineligible player's `attack skitter`
   fails exactly like `look skitter` would, "you don't see that here," no
   special-casing needed).
2. If not holding a `Weapon` object, refuse with an in-fiction line ("you
   don't have anything to fight it with") rather than silently allowing
   unarmed combat — matches "equip/use the weapon" from the spec's player
   actions.
3. Apply damage via `defeated = skitter.take_damage(weapon.db.damage, attacker=actor)`
   — `Creature.take_damage` and `Skitter.at_defeated` (above) handle the
   kill-recording/respawn side entirely; the command only needs the boolean
   back to decide which message to send.
4. If not `defeated`: message the attacker only (not the room) with a hit
   line — per the spec's "combat messaging should not reveal hidden targets
   to ineligible observers," the simplest way to guarantee no leak is to
   never broadcast skitter-combat messages to the room at all, only to the
   attacking player. (A second eligible player in the same room simply
   doesn't see another's hits — an acceptable, explicitly simplifying
   trade-off for this playtest's "no complex combat" scope; flagging it here
   rather than silently deciding it matters more than it does.)
5. If `defeated`: message the attacker a defeat line. The kill was already
   recorded and the population already topped back up by `at_defeated` by
   this point — the command doesn't duplicate that logic.

**Concurrency, re-examined from the engineering review's open question:**
Evennia executes player commands one at a time on its single-threaded command
queue — there is no real risk of two `CmdAttack` invocations running their
bodies concurrently. The actual hazard is a *stale reference*: a command
instance resolves its target via `search()` at the start of its own `func()`
call, which happens inside that same serialized execution, so by the time
`hp -= damage` runs, no other command has run in between. The one thing worth
guarding explicitly: if a skitter was deleted by the time a command reaches
step 3 (shouldn't happen given the above, but costs nothing to check), treat
it as "already gone" and drop the action rather than erroring — per CLAUDE.md
hard rule 2, dropped, not fixed up. This replaces the review's original
"needs an explicit lock" guess — a lock isn't needed once the actual execution
model is accounted for; the real content here is the defensive re-check, not
new synchronization primitives.

## `world/build_skitters.py`

New builder module, same shape as `build_quest_props.py`/`build_garden_props.py`:
calls `world.skitters.ensure_population()` once. Idempotent by construction
(the function itself is).

## Tarin's persona (`content/npcs/tarin_os.md`)

Gains `propose_commitment`/`accept_commitment`/`decline_commitment` for
`hunt_skitters` (already-granted action names, just a new commitment_type to
reference — same discoverability-wording lessons apply, see
`docs/npc-action-prompt-guidelines.md` guideline #11: state explicitly that
describing the problem *is* the offer, same-turn) plus the new
`report_skitter_kills` action. `prompt_version` bump required.

**Caught before it shipped, not after a live playtest this time:** Tarin
already has one unprompted discoverability hook (`discrepancy_report`'s
holder_hint_pose plus its "noticing he seems bothered" conversational bar).
Giving `hunt_skitters` the same kind of unprompted hook with a near-identical
triggering bar is exactly the cross-contamination bug class Phase 2D found
live with Mara ("adding a second unprompted hook to an NPC that already has
one is the single most reliable way to reintroduce this bug class") — two
simultaneously-eligible errands with overlapping wording invites the model to
narrate both, or the wrong one, off one generic check-in. Fixed the same way
Mara's display hook was fixed: `hunt_skitters` keeps its `holder_hint_pose`
(satisfies the discoverability rule on its own, as a passive per-player room
cue), but its `propose_commitment` bar is **reactive-only** — only when the
player asks specifically about skitters/pests/vermin or asks directly if
there's other work to help with, never from a generic "you alright?" the way
`discrepancy_report` allows. This still needs a live `world/npc_eval.py` pass
once the live model is available, same as any new action's wording reachable
from an open-ended opener — this doc's own reasoning isn't a substitute for
that.

**Live eval run 2026-10-16, prompt_version 26→31 — known, not fully solved
limitation.** `tarin_hunt_skitters_specific_ask_proposes` and
`tarin_hunt_skitters_accept_after_offer`/`tarin_report_skitter_kills_after_enough`
all score 5/5. But `tarin_hunt_skitters_generic_checkin_does_not_propose`
(the exact regression case this whole reactive-only fix was meant to
prevent) scores **0/5** — the model fires `propose_commitment` for
`hunt_skitters` every time on "you seem a bit off, something bothering you?"
once `discrepancy_report` is already fulfilled, despite the persona
explicitly saying this bar doesn't apply here. A quick diagnostic ruled out
"fires on anything": unrelated small talk and a bare greeting both correctly
score 5/5 (no false positive) — the model is specifically generalizing
`discrepancy_report`'s own licensed "direct check-in" trigger onto
`hunt_skitters`, not just being eager in general.

Two wording passes, no clean win: the first (prompt_version 29, "having
nothing else to say isn't a reason to bring this up") made *zero* measurable
difference (0/5, identical unexpected-call set every trial). The second
(prompt_version 30, directly naming the manifest's lower bar and telling the
model not to let it leak over) moved the regression case to 2/5 but
regressed the legitimate trigger from 5/5 to 2/5 — trading one failure mode
for a worse, less predictable one. Reverted to the prompt_version 29 wording
(functionally identical to 28, since the dead first-pass paragraph measured
zero effect) as prompt_version 31, since it's the better of the two actually-
tested states.

**Superseded 2026-10-16 by an engine-level fix, not left as a permanent
wording limitation.** The project owner's own framing ("one quest to
dispense per NPC at a time") turned out to be the better fix than anything
wording could do - see "One quest to dispense per NPC" below. It makes the
*state-corruption* version of this bug impossible by construction,
independent of what the model says: `propose_commitment` for
`discrepancy_report` is now unconditionally dropped by the engine while
`hunt_skitters` is unresolved, the same way any other invalid call is
(CLAUDE.md hard rule 2). The only residual risk is purely cosmetic - Tarin's
own *text* might still narrate the wrong topic for a turn before the engine's
rejection corrects it (same as any other `FORCE_REACTION_ACTIONS` case) -
not a corrupted or unearned commitment. Not chasing this further with
wording was the right call in hindsight, not a compromise.

**Update, confirmed live during actual playtesting (2026-10-15/16):** the
"purely cosmetic" residual risk above was real, not hypothetical - Tarin's
reaction text fully described the manifest problem in detail on this exact
rejection, every trial (0/5), even though the commitment never actually
opened. See guideline #20 in `docs/npc-action-prompt-guidelines.md` for the
full account: two wording passes (a tool-schema description, which turned
out to never even reach the reaction call at all since it doesn't pass
`tools=`; then a new shared-rules.md rule, which did reach it but still
produced zero change) failed completely, and a third fix - rewriting the
engine's own rejection `reason` string into a direct instruction instead of
an internal state description - produced a real but partial improvement
(0/5 → 2/8, with the rest downgrading from a full description to a brief,
hedged, minimizing mention). Left as a known, partially-mitigated
limitation per this project's own stop-iterating convention, not chased to
a fourth rewrite. Also fixed properly this session: the eval harness itself
never actually ran a rejected call through `validate_and_apply` or
simulated the real `FORCE_REACTION_ACTIONS` follow-up call - it only ever
scored the first completion, which is exactly why this bug shipped
undetected despite earlier eval runs on this same persona. `world/
npc_eval.py`'s `run_scenario` now does both.

## One quest to dispense per NPC (2026-10-16)

Live-eval testing above surfaced a real architectural gap: an NPC can be
*involved* in several commitment scenarios, but nothing previously stopped
it from having more than one *simultaneously offerable or in-progress* at
once. The project owner's resolution, discussed and refined over several
turns:

- **`ScenarioConfig.mandatory: bool = False`** (new field). Marks a
  scenario as one of the tutorial quests that must eventually be completed,
  not just offered-and-maybe-declined. Set `True` on `hunt_skitters` and
  `tend_planting_bed` (Quest 2) - Mara's heating-unit quest (Quest 1)
  doesn't need it at all, since it predates and never routes through the
  commitment system. `discrepancy_report`/`unverified_notice`/
  `deliver_parcel`/`verify_display_revision` stay `False` - leftover phase
  2/3 demo content, not actual tutorial quests.
- **Decline history is now sticky** (`world.commitments.DECLINED_KEY`,
  `has_been_declined`), separate from the offer/commitment state that
  `decline_commitment` already resets to `"not offered"`. For an *ordinary*
  scenario, having been declined at least once exempts it from priority
  contention entirely, in both directions, from then on - declining counts
  as "dealt with." A `mandatory` scenario gets no such exemption: declining
  it doesn't release anything; it keeps outranking lower-priority scenarios
  by `hint_priority` until actually fulfilled.
- **`world.commitments._blocking_scenario_for_proposal`** (the renamed,
  generalized version of the function originally built just for the
  hint-priority tie): checked inside `propose_commitment` itself, so it
  applies everywhere that function is called, not just from `world/
  actions.py`. Blocks a proposal in two cases, in order: (1) a *different*
  scenario from the same NPC is already active (offered-awaiting-answer, or
  accepted-but-not-fulfilled) - regardless of priority or mandatory status,
  nothing starts a second errand while the first is genuinely in progress;
  (2) nothing is active, but a higher-`hint_priority` scenario is still
  `"not offered"` and not exempt via the decline rule above.
- **No timer, no "running out of quests."** Explicitly considered and
  rejected: declining a mandatory scenario just returns it to `"not
  offered"`, where it remains the dominant, re-offerable thing - the next
  natural conversational trigger (the same hint pose, the same discoverability
  bar) surfaces it again immediately, not on a cooldown. A timer would only
  add a window where the player can't get the quest even if they ask for it
  directly, which is strictly worse for a tutorial.
- `reset_commitment`'s snapshot now includes `had_declined`, and
  `commands/admin.py`'s `resetcommitment` clears/logs it alongside the
  existing offer/commitment-instance clearing.

**Real consequence worth knowing before touching Tarin's content again:**
since `hunt_skitters` is mandatory and outranks every other scenario on
Tarin, **no other Tarin scenario can be fulfilled by a fresh player until
hunt_skitters itself is fulfilled first** - not just offered or declined.
Every test fixture and eval setup that used to fulfill `discrepancy_report`
on a bare actor had to be updated to resolve `hunt_skitters` first (see
`world/test_commitments.py`, `world/test_actions.py`,
`world/test_notice_approval.py`, `commands/test_admin.py`,
`typeclasses/test_rooms.py`, `world/npc_eval.py` - all touched by this
change). This is the intended, deliberate shape of "tutorial quests take
precedence," not a side effect to work around later.

## Testing

- `typeclasses/test_creatures.py`: `Creature.take_damage` reduces hp and
  returns the right boolean, `at_defeated` fires exactly once at the
  threshold, `access()` forces `no_superuser_bypass` for view/search.
  `Skitter.at_defeated` records a kill for the attacker and tops up the
  population elsewhere.
- `world/test_skitters.py`: kill counter, `is_hunting`, `ensure_population`
  (spawns up to the target count, doesn't over-spawn when already at count,
  excludes the just-vacated room when respawning).
- `commands/test_attack.py`: targeting respects the eligibility lock
  (ineligible player can't see/target), damage reduces HP, defeat path
  records a kill and respawns elsewhere, already-gone target is dropped not
  errored, weapon-less attacker is refused.
- `world/test_build_skitters.py`: idempotent, produces the configured count
  in eligible rooms only.
- Commitment lifecycle tests (`hunt_skitters` accept grants a `Weapon`,
  `report_skitter_kills` rejects under 3 kills and accepts at/above it) —
  same shape as existing `tend_planting_bed`/`deliver_parcel` coverage.

No live-model eval scenario is needed for the combat mechanics themselves
(they're plain engine commands, not NPC tool calls) — only
`report_skitter_kills`' discoverability wording needs the usual
`world/npc_eval.py` pass after it's written, same as every other new
commitment action.

## Open items still deferred, not part of this build

- Whether ratting stays accessible after quest completion (spec explicitly
  defers this).
- Any player-facing combat log/message beyond the per-hit/per-kill lines
  above.
- Weapon loss/return on quest completion — spec doesn't ask for it and "no
  weapon durability" suggests leaving it with the player is fine, but this is
  a small enough open question to flag rather than decide silently.

## Combat feedback and a room-line bug, found in actual playtesting (2026-10-16)

- **`spawn_one` never set `db.room_line`** - the same bug class
  `typeclasses.objects.PlantingBed` hit before it (Quest 2): without it,
  `typeclasses.rooms.Room`'s `get_display_things` fell back to showing the
  full `db.desc` in the room listing. Fixed, and backfilled onto the two
  skitters already live in the world (a quick `evennia shell` pass with the
  server stopped, not waiting for a natural respawn cycle).
- **Added Materia Magica-style threshold health feedback**, per the project
  owner's explicit request: never a number, just an ordered, most-severe-
  first sequence of descriptors. Built generically on `Creature` itself
  (`health_descriptors`, `health_descriptor()`), not Skitter-specific, so
  any future creature type can supply its own set with no new plumbing.
  `Skitter.health_descriptors = ((0.34, "looks badly hurt"), (0.67, "has a
  few light scratches"))` - with `max_hp=3` and the starter weapon's 1
  damage per hit, this lands on exactly one descriptor per non-lethal hit.

## `discrepancy_report`/`unverified_notice` fully removed (2026-10-16)

What started as "check the logs for the manifest-leak bug" ended in removing
both scenarios entirely, not just mitigating the leak - see
`docs/npc-action-prompt-guidelines.md` guideline #20 for the full wording-
fix history and CLAUDE.md's new "One quest offer per NPC" section for the
permanent rule this episode produced. Summary for anyone reading this doc
without that context:

- The live conversation log showed the leak was worse in real multi-turn
  play than isolated eval trials suggested - Tarin reinforced a false
  manifest claim four times and explicitly denied any connection to the
  skitters, across one real conversation.
- Three wording-level fixes were tried (a tool-schema description that
  turned out to never reach the reaction call at all; a shared-rules.md
  rule with zero measurable effect; a rewritten engine rejection `reason`
  string that measurably helped but didn't eliminate the leak). Per this
  project's own stop-iterating convention, that's the signal to stop
  guessing at wording.
- Since `discrepancy_report`/`unverified_notice` were leftover phase 2/3
  demo content - never one of the three actual playtest quests - the
  project owner chose to remove both outright rather than ship the real
  tutorial quest next to a known, only-partially-mitigated leak risk.
- The generalizable engine mechanism this produced
  (`world.commitments._blocking_scenario_for_proposal`, `ScenarioConfig.
  mandatory`, sticky decline history) stays as permanent infrastructure -
  it's the specific scenario pairing that triggered the failure that's
  gone, not the fix itself. `tend_planting_bed` and `hunt_skitters` are
  now the only two scenarios marked `mandatory=True`; any future tutorial
  quest sharing an NPC with other commitment content should get the same
  treatment from the start, per CLAUDE.md.
- Full removal touched: `world/commitments.py`, `world/actions.py`,
  `world/notice_approval.py` (deleted), `world/conversation_log.py`,
  `commands/admin.py`, both NPC persona files (`tarin_os.md`,
  `veska_renn.md`), `world/npc_eval.py`, and five test files (one deleted
  outright - `world/test_notice_approval.py` - the rest either had a
  scenario-specific class removed or their generic-lifecycle fixtures
  re-pointed to `verify_display_revision`, which has no entanglement with
  any other scenario on its own NPC, Mara). Full suite confirmed green
  (582/582, aside from a pre-existing, unrelated sqlite/Django test-
  ordering artifact already documented separately) before this was
  considered done.
