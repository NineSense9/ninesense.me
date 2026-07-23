$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$site = Join-Path $root 'site'
$index = [IO.File]::ReadAllText((Join-Path $site 'index.html'), [Text.Encoding]::UTF8)

$required = @(
  'index.html', '404.html', 'robots.txt', 'site.webmanifest',
  'favicon.svg', 'apple-touch-icon.png', 'assets/og-cover.jpg',
  'guestbook/index.html', 'guestbook/guestbook.css', 'guestbook/guestbook.js',
  'admin/index.html', 'admin/.vite/manifest.json'
)

$missing = @($required | Where-Object { -not (Test-Path (Join-Path $site $_)) })
if ($missing.Count) { throw "Missing release files: $($missing -join ', ')" }
if ($index -notmatch 'href="\./guestbook/"') { throw 'Desktop guestbook navigation link missing' }
if ($index -notmatch 'class="mobile-menu-item" href="\./guestbook/"') { throw 'Mobile guestbook navigation link missing' }

$guestbook = [IO.File]::ReadAllText((Join-Path $site 'guestbook/index.html'), [Text.Encoding]::UTF8)
$guestbookCss = [IO.File]::ReadAllText((Join-Path $site 'guestbook/guestbook.css'), [Text.Encoding]::UTF8)
$guestbookJs = [IO.File]::ReadAllText((Join-Path $site 'guestbook/guestbook.js'), [Text.Encoding]::UTF8)
$guestbookContracts = @(
  'id="guestbook-form"', 'name="kind"', 'value="public"', 'value="private"',
  'id="nickname"', 'id="contact"', 'id="content"', 'name="website"',
  'id="content-counter"', 'aria-live="polite"', 'id="message-feed"',
  'id="load-more"', 'maxlength="500"'
)
foreach ($contract in $guestbookContracts) {
  if ($guestbook -notmatch [regex]::Escape($contract)) { throw "Guestbook contract missing: $contract" }
}
if ($guestbookCss -notmatch 'max-width:\s*768px') { throw 'Guestbook tablet breakpoint missing' }
if ($guestbookCss -notmatch 'max-width:\s*390px') { throw 'Guestbook mobile breakpoint missing' }
if ($guestbookCss -notmatch 'prefers-reduced-motion') { throw 'Guestbook reduced-motion rules missing' }
if ($guestbookJs -notmatch '\.textContent') { throw 'Guestbook safe text rendering missing' }
if ($guestbookJs -match '\.innerHTML') { throw 'Guestbook must not render visitor content with innerHTML' }
if ($guestbook -notmatch 'aria-label="LEAVE A NOTE FOR LATER"') {
  throw 'Guestbook BlurText accessible title missing'
}
$blurTitleContracts = @(
  'NINESENSE / GUESTBOOK / PRIVATE LETTERS',
  'data-blur-title',
  'data-blur-text="LEAVE A NOTE"',
  'data-blur-text="FOR LATER"',
  'guestbook.css?v=20260723-blur1',
  'guestbook.js?v=20260723-blur1'
)
foreach ($contract in $blurTitleContracts) {
  if ($guestbook -notmatch [regex]::Escape($contract)) {
    throw "Guestbook BlurText title contract missing: $contract"
  }
}
foreach ($contract in @(
  'function initBlurTitle()',
  'IntersectionObserver',
  'prefers-reduced-motion: reduce',
  'animationend'
)) {
  if ($guestbookJs -notmatch [regex]::Escape($contract)) {
    throw "Guestbook BlurText implementation missing: $contract"
  }
}
foreach ($contract in @(
  '.blur-word',
  '.blur-word + .blur-word',
  '@keyframes blur-word-in'
)) {
  if ($guestbookCss -notmatch [regex]::Escape($contract)) {
    throw "Guestbook BlurText styling missing: $contract"
  }
}
if ($guestbook -match 'data-shuffle' -or
    $guestbookJs -match 'Shuffle|shuffle-' -or
    $guestbookCss -match '\.shuffle-|letter-handoff|final-arrive') {
  throw 'Legacy Shuffle title implementation must be removed'
}

$adminRoot = Join-Path $site 'admin'
$admin = [IO.File]::ReadAllText((Join-Path $adminRoot 'index.html'), [Text.Encoding]::UTF8)
$manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $adminRoot '.vite/manifest.json') | ConvertFrom-Json
$adminEntry = @(
  $manifest.PSObject.Properties.Value |
    Where-Object { $_.isEntry -and $_.src -eq 'index.html' }
) | Select-Object -First 1
if (-not $adminEntry) { throw 'Admin release entry missing' }
if (-not (Test-Path (Join-Path $adminRoot $adminEntry.file))) { throw 'Admin release script missing' }
foreach ($cssFile in @($adminEntry.css)) {
  if (-not (Test-Path (Join-Path $adminRoot $cssFile))) { throw "Admin release CSS missing: $cssFile" }
}
if ($admin -match '注册|忘记密码') { throw 'Admin page must not expose registration or password reset' }
$adminSource = Get-ChildItem (Join-Path $root 'admin-app/src') -Recurse -File |
  ForEach-Object { [IO.File]::ReadAllText($_.FullName, [Text.Encoding]::UTF8) }
$sourceText = $adminSource -join "`n"
if ($sourceText -notmatch 'X-CSRF-Token') { throw 'Admin mutations must attach CSRF token' }
if ($sourceText -match 'localStorage|sessionStorage') { throw 'Admin must keep security tokens in memory only' }
if ($sourceText -match 'dangerouslySetInnerHTML|\.innerHTML') { throw 'Admin must render untrusted content as text' }
Write-Host 'PASS static guestbook release contract'
