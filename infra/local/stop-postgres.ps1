$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$dataDirectory = Join-Path $projectRoot ".dev\postgres-data"
$postgresBin = $env:POSTGRES_BIN
if (-not $postgresBin) { $postgresBin = "C:\Program Files\PostgreSQL\17\bin" }
$pgCtl = Join-Path $postgresBin "pg_ctl.exe"
if (-not (Test-Path $dataDirectory)) { throw "Local PostgreSQL cluster not found." }
& $pgCtl -D $dataDirectory stop -m fast
if ($LASTEXITCODE -ne 0) { throw "Local PostgreSQL failed to stop cleanly." }
