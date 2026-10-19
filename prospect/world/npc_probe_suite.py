"""
Runs the live-model NPC evals inside the test runner's throwaway
database, one TestCase per NPC so ./run_npc_eval.sh can run the NPCs
in parallel workers. Named so the ordinary suite never discovers it,
and every test skips unless PROSPECT_NPC_EVAL is set, so even an
explicit label costs nothing by accident.

PROSPECT_NPC_EVAL: comma-separated, "probes" (world/npc_probes.py)
and/or "scenarios" (world/npc_eval.py's tool-call scenarios).
PROSPECT_NPC_EVAL_TRIALS: trials per probe or scenario.
PROSPECT_NPC_EVAL_OUT: directory for each NPC's JSON results;
world/npc_probe_report.py turns them into report.md.
"""

import json
import os
from pathlib import Path

from django.test import TestCase

from world import npc_eval, npc_probes
from world.content_files import CONTENT_DIR

MODES = {mode.strip() for mode in os.environ.get("PROSPECT_NPC_EVAL", "").split(",") if mode.strip()}
NPC_IDS = sorted(path.stem for path in (Path(CONTENT_DIR) / "npcs").glob("*.md"))


def _scenario_json(result) -> dict:
    return {
        "name": result.scenario.name,
        "hits": result.hits,
        "trials": result.trials,
        "notes": result.scenario.notes,
        "unexpected": [repr(item) for item in result.unexpected],
    }


class _NpcEval(TestCase):
    npc_id = ""

    def setUp(self):
        if not MODES:
            self.skipTest("set PROSPECT_NPC_EVAL to run the live-model NPC eval")

    def _write(self, kind, data):
        out = Path(os.environ.get("PROSPECT_NPC_EVAL_OUT", "server/logs/npc_eval/latest"))
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{self.npc_id}.{kind}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

    def _trials(self, default):
        return int(os.environ.get("PROSPECT_NPC_EVAL_TRIALS") or default)

    def test_probes(self):
        if "probes" not in MODES:
            self.skipTest("probes not requested")
        results = npc_probes.run_for_npc(self.npc_id, trials=self._trials(npc_probes.DEFAULT_TRIALS))
        self._write("probes", npc_probes.to_json(results))

    def test_scenarios(self):
        if "scenarios" not in MODES:
            self.skipTest("scenarios not requested")
        scenarios = [s for s in npc_eval.SCENARIOS if s.npc_id == self.npc_id]
        if not scenarios:
            self.skipTest(f"no tool-call scenarios for {self.npc_id}")
        trials = self._trials(npc_eval.DEFAULT_TRIALS)
        self._write("scenarios", [_scenario_json(npc_eval.run_scenario(s, trials=trials)) for s in scenarios])


for _npc_id in NPC_IDS:
    _name = "".join(part.title() for part in _npc_id.split("_")) + "Eval"
    globals()[_name] = type(_name, (_NpcEval,), {"npc_id": _npc_id})
del _npc_id, _name
