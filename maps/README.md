# Obsidian world navigation

Open [[maps/Elsewhere Map.canvas|Elsewhere Map]]. Each compact room box has a title that opens a generated navigation note, plus a **Room file** link to the original authored content. The navigation note lists clickable exits, NPCs, ambient NPCs, and objects. Exit links open other navigation notes, so you can walk through the neighborhood without returning to the Canvas.

## Refresh from game files

From the project directory, run:

```powershell
.\.venv\Scripts\python.exe ops\generate_obsidian.py
```

Refresh after changing builder definitions, entity placements, or ambient approval status. This is a manual refresh; it does not watch files in the background. No running server or model is required.

## Sources and boundaries

- Room names and exits: `prospect/world/build_rooms.py` (`ROOMS`, `HUB`, `SPOKES`).
- Talk-capable NPC names and placements: `prospect/world/build_npcs.py` (`NPCS`).
- Ambient entities: the explicit lists in `prospect/world/build_ambient.py`, with names, rooms, and approval read from their content files. Only listed, approved entities appear; unused drafts do not become map objects.
- The generator reads literal assignments without importing or executing game builders. If these definitions stop being literal data or the topology changes beyond the current hub-and-spoke builder, update the generator to match.

This represents the builders' intended layout, **not the running database**. In-game edits, moved NPCs, or older exits left by an earlier build are not reflected. This reference does not establish new setting canon.

## Generated and editable files

- `maps/rooms/*.md`: generated navigation only. Edit the original game/content files to change source data; regenerating replaces these notes. Obsolete generator-owned room notes are removed.
- `maps/Elsewhere Map.canvas`: generated room boxes and connections. You may rearrange or resize the boxes; regeneration preserves positions, sizes, colors, and connection attachment sides for matching IDs. Text, connections, and extra cards are rebuilt, so keep personal annotations in separate notes or a separate Canvas.
- `maps/README.md`: this manually maintained guide.

The generator writes only under `maps/`. It never modifies authored content, builder code, NPC prompts, or the game database. Unknown hand-authored notes in `maps/rooms/` are preserved; a name collision stops generation before writing.

The navigation notes also provide room-to-room links for Obsidian's Graph view. Filter the graph with `path:maps/rooms` for the room navigation layer.
