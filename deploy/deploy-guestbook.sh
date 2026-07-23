#!/usr/bin/env bash
set -Eeuo pipefail

release=${1:?usage: deploy-guestbook.sh RELEASE [ARCHIVE]}
archive=${2:-/tmp/ninesense-${release}.tar.gz}
app_root=/opt/ninesense-guestbook
app_release=${app_root}/releases/${release}
static_root=/var/www/ninesense
static_release=${static_root}/releases/${release}
backup_root=/root/ninesense-deploy-backups/${release}
previous_app=$(readlink -f "${app_root}/current" 2>/dev/null || true)
previous_static=$(readlink -f "${static_root}/current" 2>/dev/null || true)
previous_revision=
app_switched=0
nginx_changed=0
static_switched=0
migration_applied=0
service_was_active=0
backup_timer_was_active=0

restore_file() {
  local path="$1" name="$2"
  if [[ -e "${backup_root}/${name}" ]]; then
    cp -a "${backup_root}/${name}" "$path"
  else
    rm -f "$path"
  fi
}

rollback() {
  local rc="$1"
  trap - ERR
  set +e
  echo "ROLLBACK rc=${rc}" >&2
  systemctl stop ninesense-guestbook.service >/dev/null 2>&1 || true
  if [[ $migration_applied -eq 1 && -n "$previous_revision" ]]; then
    if ! runuser -u ninesense -- bash -c \
      "cd '${app_release}/server'; set -a; . /etc/ninesense/guestbook.env; set +a; exec '${app_release}/venv/bin/alembic' -c alembic.ini downgrade '${previous_revision}'"; then
      [[ -f "${backup_root}/pre-migration.sqlite3" ]] && install \
        -o ninesense -g ninesense -m 0600 \
        "${backup_root}/pre-migration.sqlite3" \
        /var/lib/ninesense/guestbook.sqlite3
    fi
  elif [[ -f "${backup_root}/pre-migration.sqlite3" ]]; then
    install -o ninesense -g ninesense -m 0600 \
      "${backup_root}/pre-migration.sqlite3" \
      /var/lib/ninesense/guestbook.sqlite3
  fi
  if [[ $app_switched -eq 1 ]]; then
    if [[ -n "$previous_app" ]]; then
      ln -sfn "$previous_app" "${app_root}/current.rollback"
      mv -Tf "${app_root}/current.rollback" "${app_root}/current"
    else
      rm -f "${app_root}/current"
    fi
  fi
  if [[ $static_switched -eq 1 ]]; then
    if [[ -n "$previous_static" ]]; then
      ln -sfn "$previous_static" "${static_root}/current.rollback"
      mv -Tf "${static_root}/current.rollback" "${static_root}/current"
    else
      rm -f "${static_root}/current"
    fi
  fi
  if [[ $nginx_changed -eq 1 ]]; then
    restore_file /etc/nginx/sites-available/ninesense.conf ninesense.conf
    restore_file /etc/nginx/conf.d/ninesense-rate-limit.conf ninesense-rate-limit.conf
    restore_file /etc/nginx/snippets/ninesense-guestbook.conf ninesense-guestbook.conf
    nginx -t >/dev/null 2>&1 && systemctl reload nginx
  fi
  systemctl stop ninesense-guestbook-backup.timer >/dev/null 2>&1 || true
  systemctl daemon-reload >/dev/null 2>&1 || true
  if [[ $service_was_active -eq 1 && -n "$previous_app" ]]; then
    systemctl restart ninesense-guestbook.service >/dev/null 2>&1 || true
  fi
  if [[ $backup_timer_was_active -eq 1 ]]; then
    systemctl start ninesense-guestbook-backup.timer >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap 'rollback $?' ERR

install -d -m 0700 "$backup_root"
for pair in \
  /etc/nginx/sites-available/ninesense.conf:ninesense.conf \
  /etc/nginx/conf.d/ninesense-rate-limit.conf:ninesense-rate-limit.conf \
  /etc/nginx/snippets/ninesense-guestbook.conf:ninesense-guestbook.conf; do
  path=${pair%%:*}
  name=${pair##*:}
  [[ -e "$path" ]] && cp -a "$path" "${backup_root}/${name}"
done

id -u ninesense >/dev/null 2>&1 || \
  useradd --system --home-dir /var/lib/ninesense --shell /usr/sbin/nologin ninesense
install -d -o root -g root -m 0755 "${app_root}/releases" "${static_root}/releases"
install -d -o ninesense -g ninesense -m 0700 /var/lib/ninesense
install -d -o ninesense -g ninesense -m 0700 \
  /var/backups/ninesense/guestbook \
  /var/backups/ninesense/guestbook/daily \
  /var/backups/ninesense/guestbook/monthly
install -d -o root -g ninesense -m 0750 /etc/ninesense

rm -rf "$app_release" "$static_release"
install -d -m 0755 "$app_release" "$static_release"
tar -xzf "$archive" -C "$app_release"
[[ -f "$app_release/site/admin/.vite/manifest.json" ]]
cp -a "$app_release/site/." "$static_release/"
find "$static_release" -type d -exec chmod 0755 {} +
find "$static_release" -type f -exec chmod 0644 {} +

python3 -m venv "$app_release/venv"
"$app_release/venv/bin/python" -m pip install \
  --disable-pip-version-check --no-cache-dir "$app_release/server"

if [[ ! -e /etc/ninesense/guestbook.env ]]; then
  contact_key=$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')
  security_key=$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')
  session_pepper=$(openssl rand -hex 48)
  rate_limit_key=$(openssl rand -hex 48)
  cat > /etc/ninesense/guestbook.env <<EOF
NINESENSE_DATABASE_URL=sqlite:////var/lib/ninesense/guestbook.sqlite3
NINESENSE_CONTACT_KEY=${contact_key}
NINESENSE_SECURITY_KEY=${security_key}
NINESENSE_SESSION_PEPPER=${session_pepper}
NINESENSE_RATE_LIMIT_KEY=${rate_limit_key}
NINESENSE_COOKIE_SECURE=false
NINESENSE_COOKIE_NAME=ninesense_admin
NINESENSE_SESSION_HOURS=8
NINESENSE_LOGIN_CHALLENGE_MINUTES=5
NINESENSE_SMTP_HOST=
NINESENSE_SMTP_PORT=465
NINESENSE_SMTP_USERNAME=
NINESENSE_SMTP_PASSWORD=
NINESENSE_NOTIFICATION_TO=
NINESENSE_PUBLIC_ADMIN_URL=https://example.com/admin/
EOF
fi
if ! grep -q '^NINESENSE_SECURITY_KEY=' /etc/ninesense/guestbook.env; then
  security_key=$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')
  printf '\nNINESENSE_SECURITY_KEY=%s\n' "$security_key" >> /etc/ninesense/guestbook.env
fi
contact_key_value=$(sed -n 's/^NINESENSE_CONTACT_KEY=//p' /etc/ninesense/guestbook.env | tail -n 1)
security_key_value=$(sed -n 's/^NINESENSE_SECURITY_KEY=//p' /etc/ninesense/guestbook.env | tail -n 1)
if [[ -z "$contact_key_value" || -z "$security_key_value" || "$contact_key_value" == "$security_key_value" ]]; then
  echo 'CONTACT_KEY and SECURITY_KEY must differ' >&2
  exit 1
fi
chown root:ninesense /etc/ninesense/guestbook.env
chmod 0640 /etc/ninesense/guestbook.env

if systemctl is-active --quiet ninesense-guestbook.service; then
  service_was_active=1
fi
if systemctl is-active --quiet ninesense-guestbook-backup.timer; then
  backup_timer_was_active=1
fi
systemctl stop ninesense-guestbook-backup.timer >/dev/null 2>&1 || true
if [[ -f /var/lib/ninesense/guestbook.sqlite3 ]]; then
  if [[ -n "$previous_app" ]]; then
    previous_revision=$(runuser -u ninesense -- bash -c \
      "cd '${app_release}/server'; set -a; . /etc/ninesense/guestbook.env; set +a; exec '${app_release}/venv/bin/alembic' -c alembic.ini current" \
      | awk 'NF {print $1}' | tail -n 1)
    [[ -n "$previous_revision" ]]
  fi
  systemctl stop ninesense-guestbook.service >/dev/null 2>&1 || true
  bash -c \
    "set -a; . /etc/ninesense/guestbook.env; set +a; exec '${app_release}/venv/bin/python' -m ninesense_guestbook.cli backup-db --output '${backup_root}/pre-migration.sqlite3'"
fi

runuser -u ninesense -- bash -c \
  "cd '${app_release}/server'; set -a; . /etc/ninesense/guestbook.env; set +a; exec '${app_release}/venv/bin/alembic' -c alembic.ini upgrade head"
migration_applied=1

ln -sfn "$app_release" "${app_root}/current.next"
mv -Tf "${app_root}/current.next" "${app_root}/current"
app_switched=1

install -o root -g root -m 0644 \
  "$app_release/deploy/ninesense-guestbook.service" \
  /etc/systemd/system/ninesense-guestbook.service
install -o root -g root -m 0644 \
  "$app_release/deploy/ninesense-guestbook-backup.service" \
  /etc/systemd/system/ninesense-guestbook-backup.service
install -o root -g root -m 0644 \
  "$app_release/deploy/ninesense-guestbook-backup.timer" \
  /etc/systemd/system/ninesense-guestbook-backup.timer
install -o root -g ninesense -m 0750 \
  "$app_release/deploy/backup-guestbook.sh" \
  /usr/local/sbin/ninesense-guestbook-backup
systemctl daemon-reload
systemctl enable ninesense-guestbook.service >/dev/null
systemctl restart ninesense-guestbook.service

healthy=0
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8812/api/health >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done
[[ $healthy -eq 1 ]]
echo API_LOCAL_OK

install -o root -g root -m 0644 \
  "$app_release/deploy/ninesense-rate-limit.conf" \
  /etc/nginx/conf.d/ninesense-rate-limit.conf
install -o root -g root -m 0644 \
  "$app_release/deploy/ninesense-nginx.conf" \
  /etc/nginx/snippets/ninesense-guestbook.conf
install -o root -g root -m 0644 \
  "$app_release/deploy/ninesense-site.conf" \
  /etc/nginx/sites-available/ninesense.conf
nginx_changed=1
nginx -t

ln -sfn "$static_release" "${static_root}/current.next"
mv -Tf "${static_root}/current.next" "${static_root}/current"
static_switched=1
systemctl reload nginx

nginx_ready=0
for _ in $(seq 1 30); do
  if [[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8811/api/health) == 200 ]]; then
    nginx_ready=1
    break
  fi
  sleep 1
done
[[ $nginx_ready -eq 1 ]]
[[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8811/guestbook/) == 200 ]]
[[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8811/admin/) == 200 ]]
echo NGINX_LOCAL_OK

systemctl start ninesense-guestbook-backup.service
systemctl enable --now ninesense-guestbook-backup.timer >/dev/null

trap - ERR
printf 'DEPLOY_OK release=%s previous_static=%s\n' "$release" "$previous_static"
