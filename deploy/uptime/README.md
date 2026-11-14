# Uptime (ADR-011)

A Cloudflare Worker, `mizan-uptime`, checks production from outside the server every 5 minutes:
the five apps (200), the four APIs' `/health` (`"status":"ok"`, so a disconnected database counts
as down) and the mail server's ports 587 and 993 (Workers can't open port 25). A failing check is
retried once after 5 s.

- **Alerts** by email through Brevo to `ALERT_TO` (default `ammar0xf@gmail.com`, off the server so
  they arrive when it is down): when something goes down, every hour while it stays down (or when
  the failing set changes), and when everything is back, with how long it lasted.
- **Status page**: https://status.allmizan.live (`/status.json` for the raw state).
- **Manual check**: `https://status.allmizan.live/run?key=<RUN_KEY>`; add `&simulate=down` to test
  the alert emails (the next normal check sends the recovery email).
- **State** in the KV namespace `mizan-uptime` (key `state`).

Deploy or update (stdlib Python, Cloudflare API):

```bash
CF_API_TOKEN=... BREVO_API_KEY=... RUN_KEY=... python deploy/uptime/deploy.py
```

It is not a GitHub workflow: every 5 minutes would use the free Actions minutes several times over.
