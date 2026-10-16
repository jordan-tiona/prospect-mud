# Lore request queue

Any lane that needs lore it doesn't have adds an entry here instead of inventing it (CLAUDE.md hard rule 7). The Lore lane works through the queue; Jordan approves resolutions.

Format (see `docs/game-plan.md` Section 4):

```
## LR-0001: <short title>
- Requested by: dev | tools | tests | playtest-review
- Needed for: <feature, file, or finding>
- What's needed: <specific question or content>
- Blocking: yes | no
- Status: open | drafted | approved | rejected
- Resolution: <bible section or content file, once approved>
```

---

## LR-0001: Civic Office skitter ledger and Iri's pest-log framing
- Requested by: dev
- Needed for: post-quest skitter loop (`world/build_skitter_ledger.py`, `content/npcs/iri_vael.md`'s `## Actions`)
- What's needed: (1) the ledger's room line and `look`/`read` description - currently plain placeholders in `world/build_skitter_ledger.py` (`ROOM_LINE`, `DESC`); the per-player count line is appended by code and isn't part of this. (2) Review the minimal in-world framing in Iri's `## Actions` section: that the office keeps a pest log, that Iri is the one who logs reports, and that she knows Tarin lends out the baton. (3) Whether Tarin should know Iri by name (his `## Actions` now points players to "Iri Vael at the Civic Office").
- Blocking: no
- Status: open
- Resolution:
