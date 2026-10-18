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

## Map coordinates (Tools follow-up)

`Room.Info` sends `coords` only when a room has `db.map_coords`, and today none do. The editor's `editor.x`/`editor.y` values are canvas pixels on an uneven spacing, and export strips them. Turning them into grid coordinates needs a sector-format change, so it's Tools' work:

1. Add an exported per-room `map` field (`{"x", "y", "z"}`, integers) to `sector.json` and the manifest, editable in the editor.
2. Have `world/build_sector.py` write it to the room as `db.map_coords`.
3. Make `ops/editor/check.py` report two rooms in a sector with the same coordinates. A warning is enough, because mapper clients cope with stretched exits but not with stacked rooms.

**Elsewhere doesn't fit a plain one-step grid today.** With the square at (0,0,0), the Civic Office is west at (-1,0). Old Quarter Street is southwest at (-1,-1), and Daven's Office is north of the street, which puts it at (-1,0) too. The editor already draws Daven's Office further west (x -960, against the Civic Office's -560). Map coordinates can stretch an exit across several grid steps, so a layout such as Daven's Office at (-2,0) works. Choosing the layout is the owner's call in the editor.
