-- Prospect mapper for Mudlet.
-- Builds the map from the game's GMCP Room.Info (docs/gmcp.md): rooms are
-- keyed on `num`, placed at the server's `coords`, and linked by `exits`.
-- Adapted from Blizzard's generic GMCP mapping script (https://worldofpa.in).
--
-- Setup:
--   1. Settings > General > tick "Enable GMCP".
--   2. Paste this into a new script in the Scripts editor and save.
--   3. If Package Manager lists generic_mapper, uninstall it; it maps from
--      room text and fights with this script.
--   4. Reconnect, log in, and open the map with the Map toolbar button.
-- Double-click a room on the map to walk there.

prospect_map = prospect_map or {}
local M = prospect_map

-- Room.Info exit keys that Mudlet draws as normal exits. Anything else
-- becomes a special exit whose command is the exit's name.
local STANDARD = {
    n = true, ne = true, nw = true, e = true, w = true,
    s = true, se = true, sw = true, u = true, d = true,
    ["in"] = true, out = true,
}

-- Fallback placement for rooms the server sends without coords.
local VECTORS = {
    n = {0, 1, 0}, s = {0, -1, 0}, e = {1, 0, 0}, w = {-1, 0, 0},
    ne = {1, 1, 0}, nw = {-1, 1, 0}, se = {1, -1, 0}, sw = {-1, -1, 0},
    u = {0, 0, 1}, d = {0, 0, -1},
}

local function area_id(name)
    if name == nil or name == "" then name = "Prospect" end
    local areas = getAreaTable()
    return areas[name] or addAreaName(name)
end

-- Places a room with no server coords one step from the room we came from.
local function guess_coords(prev)
    if not prev or not roomExists(prev.num) then return 0, 0, 0 end
    local x, y, z = getRoomCoordinates(prev.num)
    for dir, dest in pairs(prev.exits or {}) do
        if tonumber(dest) == M.current and VECTORS[dir] then
            local v = VECTORS[dir]
            return x + v[1], y + v[2], z + v[3]
        end
    end
    return x, y, z
end

-- Links a room's stored exits to every destination already on the map,
-- and leaves a stub for the ones not yet visited.
local function apply_exits(id)
    local raw = getRoomUserData(id, "prospect_exits")
    if raw == nil or raw == "" then return end
    local exits = yajl.to_value(raw)
    for dir, dest in pairs(exits) do
        dest = tonumber(dest)
        if roomExists(dest) then
            if STANDARD[dir] then
                setExitStub(id, dir, false)
                setExit(id, dest, dir)
            else
                addSpecialExit(id, dest, dir)
            end
        elseif STANDARD[dir] then
            setExitStub(id, dir, true)
        end
    end
end

function M.on_room_info()
    local info = gmcp.Room.Info
    local id = tonumber(info.num)
    if not id then return end
    local prev = M.prev_info
    M.current = id

    if not roomExists(id) then
        addRoom(id)
    end
    setRoomName(id, info.name)
    setRoomArea(id, area_id(info.area))
    local c = info.coords
    if c then
        setRoomCoordinates(id, c.x, c.y, c.z)
    elseif not M.placed or not M.placed[id] then
        setRoomCoordinates(id, guess_coords(prev))
    end
    M.placed = M.placed or {}
    M.placed[id] = true

    setRoomUserData(id, "prospect_exits", yajl.to_string(info.exits or {}))
    apply_exits(id)
    -- Neighbours visited earlier now have this room to link to.
    for _, dest in pairs(info.exits or {}) do
        dest = tonumber(dest)
        if dest and roomExists(dest) then apply_exits(dest) end
    end

    M.prev_info = {num = id, exits = info.exits}
    centerview(id)
    updateMap()
end

-- Mudlet calls this when you double-click a room on the map.
function doSpeedWalk()
    for _, dir in ipairs(speedWalkDir) do
        send(dir, false)
    end
end

if M.handler then killAnonymousEventHandler(M.handler) end
M.handler = registerAnonymousEventHandler("gmcp.Room.Info", "prospect_map.on_room_info")
