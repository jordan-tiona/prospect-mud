#!/usr/bin/env bash
# Live-model NPC evals: the bad-actor probes (world/npc_probes.py) and
# the tool-call scenarios (world/npc_eval.py), run in the test
# database so the server can stay up. Costs real API usage, roughly
# $0.10-0.30 per NPC for the probes at the default trials.
#
#   ./run_npc_eval.sh                     # probes, every NPC
#   ./run_npc_eval.sh tarin_os mara_voss  # probes, two NPCs
#   EVAL=probes,scenarios ./run_npc_eval.sh
#   TRIALS=3 ./run_npc_eval.sh
#
# Writes prospect/server/logs/npc_eval/<timestamp>/report.md.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/.venv/Scripts/activate"

OUT="$ROOT/prospect/server/logs/npc_eval/$(date +%Y-%m-%d_%H%M)"
export PROSPECT_NPC_EVAL="${EVAL:-probes}"
export PROSPECT_NPC_EVAL_TRIALS="${TRIALS:-}"
export PROSPECT_NPC_EVAL_OUT="$OUT"

labels=()
for npc in "$@"; do
    class="$(echo "$npc" | awk -F_ '{for (i = 1; i <= NF; i++) printf "%s", toupper(substr($i, 1, 1)) substr($i, 2)}')Eval"
    labels+=("world.npc_probe_suite.$class")
done
[ ${#labels[@]} -eq 0 ] && labels=("world.npc_probe_suite")

cd "$ROOT/prospect"
python -m django test --settings=server.conf.settings \
    --testrunner=server.conf.test_runner.ParallelEvenniaTestSuiteRunner \
    --parallel "${PARALLEL:-6}" "${labels[@]}" || true
python world/npc_probe_report.py "$OUT"
