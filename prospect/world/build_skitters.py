"""
Quest 3 ("Unwelcome Guests" - docs/playtest-quest3-skitters-design.md):
initial skitter population. Idempotent by construction -
world.skitters.ensure_population() only ever spawns up to the
configured count, never duplicates existing ones.

Run with:
    evennia shell -c "from world.build_skitters import build; build()"
"""

from world.skitters import ensure_population


def build():
    ensure_population()
    print("Skitter population ensured.")
