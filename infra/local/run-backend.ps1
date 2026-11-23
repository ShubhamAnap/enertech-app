$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backendDirectory = Join-Path $projectRoot "backend"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Project virtual environment not found. Create .venv and install backend/requirements.txt." }
Push-Location $backendDirectory
try { & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 }
finally { Pop-Location }
