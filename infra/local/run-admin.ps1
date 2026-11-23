$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$adminDirectory = Join-Path $projectRoot "apps\admin"
$npm = "C:\Program Files\nodejs\npm.cmd"
if (-not (Test-Path $npm)) { throw "npm.cmd not found. Install Node.js and set the npm executable path." }
Push-Location $adminDirectory
try { & $npm run dev }
finally { Pop-Location }
