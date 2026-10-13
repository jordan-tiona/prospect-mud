#!/usr/bin/env bash
# Runs the project's test suite. From the repo root: ./run_tests.sh
set -e

cd "$(dirname "$0")/prospect"
source ../.venv/Scripts/activate
evennia test --settings settings.py commands world
