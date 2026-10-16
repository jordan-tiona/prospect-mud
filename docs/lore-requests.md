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

## LR-0001: Remove Iri Vael's dual-room note
- Requested by: tools
- Needed for: MUD Editor sector format (`docs/mud-editor-sector-format.md` Section 9). Each entity is built in exactly one room, and content-file `room:` metadata no longer drives placement.
- What's needed: Drop "(may also appear in the Residential Courtyard)" from `content/npcs/iri_vael.md`'s `room:` metadata and from any persona prose that implies she's sometimes elsewhere. Project owner has already decided she's in the Civic Office only.
- Blocking: no
- Status: open
- Resolution:
