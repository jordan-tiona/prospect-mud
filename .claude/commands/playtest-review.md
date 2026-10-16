---
description: Run one playtest-review pass over the logs
---

You are the **Playtest review lane** for this project. This is one review pass, not an ongoing session. You report; you never fix anything.

Run this from the main checkout (`D:\Projects\prospect-mud`), not a worktree: the logs below are gitignored, so they only exist where the server runs. You're on `master` there already, so there's no merge step. The only file you edit is `docs/playtest-findings.md` (plus `docs/lore-requests.md` if a finding needs lore); commit just those.

Follow `docs/game-plan.md` Section 5. Read only log entries since the checkpoint given below, from:
- `prospect/server/logs/sessions.jsonl` (commands, unknown commands, room changes, quest events, idle time, `bug`/`feedback` reports)
- `prospect/server/logs/conversations.jsonl` (NPC turns, with usage, cost and latency)

Look for bugs, pain points, NPC/canon issues, cost/latency outliers, and explicit player feedback. Record each distinct issue in `docs/playtest-findings.md` using its format: update an existing entry's count if it's a repeat, rather than adding a duplicate. If a finding needs lore, add an `LR-REVIEW-####` entry to `docs/lore-requests.md`.

End with a short summary, and the timestamp of the last log entry you read, to use as the next pass's checkpoint.

Checkpoint and notes: $ARGUMENTS
