$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$mobileDirectory = Join-Path $projectRoot "apps\mobile"
$envFile = Join-Path $mobileDirectory ".env"
$flutter = Join-Path $projectRoot ".dev\flutter-sdk\flutter\bin\flutter.bat"

if (-not (Test-Path -LiteralPath $envFile)) { throw "Create apps/mobile/.env from apps/mobile/.env.example and configure Firebase and API values before building." }
if (-not (Test-Path -LiteralPath $flutter)) { throw "Project-local Flutter SDK not found at $flutter." }
$values = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$') { $values[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'") }
}
$required = @("FIREBASE_API_KEY", "FIREBASE_APP_ID", "FIREBASE_PROJECT_ID", "FIREBASE_MESSAGING_SENDER_ID", "GOOGLE_SERVER_CLIENT_ID", "API_BASE_URL")
$missing = @($required | Where-Object { -not $values[$_] })
if ($missing.Count -gt 0) { throw "APK build stopped: configure $($missing -join ', ') in apps/mobile/.env first." }
$forbidden = @($values.Keys | Where-Object { $_ -match 'SUPABASE|DATABASE_URL|SERVICE_ACCOUNT|WORDPRESS|APPLICATION_PASSWORD' })
if ($forbidden.Count -gt 0) { throw "Remove server-only values from apps/mobile/.env: $($forbidden -join ', ')." }

$env:APPDATA = Join-Path $projectRoot ".dev\appdata"
$env:LOCALAPPDATA = Join-Path $projectRoot ".dev\local-appdata"
$env:PUB_CACHE = Join-Path $projectRoot ".dev\pub-cache"
$env:GRADLE_USER_HOME = Join-Path $projectRoot ".dev\gradle"
$env:TEMP = Join-Path $projectRoot ".dev\temp"
$env:TMP = Join-Path $projectRoot ".dev\temp"
$env:FLUTTER_SUPPRESS_ANALYTICS = "true"
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
$env:ANDROID_HOME = "C:\Users\User\AppData\Local\Android\Sdk"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH;$env:WINDIR\System32;$env:WINDIR;$env:WINDIR\System32\WindowsPowerShell\v1.0;C:\Program Files\Git\cmd"
Push-Location $mobileDirectory
try {
    & $flutter build apk --release
    $outputApk = Join-Path $mobileDirectory "build\app\outputs\flutter-apk\app-release.apk"
    $targetApk = Join-Path $projectRoot "update.apk"
    if (Test-Path -LiteralPath $outputApk) {
        Copy-Item -LiteralPath $outputApk -Destination $targetApk -Force
        Write-Host "Success: Copied release APK to $targetApk"
    }
}
finally { Pop-Location }
