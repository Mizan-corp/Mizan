# Mizan on the k3s cluster (ADR-011)

`latitude-e6530` runs the k3s control plane and `homie` is a worker; cluster traffic goes over
Tailscale. Production still runs on homie's compose (`deploy/server`); the cluster runs a second
copy of the apps and APIs on latitude, behind the same Cloudflare tunnel, so either machine keeps
Mizan up.

| Piece | Where | Notes |
|---|---|---|
| `api`, `web` | latitude | Same images and settings as compose; Services named like compose's (`api:8000`, `web:8080`), which the tunnel routes to |
| `tunnel` | latitude | A second connector of the `mizan-homie` tunnel (`TUNNEL_TOKEN`), live since 2026-11-14 |
| `pg-bridge` → Service `postgres` | homie | The database stays on homie's compose, published on `127.0.0.1:15432`; the bridge listens on homie's Tailscale address only |
| Uploads | homie's disk over NFS | `/srv/data/mizan/{uploads,private_uploads}` exported to latitude's Tailscale address only (`/etc/exports.d/mizan.exports`) |

Set up outside this repo:
- Secret `mizan-env` (namespace `mizan`): homie's `/srv/mizan/mizan.env`, quotes stripped as compose
  does. Recreate it after changing `mizan.env`.
- `~/.kube/mizan-k3s` on homie for the release runner; the join token is in homie's `~/SECRETS.txt`.

Releases (`.github/workflows/deploy-server.yml`, step "Cluster"): after homie migrates and switches,
the job makes the `ghcr` pull secret from its own token, applies `mizan.yaml` with the commit as the
tag and waits for the rollout. Migrations only ever run on homie.

```bash
export KUBECONFIG=~/.kube/mizan-k3s          # on homie (or a copy of latitude's k3s.yaml)
kubectl -n mizan get pods -o wide
kubectl -n mizan logs deploy/api --tail=50
kubectl -n mizan scale deploy/tunnel --replicas=0   # take latitude out of the tunnel at once
```
