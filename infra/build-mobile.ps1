$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$mobileDirectory = Join-Path $projectRoot "apps\mobile"
$envFile = Join-Path $mobileDirectory ".env"
$flutter = Join-Path $projectRoot ".dev\flutter-sdk\flutter\bin\flutter.bat"
$signingEnvFile = Join-Path $projectRoot "infra\local\release-signing.env"

# Local-only release credentials are git-ignored and never printed. Explicit
# process environment variables take precedence over the local file.
if (Test-Path -LiteralPath $signingEnvFile -PathType Leaf) {
    $allowedSigningVariables = @("ANDROID_KEYSTORE_PATH", "ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD")
    foreach ($line in Get-Content -LiteralPath $signingEnvFile) {
        if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$' -and $Matches[1] -in $allowedSigningVariables) {
            $name = $Matches[1]
            if (-not [Environment]::GetEnvironmentVariable($name)) {
                [Environment]::SetEnvironmentVariable($name, $Matches[2], "Process")
            }
        }
    }
}

if (-not (Test-Path -LiteralPath $envFile)) { throw "Create apps/mobile/.env from apps/mobile/.env.example and configure Firebase and API values before building." }
if (-not (Test-Path -LiteralPath $flutter)) { throw "Project-local Flutter SDK not found at $flutter." }
$values = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$') { $values[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'") }
}
$required = @("FIREBASE_API_KEY", "FIREBASE_APP_ID", "FIREBASE_PROJECT_ID", "FIREBASE_MESSAGING_SENDER_ID", "GOOGLE_SERVER_CLIENT_ID", "API_BASE_URL")
$missing = @($required | Where-Object { -not $values[$_] })
if ($missing.Count -gt 0) { throw "APK build stopped: configure $($missing -join ', ') in apps/mobile/.env first." }
$apiUri = $null
if (-not [Uri]::TryCreate($values["API_BASE_URL"], [UriKind]::Absolute, [ref]$apiUri) -or $apiUri.Scheme -ne "https" -or $apiUri.Host -in @("localhost", "127.0.0.1", "10.0.2.2")) {
    throw "Release APK build stopped: API_BASE_URL must be the HTTPS production or staging API endpoint, not a local development URL."
}
$forbidden = @($values.Keys | Where-Object { $_ -match 'SUPABASE|DATABASE_URL|SERVICE_ACCOUNT|WORDPRESS|APPLICATION_PASSWORD' })
if ($forbidden.Count -gt 0) { throw "Remove server-only values from apps/mobile/.env: $($forbidden -join ', ')." }
$dartDefines = @($required | ForEach-Object { "--dart-define=$($_)=$($values[$_])" })

$signingVariables = @("ANDROID_KEYSTORE_PATH", "ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD")
$missingSigning = @($signingVariables | Where-Object { -not [Environment]::GetEnvironmentVariable($_) })
if ($missingSigning.Count -gt 0) { throw "Production APK build stopped: configure the existing production signing identity in environment variables: $($missingSigning -join ', '). Do not put passwords in apps/mobile/.env." }
if (-not (Test-Path -LiteralPath $env:ANDROID_KEYSTORE_PATH -PathType Leaf)) { throw "Production APK build stopped: ANDROID_KEYSTORE_PATH does not point to an existing keystore file." }

$env:APPDATA = Join-Path $projectRoot ".dev\appdata"
$env:LOCALAPPDATA = Join-Path $projectRoot ".dev\local-appdata"
$env:PUB_CACHE = Join-Path $projectRoot ".dev\pub-cache"
$env:GRADLE_USER_HOME = Join-Path $projectRoot ".dev\gradle"
$env:TEMP = Join-Path $projectRoot ".dev\temp"
$env:TMP = Join-Path $projectRoot ".dev\temp"
$env:FLUTTER_SUPPRESS_ANALYTICS = "true"
$localJdkRoot = Join-Path $projectRoot ".dev\jdk21"
$javaHomeCandidates = @(
    Get-ChildItem -LiteralPath $localJdkRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "jdk-21*" } |
        Sort-Object Name -Descending |
        ForEach-Object { $_.FullName }
)
if ($env:JAVA_HOME) { $javaHomeCandidates += $env:JAVA_HOME }
foreach ($jdkParent in @(
    (Join-Path $env:ProgramFiles "Eclipse Adoptium"),
    (Join-Path $env:ProgramFiles "Microsoft"),
    (Join-Path $env:ProgramFiles "Android Studio"),
    (Join-Path $env:ProgramFiles "Android\Android Studio")
)) {
    if (Test-Path -LiteralPath $jdkParent -PathType Container) {
        $javaHomeCandidates += Get-ChildItem -LiteralPath $jdkParent -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "jdk-21*" -or $_.Name -eq "jbr" } |
            ForEach-Object { $_.FullName }
    }
}
$java21Directory = $null
foreach ($javaHomeCandidate in ($javaHomeCandidates | Select-Object -Unique)) {
    $javaExecutable = Join-Path $javaHomeCandidate "bin\java.exe"
    if (-not (Test-Path -LiteralPath $javaExecutable -PathType Leaf)) { continue }
    $javaVersion = (& $javaExecutable -version 2>&1 | Out-String)
    if ($javaVersion -match 'version "21(?:\.|"")') {
        $java21Directory = Get-Item -LiteralPath $javaHomeCandidate
        break
    }
}
if (-not $java21Directory) { throw "Release build requires JDK 21. Install an x64 JDK 21 under $localJdkRoot." }
$env:JAVA_HOME = $java21Directory.FullName
$env:ANDROID_HOME = "C:\Users\User\AppData\Local\Android\Sdk"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH;$env:WINDIR\System32;$env:WINDIR;$env:WINDIR\System32\WindowsPowerShell\v1.0;C:\Program Files\Git\cmd"
Push-Location $mobileDirectory
try {
    & $flutter build apk --release @dartDefines
    $outputApk = Join-Path $mobileDirectory "build\app\outputs\flutter-apk\app-release.apk"
    $targetApk = Join-Path $projectRoot "update.apk"
    if (Test-Path -LiteralPath $outputApk) {
        Copy-Item -LiteralPath $outputApk -Destination $targetApk -Force
        Write-Host "Success: Copied release APK to $targetApk"
    }
}
finally { Pop-Location }
