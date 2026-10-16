# Obsidian world navigation

Open [[maps/Elsewhere Map.canvas|Elsewhere Map]]. Each compact room box has a title that opens a generated navigation note, plus a **Room file** link to the original authored content. The navigation note lists clickable exits, NPCs, ambient NPCs, and objects. Exit links open other navigation notes, so you can walk through the neighborhood without returning to the Canvas.

## Refresh from game files

From the project directory, run:

```powershell
.\.venv\Scripts\python.exe ops\generate_obsidian.py
```

Refresh after changing the sector file, entity placements, or ambient approval status. This is a manual refresh; it does not watch files in the background. No running server or model is required.

## Sources and boundaries

- Rooms, titles, exits and placements: the MUD editor's sector file, `sectors/elsewhere/sector.json` (see `docs/mud-editor-sector-format.md`). New rooms start at the editor's map position; boxes already on the Canvas keep yours.
- Names come from each entity's content file heading. Ambient NPCs and objects appear only when their content is Approved; talk-capable NPCs always appear. Quest props and other objects aren't shown.
- The generator reads the sector file without importing or running game code.

This represents the sector file's layout, **not the running database**. In-game edits, or anything not yet rebuilt from an export, isn't reflected. This reference does not establish new setting canon. Obsidian is being retired once the MUD editor's viewer exists.

## Generated and editable files

- `maps/rooms/*.md`: generated navigation only. Edit the original game/content files to change source data; regenerating replaces these notes. Obsolete generator-owned room notes are removed.
- `maps/Elsewhere Map.canvas`: generated room boxes and connections. You may rearrange or resize the boxes; regeneration preserves positions, sizes, colors, and connection attachment sides for matching IDs. Text, connections, and extra cards are rebuilt, so keep personal annotations in separate notes or a separate Canvas.
- `maps/README.md`: this manually maintained guide.

The generator writes only under `maps/`. It never modifies authored content, the sector file, NPC prompts, or the game database. Unknown hand-authored notes in `maps/rooms/` are preserved; a name collision stops generation before writing.

The navigation notes also provide room-to-room links for Obsidian's Graph view. Filter the graph with `path:maps/rooms` for the room navigation layer.
