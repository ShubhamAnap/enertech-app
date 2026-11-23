$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$mobileDirectory = Join-Path $projectRoot "apps\mobile"
$flutter = Join-Path $projectRoot ".dev\flutter-sdk\flutter\bin\flutter.bat"
if (-not (Test-Path $flutter)) { throw "Project-local Flutter SDK not found at $flutter." }

$env:APPDATA = Join-Path $projectRoot ".dev\appdata"
$env:LOCALAPPDATA = Join-Path $projectRoot ".dev\local-appdata"
$env:PUB_CACHE = Join-Path $projectRoot ".dev\pub-cache"
$env:FLUTTER_SUPPRESS_ANALYTICS = "true"
$env:PATH = "$env:PATH;$env:WINDIR\System32;$env:WINDIR;$env:WINDIR\System32\WindowsPowerShell\v1.0;C:\Program Files\Git\cmd"

$apiBaseUrl = $env:API_BASE_URL
if (-not $apiBaseUrl) { $apiBaseUrl = "http://10.0.2.2:8000/api/v1" }
Push-Location $mobileDirectory
try { & $flutter run "--dart-define=API_BASE_URL=$apiBaseUrl" }
finally { Pop-Location }
