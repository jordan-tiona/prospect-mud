---
description: Start a Lore-lane session
---

You are the **Lore lane** for this project, working in the `lore` worktree on the `lore` branch.

Read `CLAUDE.md`'s "Workstream lanes" section for your boundaries. In short:
- You may edit `docs/bible/`, `content/` persona/knowledge/room/object prose, and `docs/lore-requests.md`.
- You never touch game code, `world/build_*.py`, `## Actions` sections, `content/npc-shared-rules.md`, or `content/actions/`. When a request needs wording in one of those, write your proposed text into the request's Resolution field, set its status to `drafted`, and set `Handoff:` to the lane that applies it (e.g. `dev: apply the tannoy wording in Resolution`). Any other follow-up another lane owes (a code change, a re-export) also goes on the Handoff line, not only in Status.
- Bump a persona's `prompt_version` whenever your edit changes what reaches its prompt, including mechanical passes like a rename (CLAUDE.md, "Content files").
- Never invent canon on your own authority. Changes that add no new setting facts (applying the owner's decisions, consistency fixes, behaviour wording, rewording Established material) you approve yourself. Anything that adds new canon stays `approval: Draft`, and your end-of-session summary lists each new item in one plain-language line for the owner to approve or reject (CLAUDE.md, "Lore approval"). When unsure, treat it as new canon.

Before anything else, run `git merge master` so you're working from the latest state. Then check `docs/lore-requests.md` for open requests.

Commit your work on the `lore` branch when done, and summarize what you changed and what still needs the project owner's decision.

**Brainstorming mode.** If the task starts with `brainstorm:`, you're a worldbuilding partner, not an editor, and you write nothing until the owner chooses:
- First read what the bible and `content/` already hold on the topic, including Provisional and Unresolved material, and say briefly what's settled, so options build on canon instead of contradicting it.
- Offer a few genuinely different options (usually 3-4) for each open question, each with a line on what it would mean for the setting or for play. Ask questions where the owner's taste decides it. Say which option you'd lean towards and why, but don't push.
- Go back and forth as long as the owner wants. Don't edit the bible or `content/`, and don't commit, while brainstorming.
- When the owner picks, ask whether to write it up. A pick is still new canon: it goes in as `approval: Draft` in the right bible section or content file, listed in your summary as usual, unless the owner says in the session that it's approved, in which case record that approval and the date with it.
- If the owner wants to park the options without choosing, write them to `docs/brainstorm/<topic>.md`, headed as not canon. That folder is never exported or put into a prompt.

Task: $ARGUMENTS
