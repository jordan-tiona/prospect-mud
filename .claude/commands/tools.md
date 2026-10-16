---
description: Start a Tools-lane session
---

You are the **Tools lane** for this project, working in the `tools` worktree on the `tools` branch. Your main project is the MUD editor (`docs/mud-editor-sector-format.md`, `ops/editor/`).

Read `CLAUDE.md`'s "Workstream lanes" section for your boundaries. In short:
- You may edit tool code, `world/build_*.py`, and in-game object/placement code.
- You never change game behavior or mechanics without a Dev-lane review, and never invent lore. If you need lore, add an `LR-TOOLS-####` entry to `docs/lore-requests.md`.
- Don't run the Evennia server; only the Dev lane does.

Before anything else, run `git merge master` so you're working from the latest state.

Commit finished work on the `tools` branch and tell the project owner when it's ready to merge. Leave unfinished work uncommitted.

Task: $ARGUMENTS
