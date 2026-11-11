"""The files service picks its storage by deployment (#114): Vercel Blob when a token is set, the
disk on site and in development, and never the throwaway disk of a Vercel function."""
import asyncio

import pytest
from fastapi import HTTPException

from app.framework import files


def test_vercel_without_a_blob_token_refuses_uploads(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(HTTPException) as e:
        files.backend()
    assert e.value.status_code == 503


def test_the_backend_follows_the_token(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    assert isinstance(files.backend(), files._Disk) and files.backend_name() == "disk"
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_store_secret")
    assert isinstance(files.backend(), files._Blob) and files.backend_name() == "blob"


def test_blob_requests(monkeypatch):
    """What the Blob backend sends: a public upload with a random suffix, deletes by URL, and a
    paged purge by prefix."""
    calls = []
    pages = iter([{"blobs": [{"url": "https://b/1"}], "hasMore": True, "cursor": "c1"},
                  {"blobs": [{"url": "https://b/2"}], "hasMore": False}])

    def fake(method, path, *, body=None, headers=None):
        calls.append((method, path, body, headers or {}))
        if method == "PUT":
            return {"url": "https://store.public.blob.vercel-storage.com/t/x/logo/file-abc.png"}
        if method == "GET":
            return next(pages)
        return {}

    monkeypatch.setattr(files, "_blob_request", fake)
    blob = files._Blob()
    url = asyncio.run(blob.put("t/x/logo/file.png", b"data", "image/png"))
    assert url.endswith("file-abc.png")
    method, path, body, headers = calls[0]
    assert (method, path, body) == ("PUT", "/?pathname=t%2Fx%2Flogo%2Ffile.png", b"data")
    assert headers["x-vercel-blob-access"] == "public" and headers["x-add-random-suffix"] == "1"
    assert headers["x-content-type"] == "image/png"

    assert asyncio.run(blob.delete_prefix("t/x/")) == 2
    deletes = [c for c in calls if c[1] == "/delete"]
    assert [d[2] for d in deletes] == [b'{"urls": ["https://b/1"]}', b'{"urls": ["https://b/2"]}']
    assert "cursor=c1" in [c for c in calls if c[0] == "GET"][1][1]


def test_disk_files_get_unguessable_names_and_stay_in_the_upload_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    disk = files._Disk()
    a = asyncio.run(disk.put("t/w1/logo/file.png", b"one", "image/png"))
    b = asyncio.run(disk.put("t/w1/logo/file.png", b"two", "image/png"))
    assert a != b and a.startswith("/uploads/t/w1/logo/file-")
    asyncio.run(disk.delete([a, "/uploads/../../etc/passwd"]))
    assert not (tmp_path / a.removeprefix("/uploads/")).exists()
    assert (tmp_path / b.removeprefix("/uploads/")).exists()
    assert asyncio.run(disk.delete_prefix("t/w1/")) == 1
    assert not (tmp_path / "t" / "w1").exists()
