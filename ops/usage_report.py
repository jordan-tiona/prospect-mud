"""LLM usage and spend report from the conversation log (read-only).

    python ops/usage_report.py              # last 7 days
    python ops/usage_report.py --days 30
    python ops/usage_report.py --log path/to/conversations.jsonl

Per UTC day: logged turns, active players, total spend, average spend per
turn and per player, average prompt tokens per turn, and the share of
prompt tokens served from the provider's prompt cache. Then the top
spenders over the whole window.

Spend is each turn's `cost_usd` as logged. Turns logged before
2026-10-16's cache-aware pricing have no `cached_tokens` in their usage:
their cost ignores cache discounts (an overestimate) and they're counted
as "cache unknown".
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parents[1] / "prospect" / "server" / "logs" / "conversations.jsonl"


def _rows(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def report(path, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date().isoformat()
    by_day = defaultdict(lambda: {"turns": 0, "cost": 0.0, "prompt": 0, "cached": 0, "known_prompt": 0,
                                  "unknown": 0, "players": defaultdict(float)})
    by_player = defaultdict(lambda: {"turns": 0, "cost": 0.0})

    for row in _rows(path):
        day = str(row.get("timestamp", ""))[:10]
        usage = row.get("usage") or {}
        if day < since or not usage:
            continue  # outside the window, or a turn with no model call
        player = row.get("actor_key") or "?"
        cost = row.get("cost_usd") or 0.0
        prompt = usage.get("prompt_tokens", 0)
        d = by_day[day]
        d["turns"] += 1
        d["cost"] += cost
        d["prompt"] += prompt
        d["players"][player] += cost
        if "cached_tokens" in usage:
            d["known_prompt"] += prompt
            d["cached"] += usage["cached_tokens"]
        else:
            d["unknown"] += 1
        by_player[player]["turns"] += 1
        by_player[player]["cost"] += cost

    if not by_day:
        print(f"No logged model turns since {since}.")
        return

    print(f"{'day':10}  {'turns':>5}  {'players':>7}  {'spend':>8}  {'$/turn':>7}  {'$/player':>8}  "
          f"{'prompt/turn':>11}  {'cached':>6}")
    for day in sorted(by_day):
        d = by_day[day]
        cached = f"{d['cached'] / d['known_prompt']:.0%}" if d["known_prompt"] else "?"
        if d["unknown"] and d["known_prompt"]:
            cached += "*"
        spend, per_turn, per_player = (f"${d['cost']:.3f}", f"${d['cost'] / d['turns']:.4f}",
                                       f"${d['cost'] / len(d['players']):.3f}")
        print(f"{day:10}  {d['turns']:>5}  {len(d['players']):>7}  {spend:>8}  {per_turn:>7}  {per_player:>8}  "
              f"{d['prompt'] // d['turns']:>11,}  {cached:>6}")
    if any(d["unknown"] for d in by_day.values()):
        print("  ? / * = some turns predate cache logging; their cost ignores cache discounts.")

    print("\nTop spenders over the window:")
    for player, p in sorted(by_player.items(), key=lambda item: -item[1]["cost"])[:10]:
        print(f"  {player:20}  {p['turns']:>5} turns  ${p['cost']:.3f}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7, help="how many UTC days back, including today")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="conversations.jsonl path")
    args = parser.parse_args(argv)
    report(args.log, args.days)


if __name__ == "__main__":
    main()
