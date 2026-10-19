---
description: Start a Dev-lane session
---

You are the **Dev lane** for this project, working in the main checkout (`D:\Projects\prospect-mud`) on `master`. You're the only lane that runs the Evennia server; stop it before running any shell script that writes to the database.

Read `CLAUDE.md`'s "Workstream lanes" section for your boundaries. In short:
- You may edit game code, tests, persona `## Actions` sections, `content/npc-shared-rules.md`, and `content/actions/`.
- You never write or invent lore (hard rule 7). If you need lore you don't have, add an `LR-DEV-####` entry to `docs/lore-requests.md` and use a clearly marked placeholder meanwhile.
- Before editing an `## Actions` section, check `docs/npc-action-prompt-guidelines.md`. Before adding a generic action, a per-player visibility mechanic, or an admin reset command, check `docs/engineering-pitfalls.md`.

Also check `docs/lore-requests.md` for entries whose `Handoff` line names `dev`, whatever their Status - those are yours to apply. When you finish, remove your part from the Handoff line (`none` if nothing is left) and record the commit in Status.

Propose a plan before anything beyond a small change, and run the test suite before committing.

Task: $ARGUMENTS
