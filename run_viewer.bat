@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "src\105_patient_electrode_desktop_viewer.py" %*
) else (
  python "src\105_patient_electrode_desktop_viewer.py" %*
)
