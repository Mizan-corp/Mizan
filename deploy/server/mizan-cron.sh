#!/bin/bash
# Run Mizan's scheduled platform jobs from the server's own systemd timers (ADR-011).
#
#   mizan-cron.sh <group> | <job> [<job> ...]
#
# Groups (the same five schedules .github/workflows/jobs.yml used to have; GitHub's scheduler is best
# effort and fired only 4 to 10 times a day instead of about 30):
#   hourly      paymob_reconcile community_webhooks            (Paymob payments whose callback never came, #67)
#   six-hourly  enforce_subscription_expiry                    (trials and subscriptions ending)
#   nightly     auto_close_shifts generate_daily_metrics_digest purge_removed_module_data measure_storage
#               accounting_reconciliation                      (the ledger against the balances, ADR-014 D8)
#   weekly      cleanup_system_stale_data
#   daily       owner_billing_reminders                        (trial and renewal emails to owners, #72)
# Each job is a POST to the API on loopback (no Cloudflare, no second machine), authenticated by
# CRON_SECRET from /srv/mizan/mizan.env, and is safe to repeat. Results go to the journal
# (journalctl -t mizan-cron); a failure marks the unit failed and emails the owner, at most once per
# 6 hours per group.
set -u
ENV_FILE=${ENV_FILE:-/srv/mizan/mizan.env}
API=${API:-http://127.0.0.1:18000/api}
STATE=${STATE:-/var/tmp/mizan-cron}
SECRET=$(sed -n 's/^CRON_SECRET=//p' "$ENV_FILE" | tr -d '"')
[ -n "$SECRET" ] || { logger -t mizan-cron -p user.err "CRON_SECRET missing in $ENV_FILE"; exit 78; }

case "${1:-}" in
  hourly)     jobs="paymob_reconcile community_webhooks" ;;
  six-hourly) jobs="enforce_subscription_expiry" ;;
  nightly)    jobs="auto_close_shifts generate_daily_metrics_digest purge_removed_module_data measure_storage accounting_reconciliation" ;;
  weekly)     jobs="cleanup_system_stale_data" ;;
  daily)      jobs="owner_billing_reminders" ;;
  "")         echo "usage: $0 hourly|six-hourly|nightly|weekly|daily | <job>..." >&2; exit 64 ;;
  *)          jobs="$*" ;;
esac
group=${1:-custom}
mkdir -p "$STATE"
out=$(mktemp)
trap 'rm -f "$out"' EXIT
failed=""

for job in $jobs; do
  if [ "$job" = paymob_reconcile ]; then host=owner-api.allmizan.live; path=/account/cron/paymob-reconcile
  else host=api.allmizan.live; path=/modules/automation/cron/$job; fi
  code=$(curl -s -m 280 -o "$out" -w '%{http_code}' -X POST -H "Host: $host" -H "X-Cron-Secret: $SECRET" "$API$path" 2>/dev/null)
  [ -n "$code" ] || code=000
  msg=$(head -c 240 "$out" | iconv -c -f utf-8 -t utf-8 2>/dev/null | tr '\n' ' ')   # drop a character cut in half (the journal would store a blob)
  if [ "$code" = 200 ]; then logger -t mizan-cron "$job -> 200 $msg"
  else logger -t mizan-cron -p user.err "$job -> $code $msg"; failed="$failed $job($code)"; fi
done

if [ -n "$failed" ]; then
  stamp="$STATE/alerted-$group"
  if [ ! -f "$stamp" ] || [ -n "$(find "$stamp" -mmin +360 2>/dev/null)" ]; then
    touch "$stamp"
    ENV_FILE="$ENV_FILE" python3 - "$group" "$failed" <<'PY' || logger -t mizan-cron -p user.err "failure email could not be sent"
import os, smtplib, ssl, sys
from email.message import EmailMessage
env = {}
for line in open(os.environ["ENV_FILE"]):
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.rstrip("\n").split("=", 1)
        env[k] = v.strip().strip("\"'")
m = EmailMessage()
m["Subject"] = f"Mizan scheduled jobs failed ({sys.argv[1]}):{sys.argv[2]}"
m["From"] = env["EMAIL_FROM"]; m["To"] = "ammar0xf@gmail.com"
m.set_content(f"Group {sys.argv[1]} failed:{sys.argv[2]}\nSee: journalctl -t mizan-cron on homie.\nThe job is retried at its next timer; this email is sent at most once per 6 hours per group.")
port = int(env.get("EMAIL_SMTP_PORT", "587"))
if port == 465:
    s = smtplib.SMTP_SSL(env["EMAIL_SMTP_HOST"], port, timeout=20, context=ssl.create_default_context())
else:
    s = smtplib.SMTP(env["EMAIL_SMTP_HOST"], port, timeout=20); s.starttls(context=ssl.create_default_context())
s.login(env["EMAIL_SMTP_USER"], env["EMAIL_SMTP_PASSWORD"]); s.send_message(m); s.quit()
PY
  fi
  exit 1
fi
exit 0
