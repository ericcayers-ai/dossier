@echo off
cd /d "%~dp0"
set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
uv run dossier --root "%ROOT%" --open
