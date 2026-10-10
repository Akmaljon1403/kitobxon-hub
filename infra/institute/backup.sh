#!/bin/bash
# Daily encrypted copy of the database and the uploaded files, kept for 14 days.
#   cron:  30 2 * * *  root  /srv/kitobxon-hub/infra/institute/backup.sh
# The password is read from /root/.kitobxon-backup-pass (chmod 600). Without it no copy can be opened.
set -euo pipefail
cd "$(dirname "$0")"
PASS_FILE="${PASS_FILE:-/root/.kitobxon-backup-pass}"
OUT_DIR="${OUT_DIR:-/srv/kitobxon-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d-%H%M)"
umask 077
mkdir -p "$OUT_DIR"
docker compose exec -T db pg_dump -U kitobxon -Fc kitobxon \
  | gpg --batch --yes --quiet --symmetric --cipher-algo AES256 --pinentry-mode loopback --passphrase-file "$PASS_FILE" \
    -o "$OUT_DIR/kitobxon-$STAMP.dump.gpg"
tar -C data -cf - storage \
  | gpg --batch --yes --quiet --symmetric --cipher-algo AES256 --pinentry-mode loopback --passphrase-file "$PASS_FILE" \
    -o "$OUT_DIR/kitobxon-files-$STAMP.tar.gpg"
# The copy must open: a broken backup is found today, not on the day it is needed.
gpg --batch --quiet --decrypt --pinentry-mode loopback --passphrase-file "$PASS_FILE" "$OUT_DIR/kitobxon-$STAMP.dump.gpg" \
  | docker compose exec -T db pg_restore --list >/dev/null
find "$OUT_DIR" -name 'kitobxon-*.gpg' -mtime +"$KEEP_DAYS" -delete
echo "Backup OK: $OUT_DIR/kitobxon-$STAMP.dump.gpg"
