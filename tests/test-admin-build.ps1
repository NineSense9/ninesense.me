$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'admin-app/dist'
$indexPath = Join-Path $dist 'index.html'
$manifestPath = Join-Path $dist '.vite/manifest.json'

if (-not (Test-Path $indexPath)) { throw 'Admin build index missing' }
if (-not (Test-Path $manifestPath)) { throw 'Admin Vite manifest missing' }

$manifest = Get-Content -Raw -Encoding UTF8 $manifestPath | ConvertFrom-Json
$entry = @(
    $manifest.PSObject.Properties.Value |
        Where-Object { $_.isEntry -and $_.src -eq 'index.html' }
) | Select-Object -First 1
if (-not $entry -or -not $entry.isEntry) { throw 'Admin entry missing from manifest' }

$scriptPath = Join-Path $dist $entry.file
if (-not (Test-Path $scriptPath)) { throw 'Admin JavaScript artifact missing' }

foreach ($cssFile in @($entry.css)) {
    if (-not (Test-Path (Join-Path $dist $cssFile))) {
        throw "Admin CSS artifact missing: $cssFile"
    }
}

Write-Host 'PASS administration application build contract'
