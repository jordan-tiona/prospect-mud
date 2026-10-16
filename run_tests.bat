@echo off
REM Runs the project's test suite. From the repo root: run_tests.bat
REM Optional: test labels to run instead of the full suite, e.g.
REM   run_tests.bat world.test_garden
REM Runs in parallel (see prospect\server\conf\test_runner.py); set
REM TEST_PARALLEL=1 for a serial run.
setlocal
call "%~dp0.venv\Scripts\activate.bat"
if "%TEST_PARALLEL%"=="" set TEST_PARALLEL=8
set LABELS=%*
if "%LABELS%"=="" (
    pushd "%~dp0ops\editor"
    python -m unittest -q test_editor test_serve || exit /b 1
    where node >nul 2>nul && (node --test test_core.js || exit /b 1)
    popd
    set LABELS=commands world typeclasses
)
cd /d "%~dp0prospect"
REM Django directly, not `evennia test`: the launcher forwards
REM `--settings settings.py` to Django verbatim, which breaks the
REM parallel workers' settings import.
python -m django test --settings=server.conf.settings --testrunner=server.conf.test_runner.ParallelEvenniaTestSuiteRunner --parallel %TEST_PARALLEL% %LABELS%
