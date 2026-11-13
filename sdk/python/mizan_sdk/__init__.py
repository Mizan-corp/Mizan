"""mizan-sdk: build community modules for Mizan (ADR-007) and talk to Mizan from your server.

- `mizan` command: module new, check, keys new, package (see `mizan --help`).
- `MizanClient`: the extension API (/ext/v1) with your installation token.
- `verify_webhook`: check a webhook's signature.
Docs: https://dev.allmizan.live/docs
"""
from mizan_sdk.client import MizanClient, MizanError
from mizan_sdk.webhooks import WebhookError, verify_webhook

__version__ = "0.1.0"
__all__ = ["MizanClient", "MizanError", "WebhookError", "verify_webhook", "__version__"]
