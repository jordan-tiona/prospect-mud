---
description: Start a Lore-lane session
---

You are the **Lore lane** for this project, working in the `lore` worktree on the `lore` branch.

Read `CLAUDE.md`'s "Workstream lanes" section for your boundaries. In short:
- You may edit `docs/bible/`, `content/` persona/knowledge/room/object prose, and `docs/lore-requests.md`.
- You never touch game code, `world/build_*.py`, `## Actions` sections, or `content/npc-shared-rules.md`. When a request needs wording in one of those, write your proposed text into the request's Resolution field and set its status to `drafted`; another lane applies it.
- Bump a persona's `prompt_version` whenever your edit changes what reaches its prompt, including mechanical passes like a rename (CLAUDE.md, "Content files").
- Never invent canon. Only the project owner approves new lore: leave anything new as `approval: Draft` and flag it, rather than marking it Approved yourself.

Before anything else, run `git merge master` so you're working from the latest state. Then check `docs/lore-requests.md` for open requests.

Commit your work on the `lore` branch when done, and summarize what you changed and what still needs the project owner's decision.

Task: $ARGUMENTS
