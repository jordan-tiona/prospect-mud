@echo off
REM Runs the project's test suite. From the repo root: run_tests.bat
cd "%~dp0prospect"
call ..\.venv\Scripts\activate.bat
evennia test --settings settings.py commands world
