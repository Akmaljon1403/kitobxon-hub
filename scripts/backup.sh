#!/usr/bin/env bash
# Kitobxon Hub database backups: encrypted, verified, restorable.
#
#   scripts/backup.sh backup                   -> backup/kitobxon-<UTC time>.dump.gpg
#   scripts/backup.sh verify  FILE             -> checks that FILE decrypts into a valid dump
#   scripts/backup.sh restore FILE             -> restores FILE into $TARGET_DATABASE_URL
#
# Environment:
#   DATABASE_URL         database to back up (backup)
#   TARGET_DATABASE_URL  database to restore into (restore) — preferably a new, empty one
#   PASSPHRASE           encryption password; without it a backup can never be opened
#   PG_TOOLS             "docker" (default) or "local" (pg_dump/pg_restore already installed)
#   PG_IMAGE             Docker image with the PostgreSQL tools; by default the image matching the
#                        database server's major version (e.g. postgres:17), so dumps and restores
#                        always use the server's own tool version
#
# The dump is PostgreSQL's custom format, encrypted with GnuPG (AES-256). Nothing secret is
# printed. Files and photos live in object storage and are backed up there (bucket versioning).
set -euo pipefail
umask 077  # backup files are readable by their owner only

PG_TOOLS="${PG_TOOLS:-docker}"
OUT_DIR="${OUT_DIR:-backup}"
NEWEST_IMAGE=postgres:18  # newest client: connects to any server and reads any archive

die() { echo "error: $*" >&2; exit 1; }
need() { [ -n "${!1:-}" ] || die "$1 is not set"; }

# Runs a PostgreSQL client tool from $IMAGE; connection strings are passed through the
# environment, never on the command line.
IMAGE="${PG_IMAGE:-$NEWEST_IMAGE}"
pg() {
  if [ "$PG_TOOLS" = "local" ]; then
    "$@"
  else
    docker run --rm -i --network host -e DATABASE_URL -e TARGET_DATABASE_URL "$IMAGE" "$@"
  fi
}

# Picks the tools of the server's own major version (a newer pg_restore writes settings an
# older server rejects, an older pg_dump refuses a newer server). $1 names the URL variable.
use_server_version() {
  [ "$PG_TOOLS" = "docker" ] && [ -z "${PG_IMAGE:-}" ] || return 0
  local number
  # shellcheck disable=SC2016
  number=$(IMAGE=$NEWEST_IMAGE pg sh -c "psql -tA \"\$$1\" -c 'SHOW server_version_num'" </dev/null) \
    || die "cannot connect to the database in $1"
  IMAGE="postgres:$((number / 10000))"
  echo "using $IMAGE tools (server version $number)" >&2
}

encrypt() { gpg --batch --yes --quiet --symmetric --cipher-algo AES256 --pinentry-mode loopback --passphrase-fd 3 --output "$1" 3<<<"$PASSPHRASE"; }
decrypt() { gpg --batch --quiet --decrypt --pinentry-mode loopback --passphrase-fd 3 "$1" 3<<<"$PASSPHRASE"; }

verify() {
  local file="$1" entries
  [ -f "$file" ] || die "file not found: $file"
  entries=$(decrypt "$file" | pg pg_restore --list | grep -c "TABLE DATA" || true)
  [ "$entries" -gt 0 ] || die "$file is not a valid backup (wrong password or damaged file)"
  echo "ok: $file contains data for $entries tables"
}

case "${1:-}" in
  backup)
    need DATABASE_URL; need PASSPHRASE
    use_server_version DATABASE_URL
    mkdir -p "$OUT_DIR"
    file="$OUT_DIR/kitobxon-$(date -u +%Y-%m-%d-%H%M).dump.gpg"
    # shellcheck disable=SC2016  # expanded inside the container
    pg sh -c 'pg_dump --format=custom --no-owner --no-acl --dbname "$DATABASE_URL"' | encrypt "$file"
    verify "$file"
    echo "file=$file"
    ;;
  verify)
    need PASSPHRASE
    verify "${2:-}"
    ;;
  restore)
    need TARGET_DATABASE_URL; need PASSPHRASE
    file="${2:-}"
    use_server_version TARGET_DATABASE_URL
    verify "$file"
    if [ "${CONFIRM:-}" != "yes" ]; then
      read -r -p "This replaces the data in the target database. Type yes to continue: " answer
      [ "$answer" = "yes" ] || die "cancelled"
    fi
    # shellcheck disable=SC2016
    decrypt "$file" | pg sh -c 'pg_restore --no-owner --no-acl --clean --if-exists --exit-on-error --dbname "$TARGET_DATABASE_URL"'
    echo "restored $file"
    ;;
  *)
    sed -n '2,8p' "$0"
    exit 2
    ;;
esac
