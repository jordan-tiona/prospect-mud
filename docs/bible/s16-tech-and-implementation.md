_Part of the split design bible - see [`00-index.md`](00-index.md) for the status-label legend and the full section map._

## 16. Technology and implementation boundaries

### 16.1 Established setting constraints

The home civilization possessed advanced spaceflight, orbital settlement, biotechnology, resource extraction, and sophisticated automation. Interstellar travel required generation ships sustaining populations across centuries; routine interstellar transportation was unavailable to that civilization.

The ancient AI crisis led to restrictions on general-purpose autonomous machine intelligences and independent, open-ended agency. Computers, expert systems, robotics, and automated industry remained widespread. Haven's failed containment network need not have been an unrestricted general-purpose AI.

Engineered biological capabilities are bounded. Otheryn (Void Walkers) require pressure suits and life support; Neshyr (Sea Walkers) breathe air and can live in dry shared accommodations; no engineered people is universally immune to Prospect. Technology should remain sophisticated but fallible. **Venn–Saye dynamics** adds one invented field and internally constrained magic-like effects. Ordinary Fieldworks tools are technologically operated and require **no genetic adaptation**; Dynamicists require both a school-specific genetic alteration and a **catalyst**. Neither this discovery nor modern field technology changes the original home system's limited pre-departure applications or its distrust of advanced autonomous AI.

### 16.2 Separate fiction from implementation

**Design clarification:** Using an LLM to implement an NPC does not make that character an in-world artificial intelligence. An LLM can portray an ordinary biological resident whose society restricts machine autonomy. The implementation method must not be used as evidence of an in-world technology, legal exemption, or secret AI population.

### 16.3 Remaining unresolved technical decisions

The adopted stack and NPC architecture are recorded in 16.4–16.9. Still undecided: database choice beyond Evennia's defaults, production deployment platform and hosting provider, networking/scaling architecture, the specific model that wins prototype testing, LLM failure and fallback handling, moderation tooling, and cost limits. Current-era travel capabilities and local AI law also require worldbuilding decisions rather than extrapolation from implementation choices. Fieldworks and Dynamicism introduce intended gameplay capabilities, not an implemented inventory, skill tree, combat system, or engine.

Any technical plan should separately identify settled gameplay requirements, adopted engineering choices, and missing world facts. No code, service, or completed prototype is implied by this document.

### 16.4 Adopted tech stack

**Status:** Established design direction (adopted 2026-10-10). Everything is Python, and the model sits behind one swappable API layer so moving from local testing to production is a configuration change, not a rewrite.

| Layer | Prototype | Release |
|---|---|---|
| Game engine | Evennia (Python MUD framework; theme-agnostic) | Evennia |
| Model serving | Ollama on the developer's RTX 3080 Ti (12 GB VRAM) | vLLM on rented GPUs, or a hybrid with a hosted API for some NPCs |
| Model | Open-weight model in the ~8B–14B class at 4-bit quantization (candidates: Qwen3 14B, Phi-4 14B, Gemma 3 12B) | Larger open model (30B–70B class) and/or a QLoRA fine-tuned variant |
| API interface | OpenAI-compatible endpoint | Same interface, different URL |
| Lore store | Plain files or SQLite, chunked from this bible | Same, with retrieval by relevance |

**Licensing note:** Check each candidate base model's license before release. Fine-tunes inherit their base model's license and use restrictions; this matters especially for the adult-content stretch goal (16.9).

### 16.5 NPC request flow and the tool layer

**Status:** Established design direction (adopted 2026-10-10).

The LLM is the NPC's voice; the engine is the source of truth. For each player message to a talk-capable NPC:

1. The **prompt builder** assembles a fresh prompt from the NPC's persona, the common-knowledge sheet, relevant lore from the lore store (scoped to what this NPC would know), and, from phase 2 onward, what this NPC remembers about this player.
2. The **model** returns reply text plus zero or more **tool calls** proposing actions.
3. The **engine validator** checks each tool call against authoritative game state, rules, caps and cooldowns. Valid actions are applied; invalid calls are dropped.
4. The **reply** is checked for out-of-character or offensive content, then shown to the player together with the narrated outcome of any valid actions.

**Tools:** Each NPC has a small, explicit list of permitted actions. The model can only *propose* actions; it never changes game state directly. Prototype phase 1 needs one simple action per NPC (for example `serve_item`, `hand_over_part`). Phase 2 adds actions such as `give_quest`, `share_rumor` and `adjust_reputation`.

**No bartering or negotiated prices.** NPCs never set or negotiate prices. Prices and rewards are derived by the engine from reputation. Conversation can nudge reputation only in small, capped steps with cooldowns, so manner matters over time but no single clever message moves the economy. The mechanical payoff of talking well is information (rumors, leads, hints) and access, gated by engine state.

**Cost and latency:** Only call the model when a player actually addresses a talk-capable NPC, never for ambient behavior. A one-to-three-second response delay is acceptable in a text game.

**Addressing rule (Established design direction, adopted 2026-10-11):** there is no separate `talk` command; addressing a talk-capable NPC goes through ordinary `say`. A `say` counts as addressing a present talk-capable NPC when either:

- the player names the NPC explicitly, either with `say to <name>, <message>` (the engine matches the longest run of words after "to" against a present NPC's key or alias, present NPCs only, and strips that match plus any trailing comma before the message reaches the model) or by using the NPC's name as a whole word anywhere in the message (left untouched in that case, since it's part of what the player is actually saying); or
- exactly one player and exactly one talk-capable NPC are both present in the room, with no name needed.

Any other `say` — multiple players present, no name given, and no lone NPC to default to — is ambient speech only: no model call, no reply. A room with more than one talk-capable NPC always needs an explicit name, even for a lone player.

### 16.6 Lore store, knowledge scopes and memory

**Status:** Established design direction (adopted 2026-10-10); exact schemas unresolved.

- **Lore store:** this bible split by section, with each chunk tagged by its status label. Only chunks marked **Established** are eligible for NPC prompts. Lore stays outside the model so it can be edited without retraining.
- **Knowledge scopes:** each NPC is assigned the lore slices it would plausibly know. A café owner gets neighborhood and everyday civic knowledge; she does not get Section 4's home-system history in detail.
- **Unresolved lore:** the NPC answers with ignorance, uncertainty or personal belief. Its answer never becomes canon.
- **Memory (phase 2):** a few short facts per player, written in the NPC's own words. Player claims are stored as *unverified* ("says the dock chief owes them money"), never as fact. Only engine-confirmed events become authoritative memory.
- **Shared rooms:** context fed to an NPC from other players' chatter is kept minimal and clearly labeled, so one player cannot inject instructions into another player's conversation. Whether NPCs hold one shared conversation per room or private threads per player is unresolved.

### 16.7 Safety and anti-exploit rules

**Status:** Established design direction (adopted 2026-10-10). The goal: a player can make an NPC act weird, but never make it act wrong in ways that change game state. Immutable system prompts do not guarantee immutable behavior, so the rules below put hard limits in the engine.

**Engine-enforced (never left to the model):**

- Every NPC action goes through a validated tool call.
- Prices and rewards come from engine-tracked reputation, never from negotiation.
- Reputation nudges are small, capped, per-player and on cooldown.
- Quest secrets and spoilers stay out of the prompt until the player's game state qualifies.
- Rate limits on NPC interactions per player, which also caps inference cost.

**Left to NPC judgment:** tone, personality, which rumors to share, and whether a conversation earns a small reputation nudge within its cap.

**Prompt hygiene:** player text is clearly labeled as player text; player claims enter memory as unverified; shared-room context is minimal; an output check catches out-of-character or offensive replies.

### 16.8 Development roadmap

**Status:** Established design direction; no dates or deadlines.

1. **Prototype phase 1:** the six-room neighborhood, three LLM NPCs with one validated action each, the common-knowledge sheet, scoped lore, and curated logging (Sections 13.5, 13.6, 14.6, 14.7). Exit test: conversations feel natural and distinct, NPCs admit ignorance, and tool calls are reliable enough to build on.
2. **Prototype phase 2:** per-player memory, a simple quest, rumor and reputation actions. Exit test: playtesters enjoy NPC conversations and cannot exploit game state.
3. **Expand the world:** more of Elsewhere, then ferries to other habitats; decide surface access.
4. **Fine-tune:** QLoRA on curated playtest logs for voice, setting tone and reliable tool calls, aimed at the specific gaps the stock model showed. Facts stay in the lore store.
5. **Scale for release:** move serving to vLLM on rented GPUs or a hybrid with a hosted API for key NPCs; measure cost per active player.
6. **Stretch goal:** adult content (16.9).

### 16.9 Stretch goal: adult content

**Status:** Established as a possible future stretch goal only; out of scope until the core game works. If pursued, it requires all of the following:

- **Zoned and opt-in only:** adult content happens only in designated areas or flagged scenes, with consent mechanics between players and clear scene boundaries.
- **Self-hosted models only:** mainstream hosted APIs prohibit sexually explicit content, so adult scenes need self-hosted open-weight models with permissive licenses (some licenses, such as Gemma's, prohibit this use), plus routing that keeps adult and non-adult traffic separate.
- **A hard block on any sexualization of minors or minor-coded characters,** enforced by an output classifier regardless of model or prompt. Non-negotiable.
- **Age verification** meeting the laws of the jurisdictions where players are (many US states, the UK Online Safety Act and others), and attention to payment-processor restrictions.
- **Legal review before launch.**

### 16.10 Post-prototype polish and terminal presentation notes

**Status:** Deferred cosmetic/engineering polish; not worth interrupting functional prototype tests for. Visual examples and implementation specifics here are presentation choices, **not setting lore**.

- **Drop numeric object IDs from player-facing room/object names.** Builder scripts currently print dbref numbers alongside object names for their own debug output (e.g. "Noticeboard prop ready: a civic information display (#189) in Corner Café"); these shouldn't leak into anything the player actually sees.
- **Terminal splash-screen direction:** Use the separately authored ASCII artwork: a prominent **PROSPECT** title across the center-left, overlapping a large depiction of the planet toward the right, with a sparse background of `.`, `*` and `+` stars. The foreground Elsewhere habitat concept was dropped from this composition. The currently preferred asset includes a user-adjusted layout and an ANSI-colored variant; the artwork files, not this prose, govern exact character positions.
- **Display constraints:** Aim for an approximately 80-column terminal layout and preserve all whitespace and characters when coloring. ANSI control sequences must not change visible alignment. Whether to offer a non-color fallback, screen-width handling or a replay/skip command remains an interface decision, not a finalized technical contract.

---

