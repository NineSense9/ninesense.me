param(
  [string]$BaseUrl = 'http://127.0.0.1:8811'
)

$ErrorActionPreference = 'Stop'
$checks = @(
  @{ Path = '/'; Status = 200 },
  @{ Path = '/guestbook/'; Status = 200; Csp = $true },
  @{ Path = '/admin/'; Status = 200; Csp = $true; NoStore = $true },
  @{ Path = '/api/health'; Status = 200; NoStore = $true },
  @{ Path = '/api/guestbook/messages'; Status = 200; NoStore = $true },
  @{ Path = '/definitely-missing'; Status = 404 }
)

foreach ($check in $checks) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri ($BaseUrl + $check.Path) -TimeoutSec 10
    $status = [int]$response.StatusCode
  } catch {
    if (-not $_.Exception.Response) { throw }
    $response = $_.Exception.Response
    $status = [int]$response.StatusCode
  }
  if ($status -ne $check.Status) { throw "$($check.Path) returned $status" }
  if ($check.Csp -and -not $response.Headers['Content-Security-Policy']) {
    throw "$($check.Path) is missing Content-Security-Policy"
  }
  if ($response.Headers['X-Content-Type-Options'] -ne 'nosniff' -and $status -ne 404) {
    throw "$($check.Path) is missing nosniff"
  }
  if ($check.NoStore -and $response.Headers['Cache-Control'] -notmatch 'no-store') {
    throw "$($check.Path) is missing no-store"
  }
  Write-Host "PASS $status $($check.Path)"
}

Write-Host 'PASS public deployment contract'
