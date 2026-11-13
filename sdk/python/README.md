# mizan-sdk

Build community modules for [Mizan](https://allmizan.live) and talk to Mizan from your module's server.

```bash
pip install https://dev.allmizan.live/sdk/mizan_sdk-0.1.0-py3-none-any.whl
mizan login                       # a CLI token from the portal (dev.allmizan.live/portal/tokens)
mizan module new acme.visits      # a starter module
mizan check acme.visits           # what Mizan would refuse
mizan keys new --team acme        # a signing key, certified for your team
mizan package acme.visits         # acme.visits-0.1.0.mzm, signed
```

On your server:

```python
from mizan_sdk import MizanClient, verify_webhook

client = MizanClient("mzx_…")            # the owner gives you this token (module centre → رمز الربط)
client.records("visit").create({"customer": "…", "on": "2026-11-15"})

event = verify_webhook(secret, raw_body, headers["Mizan-Timestamp"], headers["Mizan-Signature"])
```

Docs: https://dev.allmizan.live/docs
