#!/bin/bash
# Copy the newest local database backup off the machine, encrypted, to Cloudflare R2 (ADR-011).
# Run nightly by mizan-backup.service, after backup.sh. Not run on releases (their backups stay local).
#
#   /srv/mizan/r2.env           R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET (root, 600)
#   /srv/mizan/backup.passphrase  the encryption passphrase (root, 600); a copy is in SECRETS.txt on
#                                 homie and latitude: without it the off-site copies cannot be read
#
# The bucket keeps each object locked for 30 days (it cannot be deleted or overwritten, even with this
# machine's key) and deletes it after 35. The upload is checked by reading the object's size back.
# A failure marks the unit failed and emails the owner.
#
# Restore (any machine with gpg, curl and the passphrase; see deploy/server/README.md):
#   backup-offsite.sh --get <object-name> <out.dump>       # downloads and decrypts
#   backup-offsite.sh --list                                # the objects in the bucket
set -euo pipefail
DIR=${MIZAN_BACKUPS:-/mnt/media/backups/mizan}
R2_ENV=${R2_ENV:-/srv/mizan/r2.env}
PASSFILE=${PASSFILE:-/srv/mizan/backup.passphrase}
ENV_FILE=${ENV_FILE:-/srv/mizan/mizan.env}
# shellcheck disable=SC1090
. "$R2_ENV"
URL="$R2_ENDPOINT/$R2_BUCKET"
s3() { curl -fsS -m 300 --retry 3 --aws-sigv4 "aws:amz:auto:s3" --user "$R2_ACCESS_KEY_ID:$R2_SECRET_ACCESS_KEY" "$@"; }

alert() {
  [ -f "$ENV_FILE" ] || return 0
  ENV_FILE="$ENV_FILE" python3 - "$1" <<'PY' || echo "alert email failed" >&2
import os, smtplib, ssl, sys
from email.message import EmailMessage
env = {}
for line in open(os.environ["ENV_FILE"]):
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.rstrip("\n").split("=", 1)
        env[k] = v.strip().strip("\"'")
m = EmailMessage()
m["Subject"] = "Mizan off-site backup failed"
m["From"] = env["EMAIL_FROM"]; m["To"] = "ammar0xf@gmail.com"
m.set_content(f"{sys.argv[1]}\nSee: journalctl -u mizan-backup on homie. The local backup is unaffected.")
port = int(env.get("EMAIL_SMTP_PORT", "587"))
if port == 465:
    s = smtplib.SMTP_SSL(env["EMAIL_SMTP_HOST"], port, timeout=20, context=ssl.create_default_context())
else:
    s = smtplib.SMTP(env["EMAIL_SMTP_HOST"], port, timeout=20); s.starttls(context=ssl.create_default_context())
s.login(env["EMAIL_SMTP_USER"], env["EMAIL_SMTP_PASSWORD"]); s.send_message(m); s.quit()
PY
}

case "${1:-}" in
  --list)
    s3 "$URL?list-type=2" | python3 -c '
import sys, xml.etree.ElementTree as ET
ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
for c in ET.parse(sys.stdin).getroot().findall("s:Contents", ns):
    print(c.findtext("s:LastModified", "", ns), c.findtext("s:Size", "", ns), c.findtext("s:Key", "", ns), sep="  ")'
    exit 0 ;;
  --get)
    [ $# -eq 3 ] || { echo "usage: $0 --get <object-name> <out.dump>" >&2; exit 64; }
    tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
    s3 -o "$tmp" "$URL/$2"
    gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$PASSFILE" -o "$3" -d "$tmp"
    echo "restored $2 -> $3 ($(du -h "$3" | cut -f1))"
    exit 0 ;;
esac

trap 'alert "The nightly upload to R2 stopped at line $LINENO."' ERR
latest=$(ls -1t "$DIR"/mizan-*.dump | head -1)
name="$(basename "$latest").gpg"
enc=$(mktemp); trap 'rm -f "$enc"' EXIT
gpg --batch --quiet --yes --pinentry-mode loopback --passphrase-file "$PASSFILE" \
    --symmetric --cipher-algo AES256 -o "$enc" "$latest"
s3 -o /dev/null -H "Content-Type: application/octet-stream" -T "$enc" "$URL/$name"
want=$(stat -c %s "$enc")
got=$(s3 -I "$URL/$name" | tr -d '\r' | sed -n 's/^[Cc]ontent-[Ll]ength: //p')
if [ "$got" != "$want" ]; then
  alert "Uploaded $name but R2 reports $got bytes instead of $want."; exit 1
fi
echo "off-site: $name ($want bytes) in r2://$R2_BUCKET"
