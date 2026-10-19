"""
Turns a ./run_npc_eval.sh results directory (one JSON file per NPC
and kind, written by world/npc_probe_suite.py) into report.md beside
them: a summary table first, then every failing trial's transcript.
Plain Python with no Django or Evennia imports, so the script can run
it after the test workers exit.

    python world/npc_probe_report.py <results dir>
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def _load(out: Path, kind: str) -> dict:
    return {
        path.name.split(".")[0]: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(out.glob(f"*.{kind}.json"))
    }


def _transcript(trial: dict) -> list:
    lines = []
    for turn in trial["turns"]:
        lines.append(f"    > {turn['player']}")
        if turn["error"]:
            lines.append(f"    (model unavailable: {turn['error']})")
        if turn["flagged"]:
            lines.append(f"    (blocked by the output filter: {turn['flagged']})")
        for text in turn["shown"]:
            lines.append(f"    {text}")
        for call in turn["calls"]:
            outcome = "applied" if call["applied"] else f"dropped: {call['reason']}"
            lines.append(f"    [call] {call['name']} {json.dumps(call['arguments'])} ({outcome})")
    return lines


def _probe_section(probes: dict) -> list:
    trials = [trial for results in probes.values() for trial in results]
    if not trials:
        return []
    cost = sum(trial["cost_usd"] for trial in trials)
    engine_fails = [t for t in trials if t["failures"]]
    graded = [t for t in trials if t["judge_pass"] is not None]
    judge_fails = [t for t in graded if not t["judge_pass"]]
    lines = [
        "## Bad-actor probes",
        "",
        f"{len(trials)} trials, ${cost:.2f}. Engine checks failed: **{len(engine_fails)}**. "
        f"Grader failed: **{len(judge_fails)}** of {len(graded)} graded.",
        "",
        "Engine checks must be zero (docs/playtest-readiness.md). The grader is a second opinion: "
        "read its failures, don't treat them as settled.",
        "",
    ]
    names = sorted({t["probe"] for t in trials}, key=lambda n: next(t["category"] for t in trials if t["probe"] == n))
    npcs = sorted(probes)
    lines.append("| probe | " + " | ".join(npcs) + " |")
    lines.append("|---|" + "---|" * len(npcs))
    cells = defaultdict(list)
    for t in trials:
        cells[(t["probe"], t["npc_id"])].append(t)
    for name in names:
        row = []
        for npc in npcs:
            group = cells[(name, npc)]
            if not group:
                row.append("")
                continue
            engine = sum(1 for t in group if not t["failures"])
            judged = sum(1 for t in group if t["judge_pass"])
            mark = "" if engine == len(group) else " **ENGINE**"
            row.append(f"{engine}/{len(group)} · {judged}/{len(group)}{mark}")
        lines.append(f"| {name} | " + " | ".join(row) + " |")
    lines += ["", "Cells read engine passes · grader passes, out of the trials run.", ""]

    for heading, failed in (("Engine-check failures", engine_fails), ("Grader failures", judge_fails)):
        lines += [f"### {heading}", ""]
        if not failed:
            lines += ["None.", ""]
        for t in failed:
            why = "; ".join(t["failures"]) if heading.startswith("Engine") else t["judge_reason"]
            lines.append(f"**{t['npc_id']} / {t['probe']} (trial {t['trial']})**: {why}")
            lines.append("")
            lines += _transcript(t)
            lines.append("")
    unread = [t for t in trials if t["judge_pass"] is None]
    if unread:
        lines += ["### Ungraded", ""] + [f"- {t['npc_id']} / {t['probe']}: {t['judge_reason']}" for t in unread] + [""]
    return lines


def _scenario_section(scenarios: dict) -> list:
    if not scenarios:
        return []
    lines = ["## Tool-call scenarios (world/npc_eval.py)", ""]
    for npc, results in scenarios.items():
        for r in results:
            lines.append(f"- {npc} / {r['name']}: {r['hits']}/{r['trials']}")
            if r["unexpected"]:
                lines.append(f"    - unexpected: {', '.join(r['unexpected'])[:600]}")
    return lines + [""]


def write_report(out: Path) -> Path:
    lines = [f"# NPC eval: {out.name}", ""]
    lines += _probe_section(_load(out, "probes"))
    lines += _scenario_section(_load(out, "scenarios"))
    path = out / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write_report(Path(sys.argv[1])))
