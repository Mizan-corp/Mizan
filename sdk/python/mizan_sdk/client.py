"""A small client for Mizan's extension API (/ext/v1), standard library only."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.allmizan.live/api/ext/v1"


class MizanError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status, self.detail = status, detail


class MizanClient:
    """client = MizanClient("mzx_…"); client.me(); client.records("visit").create({...})"""

    def __init__(self, token: str, base_url: str = DEFAULT_BASE, timeout: float = 20):
        self.token, self.base, self.timeout = token, base_url.rstrip("/"), timeout

    def request(self, method: str, path: str, body: dict | bytes | None = None, **query) -> dict | None:
        """A JSON body, or bytes sent as they are (a package)."""
        q = {k: v for k, v in query.items() if v is not None}
        url = f"{self.base}{path}" + (f"?{urllib.parse.urlencode(q)}" if q else "")
        raw = isinstance(body, bytes)
        data = body if raw else json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, method=method, data=data,
                                     headers={"Authorization": f"Bearer {self.token}",
                                              "Content-Type": "application/octet-stream" if raw else "application/json",
                                              "Accept": "application/json", "User-Agent": "mizan-sdk/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                raw = res.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read()).get("detail", e.reason)
            except ValueError:
                detail = e.reason
            raise MizanError(e.code, str(detail)) from None

    def me(self) -> dict:
        return self.request("GET", "/me")

    def records(self, entity: str) -> Records:
        return Records(self, entity)

    def customers(self, q: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        return self.request("GET", "/customers", q=q, limit=limit, offset=offset)

    def create_customer(self, name: str, phone: str | None = None, address: str | None = None) -> dict:
        return self.request("POST", "/customers", {"name": name, "phone": phone, "address": address})

    def products(self, q: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        return self.request("GET", "/products", q=q, limit=limit, offset=offset)

    def stock(self, product_id: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        return self.request("GET", "/stock", product_id=product_id, limit=limit, offset=offset)

    def sales(self, since: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        return self.request("GET", "/sales", since=since, limit=limit, offset=offset)


class Records:
    def __init__(self, client: MizanClient, entity: str):
        self.client, self.path = client, f"/records/{urllib.parse.quote(entity)}"

    def list(self, q: str | None = None, page: int = 1) -> dict:
        return self.client.request("GET", self.path, q=q, page=page)

    def get(self, record_id: str) -> dict:
        return self.client.request("GET", f"{self.path}/{record_id}")

    def create(self, values: dict) -> dict:
        return self.client.request("POST", self.path, values)

    def update(self, record_id: str, values: dict) -> dict:
        return self.client.request("PATCH", f"{self.path}/{record_id}", values)

    def delete(self, record_id: str) -> None:
        self.client.request("DELETE", f"{self.path}/{record_id}")
