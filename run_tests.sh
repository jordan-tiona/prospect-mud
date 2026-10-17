#!/usr/bin/env bash
# Runs the project's test suite. From the repo root: ./run_tests.sh
# Optional: test labels to run instead of the full suite, e.g.
#   ./run_tests.sh world.test_garden
# Runs in parallel (see prospect/server/conf/test_runner.py); set
# TEST_PARALLEL=1 for a serial run.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/.venv/Scripts/activate"

if [ $# -eq 0 ]; then
    (cd "$ROOT/ops/editor" && python -m unittest -q test_editor test_serve)
    (cd "$ROOT/ops/namegen" && python -m unittest -q test_namegen)
    if command -v node >/dev/null; then node --test "$ROOT/ops/editor/test_core.js"; else echo "node not found: skipping ops/editor/test_core.js"; fi
    set -- commands world typeclasses
fi

cd "$ROOT/prospect"
# Django directly, not `evennia test`: the launcher forwards
# `--settings settings.py` to Django verbatim, which breaks the
# parallel workers' settings import.
python -m django test --settings=server.conf.settings \
    --testrunner=server.conf.test_runner.ParallelEvenniaTestSuiteRunner \
    --parallel "${TEST_PARALLEL:-8}" "$@"
