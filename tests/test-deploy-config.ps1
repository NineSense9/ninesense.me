$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$deploy = Join-Path $root 'deploy'
$required = @(
  'guestbook.env.example', 'ninesense-guestbook.service',
  'ninesense-guestbook-backup.service', 'ninesense-guestbook-backup.timer',
  'backup-guestbook.sh', 'ninesense-rate-limit.conf', 'ninesense-nginx.conf',
  'ninesense-site.conf', 'deploy-guestbook.sh'
)
$missing = @($required | Where-Object { -not (Test-Path (Join-Path $deploy $_)) })
if ($missing.Count) { throw "Missing deploy files: $($missing -join ', ')" }

$service = [IO.File]::ReadAllText((Join-Path $deploy 'ninesense-guestbook.service'))
$nginx = [IO.File]::ReadAllText((Join-Path $deploy 'ninesense-nginx.conf'))
$rateLimit = [IO.File]::ReadAllText((Join-Path $deploy 'ninesense-rate-limit.conf'))
$backup = [IO.File]::ReadAllText((Join-Path $deploy 'backup-guestbook.sh'))
$environment = [IO.File]::ReadAllText((Join-Path $deploy 'guestbook.env.example'))
$siteConfig = [IO.File]::ReadAllText((Join-Path $deploy 'ninesense-site.conf'))

foreach ($contract in @(
  'User=ninesense', 'EnvironmentFile=/etc/ninesense/guestbook.env',
  '--host 127.0.0.1', '--port 8812', '--workers 1',
  '--forwarded-allow-ips=127.0.0.1', 'NoNewPrivileges=true',
  'PrivateTmp=true', 'ProtectSystem=strict'
)) {
  if ($service -notmatch [regex]::Escape($contract)) { throw "Service contract missing: $contract" }
}
foreach ($contract in @(
  'proxy_pass http://127.0.0.1:8812', 'client_max_body_size 32k',
  'proxy_set_header X-Forwarded-For $remote_addr',
  'Content-Security-Policy', 'X-Content-Type-Options', 'Referrer-Policy'
)) {
  if ($nginx -notmatch [regex]::Escape($contract)) { throw "Nginx contract missing: $contract" }
}
$guestbookLocation = [regex]::Match(
  $nginx,
  'location \^~ /guestbook/ \{(?<body>[\s\S]*?)\n\}'
)
if (-not $guestbookLocation.Success) { throw 'Guestbook Nginx location missing' }
if ($guestbookLocation.Groups['body'].Value -notmatch 'Cache-Control "no-cache" always') {
  throw 'Guestbook resources must revalidate after each release'
}
if ($nginx -match 'listen\s+(80|443)') { throw 'Guestbook config must not add listeners on 80/443' }
if ($siteConfig -notmatch 'listen 8811' -or $siteConfig -notmatch 'include /etc/nginx/snippets/ninesense-guestbook.conf') { throw 'Existing 8811 site integration missing' }
if ($rateLimit -notmatch 'limit_req_zone') { throw 'Nginx submission rate-limit zone missing' }
if ($backup -notmatch 'BACKUP_ROOT:-/var/backups/ninesense/guestbook') { throw 'Backup root override missing' }
if ($backup -notmatch 'PYTHON_BIN:-/opt/ninesense-guestbook/current/venv/bin/python') { throw 'Backup Python override missing' }
if ($backup -notmatch 'backup-db' -or $backup -notmatch 'integrity') { throw 'Backup command or verification missing' }
foreach ($setting in @(
  'NINESENSE_DATABASE_URL=', 'NINESENSE_CONTACT_KEY=', 'NINESENSE_SESSION_PEPPER=',
  'NINESENSE_RATE_LIMIT_KEY=', 'NINESENSE_COOKIE_SECURE=', 'NINESENSE_SMTP_HOST=',
  'NINESENSE_SMTP_PASSWORD=', 'NINESENSE_NOTIFICATION_TO=', 'NINESENSE_PUBLIC_ADMIN_URL='
)) {
  if ($environment -notmatch [regex]::Escape($setting)) { throw "Environment setting missing: $setting" }
}
Write-Host 'PASS deployment configuration contract'
