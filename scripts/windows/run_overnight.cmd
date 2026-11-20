@echo off
rem Overnight clip run. Edit the two paths, then register it with install_task.ps1.
set CLIP_DESK_HOME=C:\clipdesk
set CLIP_DESK_ENCODER=h264_nvenc
set CLIP_DESK_WHISPER=small
cd /d %CLIP_DESK_HOME%
python "C:\path\to\gtavi-claudecode\scripts\pipeline.py" run --overnight >> "%CLIP_DESK_HOME%\overnight.log" 2>&1
