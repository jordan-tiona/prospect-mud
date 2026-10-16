# Errand redistribution plan: parcel to Veska, display check to Daven

Status: **plan, awaiting owner sign-off on Section 3** (written 2026-10-16, Dev lane)

## 1. Goal and decisions already made

Move Mara Voss's two legacy commitment errands to NPCs who currently give no quests:

| Errand (`commitment_type`) | Giver now | Giver after | Completed by |
|---|---|---|---|
| Misdelivered parcel (`deliver_parcel`) | Mara | **Veska Renn** | Tarin (holder) |
| Display revision check (`verify_display_revision`) | Mara | **Daven Varek** | Daven (holder), Iri corroborates (clerk) |
| Heating unit (Quest 1, separate `quest_context_for` system) | Mara | Mara (unchanged) | Tarin / Mara |

Owner decisions (2026-10-16):

- Move both errands rather than retire them; they're kept for playtest coverage.
- Daven may give an errand, even though the playtest spec says he isn't the giver for the *three introductory* activities. This is a fourth, side errand. Given was considered for it and rejected.

Why:

- **One quest offer per NPC (CLAUDE.md).** After the move, every quest-giving NPC has exactly one errand: Mara has the heating unit, Iri the planting bed, Tarin the skitters, Veska the parcel, and Daven the display check. That ends the parcel/display/heating cross-contamination on Mara.
- **Prompt size, as a side effect.** Mara drops about 2.5k persona tokens and five tool schemas: `propose_commitment`, `accept_commitment`, `decline_commitment`, `report_commitment_outcome` and `report_parcel_delivery`. Veska and Daven each gain roughly 1–1.5k tokens. Total tokens per call stay about the same; the saving only shows to the extent players talk to Mara more than to Veska and Daven.

## 2. Current wiring (as of f128aad)

**`deliver_parcel`** (`world/commitments.py` `SCENARIOS`):
- `proposer_npc_id="mara_voss"`, `holder_npc_id="tarin_os"`, `alt_holder_npc_ids=("veska_renn",)`.
- The discoverability cue is the `misdelivered_parcel_hint` `quest_prop` in `corner_cafe` (`sectors/elsewhere/sector.json`; text in `content/objects/misdelivered_parcel_hint.md`, "sits on the counter").
- On accept, `world/actions.py` `_create_parcel_for` puts a locked `Parcel` on the player. Its desc reads "Tarin Os, Maintenance Workshop."
- Fulfilled by `accept_handoff` from Tarin *or* Veska.
- **Phase 2E "word gets around"** (`world/rumors.py`, `docs/phase2e-word-gets-around-design.md`): `project_mara_parcel_knowledge` is wired as the scenario's `proposer_knowledge_projector`. Mara keeps seeing "open" until the player tells her and `report_parcel_delivery` validates it. `_validate_report_parcel_delivery` hard-codes `npc_id != "mara_voss"`, `_RUMOR_RECIPIENT_NPC_IDS` / `_RUMOR_RECIPIENT_DISPLAY_NAMES` (tarin/veska), and `_adjust_reputation(actor, "mara_voss", 1)`. The tool schema's `reported_recipient` enum is `["tarin", "veska"]`.
- `commands/admin.py` reset clears the rumor state plus `reset_reputation(target, "mara_voss")`, and runs `cleanup_stray_parcels`.

**`verify_display_revision`**:
- `holder_npc_id="mara_voss"` (also the proposer, since `proposer_npc_id` is empty), `clerk_npc_id="iri_vael"`.
- `holder_hint_pose="glancing at the café's information display"`.
- The `civic_information_display` entity (kind `revision_display`, `RevisionDisplayObject`) is in `corner_cafe`. Its per-player revision lives in `world/noticeboard.py`, reset by `reset_expected_revision`.
- Mara closes it with `report_commitment_outcome`; Iri corroborates with `verify_revision_report`.

**Persona and content references** (each must change; Lore unless marked Dev):
- `content/npcs/mara_voss.md`
  - Lore: the `## Your misdelivered parcel` and `## Your café's civic display` sections; the parcel and display wording inside `## Your heating unit` ("that's the parcel's territory").
  - Dev: the `## Actions` paragraphs for the five actions above, and the parcel/display lines in the per-turn engine-state paragraph.
- `content/npcs/veska_renn.md`
  - Lore: the "Civic Office can also take in an ordinary misdirected parcel" prose (around line 54).
  - Dev: the `accept_handoff` bullet in `## Actions`.
- `content/npcs/tarin_os.md`
  - Lore: "the thing Mara…" wording (around line 48) and the `## Receiving a parcel` framing.
  - Dev: the parcel lines in `## Actions`.
- `content/npcs/iri_vael.md`
  - Lore: the "display… including the one at Mara Voss's café" paragraph (around line 37).
  - Dev: the `verify_revision_report` bullet, if it names Mara or the café.
- `content/npcs/daven_varek.md`
  - Lore: `## Mentor behavior` says he doesn't assign Mara's, Tarin's or Iri's tasks. That still holds, but it needs to sit alongside his own errand.
- `content/objects/misdelivered_parcel_hint.md`: Lore (counter / café framing).
- `content/objects/civic_information_display.md`: Lore (check for café framing).
- `content/rooms/corner_cafe.md`, `civic_office.md`, `daven_office.md`: Lore. Room prose may mention the display or parcel.

**Tests touching these scenarios:**
- `world/test_commitments.py`, `world/test_actions.py`, `world/test_rumors.py`
- `world/test_npc_eval.py`, `world/test_build_quest_props.py`
- `commands/test_admin.py`, `commands/test_say.py`, `typeclasses/test_rooms.py`

**`world/npc_eval.py`:** about 12 scenarios with `npc_id="mara_voss"`. The parcel and display ones need re-targeting; setups include `_setup_mara_parcel_offered`, `_MARA_PARCEL_HANDED_OFF_CONTEXT` and others.

## 3. Open decisions (owner) and recommendations

**D1. Keep "word gets around" for the parcel?** It means Veska only learns the parcel arrived when the player comes back and tells her.
- *Recommended: keep it.* It gives the player a reason to return to the giver, which helps the RPG feel. The rumor module is already generic apart from its hard-coded IDs.
- If kept, **drop the `reported_recipient` argument**. With Tarin as the only possible recipient it has one value, and the long "never invent `reported_recipient`" prompt wording in Mara's `## Actions` existed only to stop the model guessing between two names. The validator simply checks the parcel is fulfilled.
- Alternative: remove the projector, and Veska sees "fulfilled" as soon as Tarin takes the parcel. That's simpler and removes one action, but there's no return trip.

**D2. Remove Veska as an alternative recipient?**
- *Recommended: yes.* It would be odd for a player to bring the parcel back to the NPC who gave it to them.
- The parcel's whole point becomes "this belongs to Tarin, take it to him". `alt_holder_npc_ids` becomes empty and Veska loses `accept_handoff`.

**D3. Where does the reputation point go?**
- *Recommended: Veska*, the giver, matching how Mara earned it before.
- `reset` must also keep clearing `mara_voss` reputation for existing test data (engineering-pitfalls #3).

**D4. Mandatory or ordinary?**
- *Recommended: ordinary* (`mandatory=False`, unchanged). These are side errands, not tutorial quests.
- With one errand per NPC there is no contention either way.

**D5. In-flight test data.** Commitment type names don't change, so stored records stay readable. A test character mid-parcel under the old wiring may hold a parcel Veska won't take back (D2), or have a reputation point on Mara.
- *Recommended:* after deploy, run `resetcommitment` on the dev/test characters. No external playtester has state yet.

## 4. Steps

Order: **Lore → Dev + Tools (landed together) → live verification.**

- Dev can't ship before Lore. Without the new prose, Veska's and Daven's prompts would have actions with no errand to offer. Mara's would still describe errands she can no longer offer, which is the "narrating an action it can't take" failure in the guidelines doc.
- Tools' prop moves must land with Dev's engine change. Otherwise the parcel hint sits in the café for an errand only Veska can give.

### Step 1: Lore request (Dev files it, Lore writes it, owner approves)

File **LR-DEV-0003** in `docs/lore-requests.md`. Batch it with LR-DEV-0002 (same persona files: Mara's redirect role and each NPC's single knowledge subject), so each persona gets one coherent rewrite, not two passes that clash.

Content needed, following D1–D3 as decided:

1. **Veska.** A `## Your misdelivered parcel` section, as giver: why it's at the Civic Office, that it's Tarin's, when she brings it up (passive cue below, or a general "anything I can help with"). Remove the "office takes in parcels" holder framing.
2. **Daven.** A section on the display in his office and why he wants its revision checked with Iri. When he raises it (only when asked about the display, as Mara's was). How it fits with his mentor rule of not assigning other people's tasks.
3. **Daven's `holder_hint_pose`.** Replaces "glancing at the café's information display". Dev copies it into `commitments.py`, since a pose is authored text.
4. **Mara.** Remove the parcel and display sections and the cross-references to them in `## Your heating unit`. Coordinate with LR-DEV-0002's redirect wording.
5. **Tarin.** `## Receiving a parcel` and the line around 48: the parcel comes by way of Veska / the Civic Office, not Mara.
6. **Iri.** The display paragraph: Daven's office display, not Mara's café.
7. **`content/objects/misdelivered_parcel_hint.md`.** Short description and description for the Civic Office, not "on the counter" of the café.
8. **`content/objects/civic_information_display.md`, and room files** (`corner_cafe`, `civic_office`, `daven_office`). Any wording that places the display or parcel in the café.
9. **People you know.** Each NPC's line on Veska and Daven, if their errands should be known to neighbors. Optional. Keep to "know them by name and job" unless the owner wants more.

### Step 2: Dev — engine (`world/`)

Check `docs/engineering-pitfalls.md` #1, #3 and #4 and `docs/npc-action-prompt-guidelines.md` before starting.

1. **`world/commitments.py` `SCENARIOS`:**
   - `deliver_parcel`: `proposer_npc_id="veska_renn"`, `alt_holder_npc_ids=()` (D2). Update the narrations if Lore supplies new ones; the current ones are giver-neutral apart from "hands {actor} the parcel", which still works.
   - `verify_display_revision`: `holder_npc_id="daven_varek"`, `holder_hint_pose=<Lore text>`.
   - Update the comments that name Mara.
2. **`world/rumors.py`:** rename `project_mara_parcel_knowledge` to `project_giver_parcel_knowledge` (or similar) and update the docstrings. The stored `RUMOR_KEY` data shape is unchanged.
3. **`world/actions.py`:**
   - Update the `_project_mara_parcel_knowledge` import and wiring.
   - `_validate_report_parcel_delivery`: role check against `SCENARIOS["deliver_parcel"].effective_proposer_npc_id` instead of a hard-coded `"mara_voss"` (pitfall #1 shape). Drop or shrink the recipient mapping (D1). Reputation goes to the proposer (D3).
   - Tool schema for `report_parcel_delivery`: description no longer says "Tarin or Veska"; drop `reported_recipient` (D1).
   - `_create_parcel_for` comments: the "café / Mara's counter" references.
4. **`commands/admin.py` reset:**
   - Clear reputation for both `veska_renn` and `mara_voss`. Mara's is legacy data, which pitfall #3 says to keep clearing.
   - Update `log_rumor_reset`'s field name (`previous_mara_reputation`) or make it a dict keyed by `npc_id`; the conversation log schema should stay readable.
   - `cleanup_stray_parcels` is unchanged and already scans by tag.
5. **`world/entity_kinds.py`:** nothing. `quest_prop`'s `commitment_type` values are still `["deliver_parcel"]`.
6. **`world/noticeboard.py`, `typeclasses/objects.py`:** comment-only updates ("café furniture").

### Step 3: Dev — persona metadata and `## Actions`

Follow `docs/npc-action-prompt-guidelines.md`. Moved wording is not new wording, but every action bullet must be re-read for the new giver's situation.

| Persona | `actions:` metadata change | `## Actions` change |
|---|---|---|
| Mara | remove `propose_commitment`, `accept_commitment`, `decline_commitment`, `report_commitment_outcome`, `report_parcel_delivery` | Delete those bullets and the parcel/display engine-state paragraph. Re-check that the heating-unit bullets don't cross-reference the parcel. |
| Veska | add `propose_commitment`, `accept_commitment`, `decline_commitment`, `report_parcel_delivery`; remove `accept_handoff` (D2) | Port Mara's parcel bullets: `propose`/`accept`/`decline` scoped to `deliver_parcel` only, plus the simplified `report_parcel_delivery` (D1). Engine-state paragraph for `deliver_parcel` as proposer. |
| Daven | add `propose_commitment`, `accept_commitment`, `decline_commitment`, `report_commitment_outcome` | Port Mara's display bullets, scoped to `verify_display_revision` only. Includes the hard-won "explain *and* ask in the same reply" rule (guideline #20 territory). |
| Tarin | none | Parcel bullets: comes from Veska, Tarin is the only recipient. |
| Iri | none | `verify_revision_report` bullet: Daven's display, if it names Mara or the café. |

Bump `prompt_version` on every persona touched (Lore's edits bump it too; take the higher).

### Step 4: Tools — sector placement

In `sectors/elsewhere/sector.json`, done in the Tools lane or by Dev with a Tools review as the lane table requires:

- `misdelivered_parcel_hint.room`: `corner_cafe` → `civic_office`.
- `civic_information_display.room`: `corner_cafe` → `daven_office`.

Then re-export. Rebuild the sector (`build_sector`) with the server **stopped** (see memory: live DB writes), and check that the old café instances are removed rather than duplicated (engineering-pitfalls: orphaned objects).

### Step 5: Tests (Dev)

- Update the tests listed in Section 2 for the new NPC IDs.
- Add:
  - Veska can propose, accept and decline `deliver_parcel`; Mara's calls for it are now dropped (role check).
  - Daven can propose and close `verify_display_revision`; Mara's calls are dropped.
  - Veska's `accept_handoff` for the parcel is rejected (D2).
  - `report_parcel_delivery` is validated against the proposer, not the literal `"mara_voss"`.
  - Reset clears both Veska's and Mara's reputation.
  - One-quest-per-NPC: each of Veska and Daven offers exactly their own scenario. Mara's `commitment_context_for` is empty.
  - `PromptBuilder` / persona tests: Mara's `actions` no longer include the commitment actions.
- Re-target `world/npc_eval.py` parcel/display scenarios to Veska/Daven and update their setup helpers.
- Full `./run_tests.sh` green before commit.

### Step 6: Live verification (owner)

After deploy, `evennia reload` (and the `build_sector` run from Step 4), then `resetcommitment` on test characters (D5):

1. Mara: ask "how are you / anything I can help with". She should mention only the heating unit, never the parcel or display. Check her prompt size in `conversations.jsonl`: she should drop by about 2.5k tokens plus the tool schemas.
2. Civic Office: `look`. The parcel is visible on a fresh character and disappears once offered. Veska offers it, the player accepts and carries it, and Tarin takes it. Veska still believes it's open until told, the player tells her, she's glad, and the reputation point lands on Veska (D1/D3).
3. Daven's office: the display is visible and Daven shows his hint pose. Asking about the display gets explain-and-ask in one reply. Read the number to Iri, then back to Daven, who closes it.
4. Re-run the npc_eval suite for the moved scenarios (it costs model calls; owner's call when).

## 5. Risks

- **Daven's character drift.** He's the "don't assign tasks" mentor, and now has one errand of his own. Lore's wording has to keep these distinct, or he may start offering errands on other NPCs' behalf. Watch for this live.
- **Wording regressions.** Mara's parcel and display `## Actions` text holds many playtest-hardened fixes. Porting it to a new NPC with a different situation can bring old failures back, such as narrating instead of calling, or calling on a question. Plan one live pass per errand, per the tuning style.
- **Civic Office crowding.** Iri and Veska are both in one room and both now give quests: Iri the planting bed, Veska the parcel. Unaddressed speech already prompts players to name someone, but watch for confusion over who offered what.
- **Spec drift.** The playtest spec's Daven line ("not the quest giver for the three activities") stays true but now reads as incomplete. Consider a one-line note in the spec about side errands; that's the owner's call.
