#!/usr/bin/env bash
set -euo pipefail
umask 077

backup_root="${BACKUP_ROOT:-/var/backups/ninesense/guestbook}"
daily_dir="$backup_root/daily"
monthly_dir="$backup_root/monthly"
python_bin="${PYTHON_BIN:-/opt/ninesense-guestbook/current/venv/bin/python}"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

[[ -d "$daily_dir" && -w "$daily_dir" ]] || { echo 'daily backup directory is not writable' >&2; exit 1; }
[[ -d "$monthly_dir" && -w "$monthly_dir" ]] || { echo 'monthly backup directory is not writable' >&2; exit 1; }

# backup-db uses SQLite online backup and runs PRAGMA integrity_check before publishing output.
"$python_bin" -m ninesense_guestbook.cli backup-db --output "$daily_dir/guestbook-$timestamp.sqlite3"

find "$daily_dir" -maxdepth 1 -type f -name 'guestbook-*.sqlite3' -mtime +30 -delete
if [[ $(date -u +%d) == 01 ]]; then
  cp --preserve=mode,timestamps "$daily_dir/guestbook-$timestamp.sqlite3" "$monthly_dir/guestbook-${timestamp:0:6}.sqlite3"
fi

mapfile -t monthly < <(find "$monthly_dir" -maxdepth 1 -type f -name 'guestbook-*.sqlite3' -printf '%T@ %p\n' | sort -rn | awk '{print $2}')
if (( ${#monthly[@]} > 12 )); then
  printf '%s\0' "${monthly[@]:12}" | xargs -0r rm --
fi

"$python_bin" -m ninesense_guestbook.cli cleanup

