@echo off
cd /d "%~dp0"
rem Padroes calibrados para este notebook; defina as variaveis antes para sobrescrever.
if not defined JARVIS_MIC set JARVIS_MIC=10,11
if not defined JARVIS_CLAP_THRESH set JARVIS_CLAP_THRESH=0.05
uv run python jarvis_show.py %*
