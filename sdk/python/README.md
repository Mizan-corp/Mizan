# mizan-sdk

Build for [Mizan](https://allmizan.live): community modules, theme packs and whole business
activities, checked by the same rules the platform uses and signed with a key Mizan certifies;
and talk to Mizan from your module's server.

```bash
pip install https://dev.allmizan.live/sdk/mizan_sdk-0.1.0-py3-none-any.whl
mizan login                       # a CLI token from the portal (dev.allmizan.live/portal/tokens)
mizan module new acme.visits      # a starter module
mizan check acme.visits           # what Mizan would refuse
mizan keys new --team acme        # a signing key, certified for your team
mizan package acme.visits         # acme.visits-0.1.0.mzmo, signed
mizan publish acme.visits         # send it to the marketplace for the Mizan team to review

mizan theme new acme.sunrise      # a theme pack, from Mizan's own theme
mizan activity new acme.laundry   # a whole business activity: modules, variants, theme, menus, demo data
mizan whoami | logout
```

Packages are written in signed **format 2**: the signature covers the package kind (module, activity or
theme) as well as the files, so a signature for one kind cannot be reused as another. Format 1 packages
are still read. Publishing needs a developer account that has accepted the current developer terms
(`POST /developers/terms/accept`, or `accept_terms` at sign-up); listings are free only, and every
submission and listing text change is reviewed by the Mizan team. Compiled (WebAssembly) modules are not
supported yet (design: `docs/wasm-sandbox-design.md`).

`mizan_sdk/manifest.py` is a byte copy of the platform's validator
(`system/core/backend/app/framework/manifest.py`) and `mizan_sdk/themes.py` of Mizan's own theme;
platform tests fail if either drifts. Tests: `python -m pytest` here (also run by
`python manage.py test backend` and CI). Until the package is on PyPI, the release workflow
builds the wheel that `dev.allmizan.live/sdk/` serves.

On your server:

```python
from mizan_sdk import MizanClient, verify_webhook

client = MizanClient("mzx_…")            # the owner gives you this token (module centre → رمز الربط)
client.records("visit").create({"customer": "…", "on": "2026-11-15"})

event = verify_webhook(secret, raw_body, headers["Mizan-Timestamp"], headers["Mizan-Signature"])
```

Docs: https://dev.allmizan.live/docs
