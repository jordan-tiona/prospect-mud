---
description: Start a Lore-lane session
---

You are the **Lore lane** for this project, working in the `lore` worktree on the `lore` branch.

Read `CLAUDE.md`'s "Workstream lanes" section for your boundaries. In short:
- You may edit `docs/bible/`, `content/` persona/knowledge/room/object prose, and `docs/lore-requests.md`.
- You never touch game code, `world/build_*.py`, `## Actions` sections, or `content/npc-shared-rules.md`. When a request needs wording in one of those, write your proposed text into the request's Resolution field, set its status to `drafted`, and set `Handoff:` to the lane that applies it (e.g. `dev: apply the tannoy wording in Resolution`). Any other follow-up another lane owes (a code change, a re-export) also goes on the Handoff line, not only in Status.
- Bump a persona's `prompt_version` whenever your edit changes what reaches its prompt, including mechanical passes like a rename (CLAUDE.md, "Content files").
- Never invent canon on your own authority. Changes that add no new setting facts (applying the owner's decisions, consistency fixes, behaviour wording, rewording Established material) you approve yourself. Anything that adds new canon stays `approval: Draft`, and your end-of-session summary lists each new item in one plain-language line for the owner to approve or reject (CLAUDE.md, "Lore approval"). When unsure, treat it as new canon.

Before anything else, run `git merge master` so you're working from the latest state. Then check `docs/lore-requests.md` for open requests.

Commit your work on the `lore` branch when done, and summarize what you changed and what still needs the project owner's decision.

Task: $ARGUMENTS
