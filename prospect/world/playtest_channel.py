"""
The playtest channel (owner, 2026-10-17, borrowed from Achaea): one
out-of-character channel shared by testers and staff, on by default,
which a player can leave with `playtest off` for some peace and quiet
(commands/playtest.py).

Every account is subscribed at login unless it has opted out, not only
accounts created after the channel existed - settings.DEFAULT_CHANNELS
alone would only reach new accounts.
"""

from evennia.comms.models import ChannelDB

PLAYTEST_CHANNEL_KEY = "Playtest"
HISTORY_LINES = 20


def get_playtest_channel():
    return ChannelDB.objects.get_channel(PLAYTEST_CHANNEL_KEY)


def ensure_subscribed(account):
    """Subscribe `account` unless it opted out. Returns the channel,
    or None if it doesn't exist (yet)."""
    channel = get_playtest_channel()
    if channel and not account.db.playtest_opted_out and not channel.has_connection(account):
        channel.connect(account)
    return channel
