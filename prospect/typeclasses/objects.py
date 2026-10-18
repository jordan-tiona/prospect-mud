"""
Object

The Object is the class for general items in the game world.

Use the ObjectParent class to implement common features for *all* entities
with a location in the game world (like Characters, Rooms, Exits).

"""

import re

from evennia.objects.objects import DefaultObject
from evennia.utils.utils import inherits_from

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
PARAGRAPH_INDENT = "    "  # four spaces - project owner's call


def indent_paragraphs(text):
    """Indent every paragraph (including the first) by four spaces.

    Evennia's own output formatting (format_appearance's
    compress_whitespace) collapses a blank line between paragraphs
    down to a single line break, so a multi-paragraph desc/look text
    would otherwise run together with no visual break at all. The
    project owner's call: mark every paragraph with a four-space
    indent instead of a blank line.
    """
    if not text:
        return text
    paragraphs = _PARAGRAPH_SPLIT_RE.split(text.strip())
    return "\n".join(PARAGRAPH_INDENT + p for p in paragraphs)


class ObjectParent:
    """
    This is a mixin that can be used to override *all* entities inheriting at
    some distance from DefaultObject (Objects, Exits, Characters and Rooms).

    Just add any method that exists on `DefaultObject` to this class. If one
    of the derived classes has itself defined that same hook already, that will
    take precedence.

    """

    def format_appearance(self, appearance, looker, **kwargs):
        # DefaultObject.format_appearance strips its block down to no
        # leading blank line, so looking at anything (a room, an NPC,
        # an object) runs right up against whatever the client printed
        # before it. Project owner's call: a blank line ahead of every
        # look/examine output so it reads as its own block.
        return "\n" + super().format_appearance(appearance, looker, **kwargs)

    def get_display_desc(self, looker, **kwargs):
        # typeclasses.rooms.Room overrides this itself (for the
        # glance/full-description split) and calls indent_paragraphs
        # directly - this covers every other entity (objects, NPCs,
        # characters) uniformly.
        #
        # `probe=True` (commands/probe.py) shows db.probe_desc, the longer
        # authored text, when there is one; otherwise the same text as
        # `look`. Subclasses with their own per-looker text (the pest
        # log, the civic display, the signpost, the planting bed) don't
        # call this, so `probe` shows their `look` text.
        if kwargs.get("probe") and self.db.probe_desc:
            return indent_paragraphs(self.db.probe_desc)
        return indent_paragraphs(super().get_display_desc(looker, **kwargs))


class RoomObject(ObjectParent, DefaultObject):
    """
    A static, inspectable room fixture - a sign, a corpse, a mark on
    the wall. Not a background character (see typeclasses.npcs.NPC)
    and not meant to be picked up.

    `db.room_line` is the one-liner the room itself shows automatically
    as part of its description (see typeclasses.rooms.Room), e.g. "A
    symbol is gouged into the wall." `db.desc` is the longer text shown
    on `look <object>`, same as any object; if `room_line` is left
    unset, the room falls back to using `desc` for both.

    Scenery that doesn't need its own interactive presence - and
    nothing a player might reasonably want to inspect, per the
    project owner's distinction - stays as plain prose in the room's
    own `desc` instead of becoming one of these.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false()")


class RevisionDisplayObject(RoomObject):
    """
    Phase 2D's civic information display (docs/phase2-quest-
    prototype-design.md §14, docs/phase2d-noticeboard-check-proposal.md):
    looks the same to everyone except the four-digit revision number,
    which is this specific looker's own stored value
    (world.noticeboard.get_or_create_expected_revision) - generated
    the first time *they* examine it, not one shared fact everyone
    sees alike. The first typeclass in this project where `look
    <object>` genuinely varies by who's looking, rather than every
    looker getting the same static db.desc.

    Always visible to everyone (ordinary office furniture, not gated
    behind commitment state like typeclasses.objects.CommitmentHintObject) -
    only its *content* is per-player, not its presence.
    """

    def get_display_desc(self, looker, **kwargs):
        from world.noticeboard import get_or_create_expected_revision

        if not hasattr(looker, "attributes"):
            # Defensive: something without real per-player state (not
            # expected in practice) - fall back to the plain db.desc
            # rather than guessing at a revision for it.
            return super().get_display_desc(looker, **kwargs)

        revision = get_or_create_expected_revision(looker)
        text = (
            "A small civic information display cycles through local notices "
            "and public-service announcements. A four-digit revision "
            f"identifier appears beneath the notices: {revision}."
        )
        return indent_paragraphs(text)


class SkitterLedgerObject(RoomObject):
    """
    The Civic Office's skitter log (project owner, 2026-10-16): the
    post-quest loop's visible scoreboard. Same per-looker pattern as
    RevisionDisplayObject - always visible to everyone, but `look`/`read`
    shows each player their own logged total
    (world.skitters.banked_kills_for), which only goes up when Iri logs
    a report. `db.desc` is the static part; the count line is appended.
    """

    def get_display_desc(self, looker, **kwargs):
        from world.skitters import banked_kills_for

        base = self.db.desc or ""
        if not hasattr(looker, "attributes"):
            return indent_paragraphs(base)
        count = banked_kills_for(looker)
        if count:
            plural = "" if count == 1 else "s"
            line = f"Under your name: {count} skitter{plural} logged."
        else:
            line = "There's nothing logged under your name yet."
        return indent_paragraphs(f"{base}\n\n{line}" if base else line)


class SignpostObject(RoomObject):
    """
    Old Quarter Square's signpost (docs/prospect-initial-playtest-
    design-spec.md 4, docs/prospect-playtest-new-characters-and-
    rooms.md 4): always visible to everyone, same as `RevisionDisplayObject`,
    but unlike that class its content isn't per-looker - it's computed
    once from the real room graph so it can never drift from the
    actual map.

    The route to Daven's office is computed via the same BFS
    (world.actions._find_exit_path) that the `give_directions` NPC
    action already uses, not hand-authored text. `db.spoke_lines` is
    the one hand-authored part: plain "<direction>: <existing room
    name>" flavor for the square's other spokes, set by the builder.
    """

    def get_display_desc(self, looker, **kwargs):
        from evennia import search_tag

        from world.actions import _find_exit_path
        from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY

        lines = ["A simple signpost lists the streets leading off the square."]

        matches = search_tag(key="daven_office", category=ROOM_TAG_CATEGORY)
        target_room = matches[0] if matches else None
        if target_room is not None and self.location is not None:
            path = _find_exit_path(self.location, target_room)
            if path:
                route_text = ", then ".join(path)
                lines.append(f"Daven's office: {route_text}.")

        lines.extend(self.db.spoke_lines or [])
        return indent_paragraphs("\n\n".join(lines))


class CommitmentHintObject(RoomObject):
    """
    A RoomObject whose entire purpose is per-player narrative hiding
    (world/build_quest_props.py, server/conf/lockfuncs.py's
    commitment_hint_visible) - once a player has engaged with the
    commitment it hints at, it should quietly stop existing for them.

    Evennia's `view`/`search` locks default to letting a superuser
    bypass them entirely (access()'s own `no_superuser_bypass=False`
    default) - exactly wrong for a solo project where the project
    owner's own account *is* the superuser doing the actual
    playtesting (confirmed live, 2026-10-13: the lock function itself
    correctly returned False, but the object still showed up and
    was still `look`-able regardless). Forces no_superuser_bypass for
    view/search specifically, so the mechanic actually works for the
    one account that needs to see it work; everything else (a
    builder's examine/edit/delete permissions) is untouched.
    """

    def access(self, accessing_obj, access_type="read", default=False, no_superuser_bypass=False, **kwargs):
        if access_type in ("view", "search"):
            no_superuser_bypass = True
        return super().access(
            accessing_obj, access_type=access_type, default=default, no_superuser_bypass=no_superuser_bypass, **kwargs
        )


class Parcel(ObjectParent, DefaultObject):
    """
    A single player's quest item for the phase 2C misdelivered-parcel
    scenario (docs/phase2c-misdelivered-parcel-proposal.md). Its
    `location` is the real, engine-checkable possession fact the
    scenario's handoff actions validate against - but per that
    proposal's §4/§10, the *only* thing allowed to move it is the
    validated NPC action tied to a scenario commitment, never a
    player's own `get`/`give`/`drop`. Locking those out here, on the
    object, means the handoff actions never have to reconcile "did
    this move through the quest, or did a stock command do it
    instead" - there is only one path.

    `get:false()` works the same way as `RoomObject`'s (CmdGet checks
    `access(getter, "get")` directly). Drop/give need more: Evennia's
    default `at_pre_drop` does honor a lock, but `at_pre_give` does
    not consult locks at all (ignores any `give:false()` lock string),
    so both are overridden here to unconditionally refuse - confirmed
    against evennia.objects.objects.DefaultObject's hook source, not
    assumed from the lock string alone.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false();drop:false()")

    def at_pre_give(self, giver, getter, **kwargs):
        # One exception (owner, 2026-10-17): handing the parcel to the
        # NPC it's for. That runs the same engine validator as the
        # NPC's own accept_handoff tool call - same role, open-
        # commitment and possession checks, same parcel move - so a
        # player's `give` and the conversational handoff can't
        # disagree. The stock give is always cancelled; on success
        # the validator has already moved the parcel.
        if inherits_from(getter, "typeclasses.npcs.TalkativeNPC"):
            from world.actions import PARCEL_COMMITMENT_TYPES, PARCEL_TAG_CATEGORY, validate_and_apply
            from world.emotes import format_narration

            if self.location == giver and self.tags.get(category=PARCEL_TAG_CATEGORY):
                for commitment_type in sorted(PARCEL_COMMITMENT_TYPES):
                    result = validate_and_apply(getter, giver, "accept_handoff", {"commitment_type": commitment_type})
                    if result.applied:
                        # Second person ("...from you."), so the giver's
                        # alone, like commands/say.py's narration.
                        giver.msg(format_narration(getter.key, result.narration))
                        return False
            giver.msg(f"{getter.get_display_name(giver)} isn't expecting {self.get_display_name(giver)}.")
            return False
        giver.msg(f"{self.get_display_name(giver)} isn't yours to give away.")
        return False


class GardeningKit(ObjectParent, DefaultObject):
    """
    Quest 2's communal tool (docs/prospect-initial-playtest-design-
    spec.md §6: "not locked behind a code or puzzle"). Unlike Parcel,
    this is a perfectly ordinary gettable/droppable item - no lock
    overrides at all. commands/use.py checks the actor is actually
    holding one of these (by typeclass) before letting them tend the
    planting bed; nothing about possession needs to be exclusive or
    consumed, since the completion fact tracked is per-player
    (world/garden.py), not tied to the kit itself.
    """


class PlantingBed(RoomObject):
    """
    Quest 2's "use kit on bed" target in Old Quarter Square - the one
    justified interactable object the design spec asks for (§6,
    Quest 2), folding what was previously just room-description prose
    ("low planting beds") into something commands/use.py can actually
    target. Not pickable, same as any other RoomObject.

    `look <bed>` reflects whether *this specific looker* has tended it
    (world/garden.py's is_bed_tended) - same per-looker pattern as
    RevisionDisplayObject above, and for the same reason: this is a
    per-player quest fact, not shared-world state, so one player
    finishing the bed must not change what a second player sees.
    `db.desc` (set by world/build_garden_props.py) is only the
    not-yet-tended text; the tended text is authored here since it
    isn't data the builder tracks.
    """

    def get_display_desc(self, looker, **kwargs):
        from world.garden import is_bed_tended

        if hasattr(looker, "attributes") and is_bed_tended(looker):
            return indent_paragraphs(
                "The square's planting bed, soil freshly turned and weeded - you tended to it yourself."
            )
        return super().get_display_desc(looker, **kwargs)


class Weapon(ObjectParent, DefaultObject):
    """
    Quest 3's ("Unwelcome Guests") starter weapon - handed to the
    player by accept_commitment's engine-side effect for the
    "hunt_skitters" commitment (world/actions.py's
    _create_weapon_for), same shape as Quest 1's accept_commitment
    creating a Parcel. Can't be given away or dropped (owner,
    2026-10-17): handing it to a friend would let them hunt skitters
    without ever taking Tarin's quest. Enforced in the hooks rather
    than a lock string, so batons already handed out are covered too.

    `db.damage` is the only mechanical property commands/attack.py
    reads, kept on the instance rather than hardcoded in the command
    so a future different weapon type could vary it without touching
    command code.
    """

    def at_pre_give(self, giver, getter, **kwargs):
        giver.msg(f"{self.get_display_name(giver)} isn't yours to give away.")
        return False

    def at_pre_drop(self, dropper, **kwargs):
        dropper.msg(f"You can't drop {self.get_display_name(dropper)}.")
        return False


class Object(ObjectParent, DefaultObject):
    """
    This is the root Object typeclass, representing all entities that
    have an actual presence in-game. DefaultObjects generally have a
    location. They can also be manipulated and looked at. Game
    entities you define should inherit from DefaultObject at some distance.

    It is recommended to create children of this class using the
    `evennia.create_object()` function rather than to initialize the class
    directly - this will both set things up and efficiently save the object
    without `obj.save()` having to be called explicitly.

    Note: Check the autodocs for complete class members, this may not always
    be up-to date.

    * Base properties defined/available on all Objects

     key (string) - name of object
     name (string)- same as key
     dbref (int, read-only) - unique #id-number. Also "id" can be used.
     date_created (string) - time stamp of object creation

     account (Account) - controlling account (if any, only set together with
                       sessid below)
     sessid (int, read-only) - session id (if any, only set together with
                       account above). Use `sessions` handler to get the
                       Sessions directly.
     location (Object) - current location. Is None if this is a room
     home (Object) - safety start-location
     has_account (bool, read-only)- will only return *connected* accounts
     contents (list, read only) - returns all objects inside this object
     exits (list of Objects, read-only) - returns all exits from this
                       object, if any
     destination (Object) - only set if this object is an exit.
     is_superuser (bool, read-only) - True/False if this user is a superuser
     is_connected (bool, read-only) - True if this object is associated with
                            an Account with any connected sessions.
     has_account (bool, read-only) - True is this object has an associated account.
     is_superuser (bool, read-only): True if this object has an account and that
                        account is a superuser.

    * Handlers available

     aliases - alias-handler: use aliases.add/remove/get() to use.
     permissions - permission-handler: use permissions.add/remove() to
                   add/remove new perms.
     locks - lock-handler: use locks.add() to add new lock strings
     scripts - script-handler. Add new scripts to object with scripts.add()
     cmdset - cmdset-handler. Use cmdset.add() to add new cmdsets to object
     nicks - nick-handler. New nicks with nicks.add().
     sessions - sessions-handler. Get Sessions connected to this
                object with sessions.get()
     attributes - attribute-handler. Use attributes.add/remove/get.
     db - attribute-handler: Shortcut for attribute-handler. Store/retrieve
            database attributes using self.db.myattr=val, val=self.db.myattr
     ndb - non-persistent attribute handler: same as db but does not create
            a database entry when storing data

    * Helper methods (see src.objects.objects.py for full headers)

     get_search_query_replacement(searchdata, **kwargs)
     get_search_direct_match(searchdata, **kwargs)
     get_search_candidates(searchdata, **kwargs)
     get_search_result(searchdata, attribute_name=None, typeclass=None,
                       candidates=None, exact=False, use_dbref=None, tags=None, **kwargs)
     get_stacked_result(results, **kwargs)
     handle_search_results(searchdata, results, **kwargs)
     search(searchdata, global_search=False, use_nicks=True, typeclass=None,
            location=None, attribute_name=None, quiet=False, exact=False,
            candidates=None, use_locks=True, nofound_string=None,
            multimatch_string=None, use_dbref=None, tags=None, stacked=0)
     search_account(searchdata, quiet=False)
     execute_cmd(raw_string, session=None, **kwargs))
     msg(text=None, from_obj=None, session=None, options=None, **kwargs)
     for_contents(func, exclude=None, **kwargs)
     msg_contents(message, exclude=None, from_obj=None, mapping=None,
                  raise_funcparse_errors=False, **kwargs)
     move_to(destination, quiet=False, emit_to_obj=None, use_destination=True)
     clear_contents()
     create(key, account, caller, method, **kwargs)
     copy(new_key=None)
     at_object_post_copy(new_obj, **kwargs)
     delete()
     is_typeclass(typeclass, exact=False)
     swap_typeclass(new_typeclass, clean_attributes=False, no_default=True)
     access(accessing_obj, access_type='read', default=False,
            no_superuser_bypass=False, **kwargs)
     filter_visible(obj_list, looker, **kwargs)
     get_default_lockstring()
     get_cmdsets(caller, current, **kwargs)
     check_permstring(permstring)
     get_cmdset_providers()
     get_display_name(looker=None, **kwargs)
     get_extra_display_name_info(looker=None, **kwargs)
     get_numbered_name(count, looker, **kwargs)
     get_display_header(looker, **kwargs)
     get_display_desc(looker, **kwargs)
     get_display_exits(looker, **kwargs)
     get_display_characters(looker, **kwargs)
     get_display_things(looker, **kwargs)
     get_display_footer(looker, **kwargs)
     format_appearance(appearance, looker, **kwargs)
     return_apperance(looker, **kwargs)

    * Hooks (these are class methods, so args should start with self):

     basetype_setup()     - only called once, used for behind-the-scenes
                            setup. Normally not modified.
     basetype_posthook_setup() - customization in basetype, after the object
                            has been created; Normally not modified.

     at_object_creation() - only called once, when object is first created.
                            Object customizations go here.
     at_object_delete() - called just before deleting an object. If returning
                            False, deletion is aborted. Note that all objects
                            inside a deleted object are automatically moved
                            to their <home>, they don't need to be removed here.

     at_init()            - called whenever typeclass is cached from memory,
                            at least once every server restart/reload
     at_first_save()
     at_cmdset_get(**kwargs) - this is called just before the command handler
                            requests a cmdset from this object. The kwargs are
                            not normally used unless the cmdset is created
                            dynamically (see e.g. Exits).
     at_pre_puppet(account)- (account-controlled objects only) called just
                            before puppeting
     at_post_puppet()     - (account-controlled objects only) called just
                            after completing connection account<->object
     at_pre_unpuppet()    - (account-controlled objects only) called just
                            before un-puppeting
     at_post_unpuppet(account) - (account-controlled objects only) called just
                            after disconnecting account<->object link
     at_server_reload()   - called before server is reloaded
     at_server_shutdown() - called just before server is fully shut down

     at_access(result, accessing_obj, access_type) - called with the result
                            of a lock access check on this object. Return value
                            does not affect check result.

     at_pre_move(destination)             - called just before moving object
                        to the destination. If returns False, move is cancelled.
     announce_move_from(destination)         - called in old location, just
                        before move, if obj.move_to() has quiet=False
     announce_move_to(source_location)       - called in new location, just
                        after move, if obj.move_to() has quiet=False
     at_post_move(source_location)          - always called after a move has
                        been successfully performed.
     at_pre_object_leave(leaving_object, destination, **kwargs)
     at_object_leave(obj, target_location, move_type="move", **kwargs)
     at_object_leave(obj, target_location)   - called when an object leaves
                        this object in any fashion
     at_pre_object_receive(obj, source_location)
     at_object_receive(obj, source_location, move_type="move", **kwargs) - called when this object receives
                        another object
     at_post_move(source_location, move_type="move", **kwargs)

     at_traverse(traversing_object, target_location, **kwargs) - (exit-objects only)
                              handles all moving across the exit, including
                              calling the other exit hooks. Use super() to retain
                              the default functionality.
     at_post_traverse(traversing_object, source_location) - (exit-objects only)
                              called just after a traversal has happened.
     at_failed_traverse(traversing_object)      - (exit-objects only) called if
                       traversal fails and property err_traverse is not defined.

     at_msg_receive(self, msg, from_obj=None, **kwargs) - called when a message
                             (via self.msg()) is sent to this obj.
                             If returns false, aborts send.
     at_msg_send(self, msg, to_obj=None, **kwargs) - called when this objects
                             sends a message to someone via self.msg().

     return_appearance(looker) - describes this object. Used by "look"
                                 command by default
     at_desc(looker=None)      - called by 'look' whenever the
                                 appearance is requested.
     at_pre_get(getter, **kwargs)
     at_get(getter)            - called after object has been picked up.
                                 Does not stop pickup.
     at_pre_give(giver, getter, **kwargs)
     at_give(giver, getter, **kwargs)
     at_pre_drop(dropper, **kwargs)
     at_drop(dropper, **kwargs)          - called when this object has been dropped.
     at_pre_say(speaker, message, **kwargs)
     at_say(message, msg_self=None, msg_location=None, receivers=None, msg_receivers=None, **kwargs)

     at_look(target, **kwargs)
     at_desc(looker=None)

    """

    pass
