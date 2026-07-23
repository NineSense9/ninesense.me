$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$trackedFiles = git -C $root ls-files | Where-Object {
  $_ -notlike 'docs/plans/*' -and
  $_ -notlike '*.png' -and
  $_ -notlike '*.jpg' -and
  $_ -notlike '*.jpeg' -and
  $_ -notlike '*.webp' -and
  $_ -notlike '*.ico'
}

$forbidden = @(
  @{ Label = 'live server address'; Value = ('180' + '.76' + '.137' + '.117') },
  @{ Label = 'local private-key filename'; Value = ('codex' + '_theresa' + '_ed25519') },
  @{ Label = 'local administrator profile path'; Value = ('C:\Users\' + 'Administrator') },
  @{ Label = 'previously shared server password'; Value = ('Ls52' + '11314') },
  @{ Label = 'private key material'; Value = ('BEGIN ' + 'OPENSSH PRIVATE KEY') }
)

$violations = [Collections.Generic.List[string]]::new()
foreach ($relativePath in $trackedFiles) {
  $path = Join-Path $root $relativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
  $content = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
  foreach ($item in $forbidden) {
    if ($content.IndexOf($item.Value, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
      $violations.Add("$relativePath contains $($item.Label)")
    }
  }
}

if ($violations.Count) {
  throw "Public repository hygiene failed:`n$($violations -join "`n")"
}

Write-Host 'PASS public repository hygiene'
