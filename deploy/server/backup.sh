#!/bin/sh
# Back up Mizan's database to another partition; keeps the newest 14.
# Run nightly by mizan-backup.timer and before every release (deploy.sh).
set -eu
DIR=${MIZAN_BACKUPS:-/mnt/media/backups/mizan}
mkdir -p "$DIR"
f="$DIR/mizan-$(date +%Y%m%d-%H%M%S).dump"
cd /srv/mizan
docker compose exec -T postgres pg_dump -U mizan -d mizan -Fc > "$f.part"
mv "$f.part" "$f"
ls -1t "$DIR"/mizan-*.dump | tail -n +15 | xargs -r rm -f
echo "backup: $f ($(du -h "$f" | cut -f1))"
