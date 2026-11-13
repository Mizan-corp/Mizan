# mizan-sdk

Build community modules for [Mizan](https://allmizan.live) and talk to Mizan from your module's server.

```bash
pip install mizan-sdk
mizan module new acme.visits      # a starter module
mizan check acme.visits           # what Mizan would refuse
mizan keys new                    # register the printed public key in the developer portal
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
