"""Drive the local media E2E against the running app on :8877."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, "/tmp/mizan-push/system/core/backend")
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres@127.0.0.1:5544/mizan_media"

import httpx  # noqa: E402

BASE = "http://127.0.0.1:8877"
T2 = "22222222-2222-4222-8222-222222222222"

import struct
import zlib


def make_png(w=64, h=64, rgb=(190, 30, 30)):
    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG = make_png()

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (" :: " + str(detail) if detail else ""))


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        # 1. upload a real PNG
        r = await c.post("/api/site/media", files={"file": ("pixel.png", PNG, "image/png")})
        check("upload real PNG -> 201", r.status_code == 201, r.status_code)
        item = r.json()
        url = item["url"]
        check("url is tenant disk path", url.startswith("/uploads/t/11111111-") and url.endswith(".png"), url)

        # 2. polyglot/declared-mismatch refused
        r = await c.post("/api/site/media", files={"file": ("evil.png", b"<html><script>alert(1)</script>", "image/png")})
        check("polyglot refused 400", r.status_code == 400, r.status_code)
        r = await c.post("/api/site/media", files={"file": ("evil.svg", b"<svg/>", "image/svg+xml")})
        check("svg refused 400", r.status_code == 400, r.status_code)

        # 3. list shows it; other tenant does not see it; no-perm gets 403
        r = await c.get("/api/site/media")
        check("list contains upload", any(i["id"] == item["id"] for i in r.json()["items"]))
        r = await c.get("/api/site/media", headers={"x-e2e-tenant": T2})
        check("other workspace sees empty library", r.json()["items"] == [], r.json())
        r = await c.get("/api/site/media", headers={"x-e2e-noperm": "1"})
        check("no site.manage -> 403", r.status_code == 403, r.status_code)
        r = await c.delete(f"/api/site/media/{item['id']}", headers={"x-e2e-tenant": T2})
        check("other workspace delete -> 404", r.status_code == 404, r.status_code)

        # 4. durable retrieval over HTTP with safe content type
        r = await c.get(url)
        check("served bytes identical", r.status_code == 200 and r.content == PNG, r.status_code)
        check("served content-type image/png", r.headers.get("content-type", "").startswith("image/png"),
              r.headers.get("content-type"))

        # 5. in-use semantics: reference the URL in a page tree -> delete 409
        from app.models.registry import load_all_models
        load_all_models()
        from app.db.base import engine
        from app.platform.site.models import SitePage
        from sqlalchemy.ext.asyncio import async_sessionmaker
        Session = async_sessionmaker(engine, expire_on_commit=False)
        tid = uuid.UUID("11111111-1111-4111-8111-111111111111")
        page_id = uuid.uuid4()
        tree = {"id": "n_root", "type": "section",
                "settings": {"desktop": {"visible": True, "padding": "m", "gap": "m", "background": "background", "max_width": "normal"}},
                "content": {"en": {}},
                "children": [{"id": "n_cols", "type": "columns",
                              "settings": {"desktop": {"visible": True, "columns": 1, "gap": "m", "stack": True, "reverse": False}},
                              "content": {"en": {}},
                              "children": [{"id": "n_col1", "type": "column",
                                            "settings": {"desktop": {"visible": True, "width": "auto", "padding": "m", "align": "start", "background": "background", "rounded": False}},
                                            "content": {"en": {}},
                                            "children": [{"id": "n_img1", "type": "image",
                                                          "settings": {"desktop": {"visible": True, "width": "full", "rounded": True, "art": "none"}},
                                                          "content": {"en": {"src": url, "alt": "pixel"}}}]}]}]}
        async with Session() as db:
            db.add(SitePage(id=page_id, tenant_id=tid, slug="e2e", titles={"en": "E2E"},
                            draft_tree=tree, published_tree=None))
            await db.commit()
        r = await c.delete(f"/api/site/media/{item['id']}")
        check("in-use delete -> 409", r.status_code == 409, r.status_code)

        # 6. render the REAL renderer output and save it for the screenshot.
        # A second upload stays on disk so the screenshot's <img> still resolves after
        # step 7 deletes the first one (that deletion is what step 7 exists to prove).
        from app.platform.site.render import render_page
        html = render_page(tree, "en")
        check("renderer emits img with uploaded src", f'src="{url}"' in html, html[:200])
        r = await c.post("/api/site/media", files={"file": ("stay.png", PNG, "image/png")})
        stay_url = r.json()["url"]
        with open("/tmp/media-e2e-uploads/e2e-page.html", "w") as f:
            f.write("<!doctype html><html><body style='background:#f3f5f2;padding:40px'>"
                    + html.replace(url, stay_url) + "</body></html>")

        # 7. remove the reference -> delete 204 -> file gone from disk and serving
        async with Session() as db:
            p = await db.get(SitePage, page_id)
            p.draft_tree = {"id": "n_root", "type": "section",
                            "settings": {"desktop": {"visible": True, "padding": "m", "gap": "m", "background": "background", "max_width": "normal"}},
                            "content": {"en": {}}, "children": []}
            await db.commit()
        r = await c.delete(f"/api/site/media/{item['id']}")
        check("unused delete -> 204", r.status_code == 204, r.status_code)
        r = await c.get(url)
        check("deleted file no longer served", r.status_code == 404, r.status_code)
        r = await c.get("/api/site/media")
        left = r.json()["items"]
        check("deleted item gone from library", all(i["id"] != item["id"] for i in left), left)

        # 8. in-use guard sees a URL referenced ONLY inside a gallery node's
        # Arabic-only content (not the image node tree, not English).
        from app.platform.site.models import SiteSettings
        r = await c.post("/api/site/media", files={"file": ("gal.png", PNG, "image/png")})
        gal = r.json()
        async with Session() as db:
            p = await db.get(SitePage, page_id)
            p.draft_tree = {"id": "n_root", "type": "section",
                            "settings": {"desktop": {"visible": True, "padding": "m", "gap": "m", "background": "background", "max_width": "normal"}},
                            "content": {"en": {}},
                            "children": [{"id": "n_gal", "type": "gallery",
                                          "settings": {"desktop": {"visible": True}},
                                          "content": {"ar": {"items": [{"src": gal["url"], "alt": "gallery-ar"}]}}}]}
            await db.commit()  # ASCII alt: the scratch cluster is SQL_ASCII; the ar KEY is the point
        r = await c.delete(f"/api/site/media/{gal['id']}")
        check("gallery ar-only reference -> 409", r.status_code == 409, r.status_code)

        # 9. gallery reference removed, but the SAME file is now the site logo in
        # site settings (theme/chrome record) -> still protected.
        async with Session() as db:
            p = await db.get(SitePage, page_id)
            p.draft_tree = {"id": "n_root", "type": "section",
                            "settings": {"desktop": {"visible": True, "padding": "m", "gap": "m", "background": "background", "max_width": "normal"}},
                            "content": {"en": {}}, "children": []}
            db.add(SiteSettings(id=uuid.uuid4(), tenant_id=tid,
                                value={"logo": gal["url"], "theme": {"background": gal["url"]}}))
            await db.commit()
        r = await c.delete(f"/api/site/media/{gal['id']}")
        check("settings logo/theme reference -> 409", r.status_code == 409, r.status_code)

        # 10. settings reference removed -> the delete finally goes through.
        async with Session() as db:
            from sqlalchemy import delete as sqldelete
            await db.execute(sqldelete(SiteSettings).where(SiteSettings.tenant_id == tid))
            await db.commit()
        r = await c.delete(f"/api/site/media/{gal['id']}")
        check("unreferenced gallery/logo file -> 204", r.status_code == 204, r.status_code)

    await engine.dispose()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


asyncio.run(main())
