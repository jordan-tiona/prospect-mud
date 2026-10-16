"""
Periodic idle-time detection (game-plan.md 6.2's structured-logging
item): typeclasses/scripts.py's IdleMonitor (a GLOBAL_SCRIPTS ticker,
see settings.py) calls `check_idle_sessions` on an interval, logging
an `idle` gameplay event the first time a session crosses
IDLE_THRESHOLD_SECONDS - not on every tick while it stays idle, which
would otherwise spam one event per tick for as long as someone stays
AFK, and logging again only after they've been active and then gone
idle a second time.
"""

from evennia import SESSION_HANDLER

from world.session_log import log_idle, session_id_for

IDLE_THRESHOLD_SECONDS = 600  # 10 minutes


def check_idle_sessions() -> None:
    for session in SESSION_HANDLER.get_sessions():
        account = getattr(session, "account", None)
        puppet = getattr(session, "puppet", None)
        if account is None or puppet is None:
            continue

        idle = account.idle_time
        if idle is None or idle < IDLE_THRESHOLD_SECONDS:
            session.ndb.idle_logged = False
            continue
        if session.ndb.idle_logged:
            continue

        session_id = session_id_for(puppet)
        if session_id:
            log_idle(
                session_id=session_id,
                actor_key=puppet.key,
                actor_dbref=puppet.dbref,
                location=puppet.location.key if puppet.location else "",
                idle_seconds=idle,
            )
        session.ndb.idle_logged = True
