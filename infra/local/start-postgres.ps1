$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$dataDirectory = Join-Path $projectRoot ".dev\postgres-data"
$logPath = Join-Path $projectRoot ".dev\postgres.log"
$port = 55432

if (-not (Test-Path $dataDirectory)) {
    throw "Local PostgreSQL cluster not found at $dataDirectory. Initialize a disposable local cluster first."
}

$postgresBin = $env:POSTGRES_BIN
if (-not $postgresBin) {
    $postgresBin = "C:\Program Files\PostgreSQL\17\bin"
}
$pgCtl = Join-Path $postgresBin "pg_ctl.exe"
if (-not (Test-Path $pgCtl)) {
    throw "pg_ctl.exe was not found. Set POSTGRES_BIN to the PostgreSQL bin directory."
}

& $pgCtl -D $dataDirectory status *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Output "Project-local PostgreSQL is already running on 127.0.0.1:$port."
    return
}

& $pgCtl -D $dataDirectory -l $logPath -o "-p $port -h 127.0.0.1" start
if ($LASTEXITCODE -ne 0) { throw "Local PostgreSQL failed to start. Check .dev/postgres.log." }
