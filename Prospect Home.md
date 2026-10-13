# Prospect Home

Start with [[maps/Elsewhere Map.canvas|Elsewhere Map]] for the prototype neighborhood. Room titles open generated navigation notes with clickable exits, NPCs, and objects. Each note includes a link to the original authored room file.

Start exploring from [[maps/rooms/old_quarter_square|Old Quarter Square]]. See the [[maps/README|map guide]] for sources, limitations, and the refresh command.

## Project references

- [[docs/prospect-constellation-design-v0.4.1|Design bible]] — authoritative setting and engineering reference.
- [[docs/phase2-quest-prototype-design|Phase 2 quest prototype design]]
- [[content/common-knowledge|Common knowledge]]
- [[content/npc-shared-rules|Shared NPC rules]]

## Using this vault

Open **Elsewhere Map** in the file list for the spatial map. Dragging a card only rearranges the illustration; it does not change game exits or NPC placement. Regeneration preserves room positions and sizes.

The generated notes under `maps/rooms/` link to one another through their exits, so Obsidian's Graph view can show room-to-room connections too.

When the source data changes, run the generator described in the map guide. Authored content stays in `content/`; all generated navigation stays in `maps/`. The map reflects builder definitions, not live database state.
