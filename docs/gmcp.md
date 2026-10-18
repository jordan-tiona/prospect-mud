# GMCP packages

**Status:** started 2026-10-18 (Dev lane). This is the list of every GMCP message the game sends, and the contract client scripts can rely on. Code: `prospect/world/gmcp.py`, and every message goes through it.

## Rules

- **GMCP is an extra channel.** Nothing may reach a player only through GMCP. Anything a player needs also appears as normal text, for the same reason as the colour-only rule in `world/accessibility.py`.
- **Use common package names.** Where an IRE/Mudlet package exists (`Char.Vitals`, `Char.Status`, `Room.Info`, `Comm.Channel`, `Char.Items`), use it and its field names, so client scripts written for other games need little change. Invent a package only when none fits.
- **Add packages only for systems that have settled.** Each field is a promise to players' client scripts. Renaming or removing one breaks them. Add new fields freely, but don't change or remove one without noting it here.
- **No model output in GMCP.** If NPC speech ever goes out on `Comm.Channel`, it carries the same engine-checked text the room already shows, never raw generation.
- **Transport is Evennia's.** `session.msg(Room_Info=((), payload))` goes out as GMCP `Room.Info <json>` over telnet (Evennia's `portal/gmcp_utils.py` turns underscores into dots), and as an OOB message to the webclient. Clients that don't negotiate GMCP get nothing. MSSP already advertises GMCP (`server/conf/mssp.py`).

## Packages sent

### `Room.Info`

Sent to the moving character after every move (`Character.at_post_move`, after the arrival glance), and on puppet.

| Field | Type | Meaning |
|---|---|---|
| `num` | int | The room's database id. Stable while the database lives, because the sector build updates rooms in place. Mapper scripts key rooms on this. |
| `id` | str | The sector-file room id (`corner_cafe`), stable across rebuilds. `""` for rooms not built from a sector. |
| `name` | str | The room's title. |
| `area` | str | The sector id (`elsewhere`). `""` if untagged. |
| `environment` | str | `db.room_type`, or `""`. |
| `exits` | object | Direction to destination `num`, for exits the character can see. Compass, up/down use short names (`n`, `ne`, `u`, `d`); `in`, `out` and named exits keep their key. |
| `coords` | object | `{"x", "y", "z"}`, integers, **only when the room has map coordinates**. Omitted otherwise. |

Coordinates are grid units, not pixels: **x grows east, y grows north, z grows up** (Mudlet's convention). They come from the room attribute `db.map_coords = {"x": int, "y": int, "z": int}`, which the sector build is meant to set (see "Map coordinates" below). Malformed values are left out, not sent.

### `Char.Status`

Sent on puppet.

| Field | Type | Meaning |
|---|---|---|
| `name` | str | The character's name. |
| `species` | str | Set by chargen. Omitted until it is. |

## Planned, not built

- **`Char.Vitals`**, once combat has real HP. Send it from the one place HP changes, not from each attack.
- **`Comm.Channel`** (the playtest channel, `tell`), and possibly room speech, for clients that split chat into its own window. Screen-reader users on Mudlet and MUSHclient use this.
- **Not yet:** `Char.Items`, quest/commitment tracking and skills. Those systems are still changing shape.

## Map coordinates

`Room.Info` sends `coords` only when a room has `db.map_coords`. The editor's `editor.x`/`editor.y` values are canvas pixels on an uneven spacing, and export strips them; the grid below is separate.

**Grid policy (owner, 2026-10-18): a one-step grid by default, worked out from the exits, with deliberate exceptions.** Coordinates aren't typed in. They come from the exits, so they can't drift away from them:

- Each sector has one **anchor** room at (0,0,0). From there, each compass exit is one grid step in its direction (`northeast` is +1 x, +1 y), and `up`/`down` are ±1 z.
- **Two rooms on one cell is an error.** Export refuses it, the same way it refuses `duplicate_room_pair`. Stacked rooms are the one thing mapper clients can't draw.
- **A room can be pinned** to an explicit coordinate. Use a pin when the one-step rule doesn't fit: a big space next to a small one, an exit with no direction (`in`, `out`, a named hatch or lift), or a loop that doesn't close. Coordinates are then worked out from the pinned room onward.
- **An exit that doesn't match its direction is a warning:** one that crosses more than one step, points the wrong way, or joins a room that can't be reached from the anchor. Fix the exits, or confirm the exception by pinning the room. Warnings don't block export, so a sector being built can still be exported.
- Treat any change to these rules as a deliberate design decision, the same way the one-connection-per-room-pair rule in `docs/mud-editor-sector-format.md` is.

**Built (Tools, 2026-10-18).** `sector.json` holds a top-level `map_anchor` and an optional `map_pin` per room (`docs/mud-editor-sector-format.md` Section 4). `ops/editor/check.py`'s `map_grid()` works the coordinates out, and check reports `map_overlap` (error), `exit_off_grid`, `off_map` and `no_map_anchor` (warnings). Export writes `map: {x, y, z}` for each placed room, and `world/build_sector.py` sets it as `db.map_coords`. In the editor, each room's panel shows its cell and has **Pin here**, **Unpin** and **Make this the anchor**; the map box shows the cell after the room ID.

**Elsewhere (owner's choice, 2026-10-18).** The anchor is Old Quarter Square. The one overlap, Daven's Office and the Civic Office both on (-1,0), was fixed by making the street to Daven's Office exit `south`/`north` instead of `north`/`south`, which puts the office at (-1,-2). The owner preferred that to a second diagonal. Nothing is pinned. The signpost route and `give_directions` follow the exits, so they now say "southwest, then south".
