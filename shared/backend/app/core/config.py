import warnings

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    APP_ENV: str = "development"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    UPLOAD_DIR: str = "./uploads"
    # Each API overrides this with its own production origins (Vercel env CORS_ORIGINS).
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # system (dev)
        "http://localhost:5174",  # website (dev)
        "http://localhost:5175",  # admin (dev)
        "http://localhost:5176",  # owner panel (dev)
        "http://localhost:3000",
        "http://localhost",
        "https://mizan-co.vercel.app",
        "https://mizan-co-app.vercel.app",
        "https://mizan-co-admin.vercel.app",
        "https://mizan-co-owner.vercel.app",
    ]
    # Vercel deployment URLs of this team's Mizan projects (previews, per-commit URLs).
    # Vercel preview deployments, and the one domain with its workspace subdomains (ADR-008).
    CORS_ORIGIN_REGEX: str = r"^https:\/\/(mizan(-[a-z0-9]+)*-ammar0xfs-projects\.vercel\.app|([a-z0-9-]+\.)?allmizan\.live)$"
    IS_PRODUCTION: bool = False

    # Owner panel: public addresses used in payment redirects and callbacks.
    OWNER_APP_URL: str = "http://localhost:5176"
    OWNER_API_URL: str = "http://localhost:8003"

    # Paymob (Accept). Online payment is off until the keys are set.
    PAYMOB_BASE_URL: str = "https://accept.paymob.com"
    PAYMOB_SECRET_KEY: str = ""
    PAYMOB_PUBLIC_KEY: str = ""
    PAYMOB_HMAC_SECRET: str = ""
    # Comma-separated integration ids to offer (card, wallet, …).
    PAYMOB_INTEGRATION_IDS: str = ""
    # "intention" (Unified Checkout, the default) or "accept" (the Accept API: orders and
    # payment keys, a card page (our iframe, owner/paymob/) and wallet payments). The
    # accept flow uses the dashboard's API key and one integration per method.
    PAYMOB_FLOW: str = "intention"
    PAYMOB_API_KEY: str = ""
    PAYMOB_CARD_INTEGRATION_ID: str = ""
    PAYMOB_WALLET_INTEGRATION_ID: str = ""
    PAYMOB_IFRAME_ID: str = ""
    # While set (comma-separated owner logins), only these owners may pay online: for
    # running production against Paymob's test mode without letting anyone else in.
    PAYMOB_TEST_OWNERS: str = ""

    # Licences for single-device and LAN installs (ADR-005). The private key is set
    # only on the owner API; installs verify with the public key.
    LICENSE_SIGNING_KEY: str = ""
    LICENSE_PUBLIC_KEY: str = ""

    # Server mode: "cloud" (default), or "desktop" / "lan" for on-premise installs.
    MIZAN_MODE: str = "cloud"
    # On-premise: the licence key, the built ERP to serve, and where Mizan Cloud is.
    MIZAN_LICENCE: str = ""
    MIZAN_WEB_DIR: str = ""
    MIZAN_DATA_DIR: str = "./mizan-data"
    MIZAN_CLOUD_URL: str = "https://mizan-co-owner-api.vercel.app/api"
    # Mizan's own details on the receipts it issues to owners (#69): lines such as the legal
    # name, commercial registration, tax number and address, separated by "|". Optional.
    MIZAN_COMPANY_DETAILS: str = ""
    # ⚠️ CORS_ORIGINS must NOT contain wildcard ("*") when credentials are enabled

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    def model_post_init(self, __context):
        if self.SECRET_KEY in ("change-this-in-production-use-random-32-chars", "super-secret-inventory-erp-key-2026-change-in-production"):
            if self.is_production:
                raise RuntimeError("SECRET_KEY must be set to a random value in production! Run: openssl rand -hex 32")
            warnings.warn("SECRET_KEY is still a placeholder! Set a real key via SECRET_KEY env var for production.", stacklevel=2)

    class Config:
        env_file = ".env"


settings = Settings()
