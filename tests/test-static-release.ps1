$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$site = Join-Path $root 'site'
$index = [IO.File]::ReadAllText((Join-Path $site 'index.html'), [Text.Encoding]::UTF8)

$required = @(
  'index.html', '404.html', 'robots.txt', 'site.webmanifest',
  'favicon.svg', 'apple-touch-icon.png', 'assets/og-cover.jpg',
  'guestbook/index.html', 'guestbook/guestbook.css', 'guestbook/guestbook.js',
  'admin/index.html', 'admin/admin.css', 'admin/admin.js'
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

$admin = [IO.File]::ReadAllText((Join-Path $site 'admin/index.html'), [Text.Encoding]::UTF8)
$adminJs = [IO.File]::ReadAllText((Join-Path $site 'admin/admin.js'), [Text.Encoding]::UTF8)
$adminContracts = @(
  'id="login-form"', 'id="dashboard"', 'id="status-filter"', 'id="kind-filter"',
  'id="message-search"', 'id="message-list"', 'id="message-detail"',
  'id="contact-value"', 'id="reply-editor"', 'id="confirm-dialog"', 'id="logout-button"'
)
foreach ($contract in $adminContracts) {
  if ($admin -notmatch [regex]::Escape($contract)) { throw "Admin contract missing: $contract" }
}
if ($admin -match '注册|忘记密码') { throw 'Admin page must not expose registration or password reset' }
if ($adminJs -notmatch 'X-CSRF-Token') { throw 'Admin mutations must attach CSRF token' }
if ($adminJs -match 'localStorage|sessionStorage') { throw 'Admin must keep CSRF token in memory only' }
if ($adminJs -match '\.innerHTML') { throw 'Admin must not render visitor content with innerHTML' }
Write-Host 'PASS static guestbook release contract'
