"""Crawls a running build of the website (the web image, or nginx over dist/) like a search engine
would, and fails on any SEO regression (ADR-016):

- robots.txt and every sitemap parse; every sitemap URL answers 200 with a unique <title>,
  description and canonical (= the URL itself), one <h1>, hreflang pairs that point back;
- unknown addresses answer 404, trailing slashes and /index.html 301 to the canonical address;
- with --browser, every page opens in Chromium without a hydration error or an uncaught error.

    python3 scripts/crawl-check.py http://127.0.0.1:18092 [--host allmizan.live] [--browser]
"""
import argparse
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

SITE = "https://allmizan.live"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


opener = urllib.request.build_opener(NoRedirect)


def fetch(base: str, host: str, path: str) -> tuple[int, dict, str]:
    req = urllib.request.Request(base + path, headers={"Host": host, "User-Agent": "mizan-crawl-check"})
    try:
        with opener.open(req) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.in_title, self.meta, self.links, self.h1 = "", False, {}, [], 0
        self.html_attrs = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html_attrs = a
        elif tag == "title":
            self.in_title = True
        elif tag == "meta" and (a.get("name") or a.get("property")):
            self.meta[a.get("name") or a.get("property")] = a.get("content", "")
        elif tag == "link":
            self.links.append(a)
        elif tag == "h1":
            self.h1 += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--host", default="allmizan.live")
    ap.add_argument("--browser", action="store_true")
    args = ap.parse_args()
    errors: list[str] = []
    err = errors.append

    status, headers, robots = fetch(args.base, args.host, "/robots.txt")
    if status != 200 or "text/plain" not in headers.get("Content-Type", "") or f"Sitemap: {SITE}/sitemap.xml" not in robots:
        err(f"robots.txt: {status} {headers.get('Content-Type')}")

    status, _, body = fetch(args.base, args.host, "/sitemap.xml")
    index = ET.fromstring(body.encode())
    urls: list[tuple[str, dict]] = []
    for sm in index.findall("s:sitemap/s:loc", NS):
        path = sm.text.replace(SITE, "")
        st, _, xml = fetch(args.base, args.host, path)
        if st != 200:
            err(f"{path}: {st}")
            continue
        for u in ET.fromstring(xml.encode()).findall("s:url", NS):
            loc = u.find("s:loc", NS).text
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", u.find("s:lastmod", NS).text or ""):
                err(f"{loc}: lastmod")
            alts = {x.get("hreflang"): x.get("href") for x in u.findall("x:link", NS)}
            urls.append((loc, alts))

    titles, descriptions, canonicals = {}, {}, {}
    hreflang: dict[str, dict] = {}
    for loc, alts in urls:
        path = loc.replace(SITE, "") or "/"
        st, hdrs, html = fetch(args.base, args.host, path)
        if st != 200:
            err(f"{path}: status {st}")
            continue
        if "noindex" in hdrs.get("X-Robots-Tag", ""):
            err(f"{path}: X-Robots-Tag noindex")
        h = Head()
        h.feed(html)
        canon = next((l.get("href") for l in h.links if l.get("rel") == "canonical"), None)
        desc = h.meta.get("description", "")
        if canon != loc:
            err(f"{path}: canonical {canon}")
        if "noindex" in h.meta.get("robots", ""):
            err(f"{path}: meta robots noindex")
        if not h.title.strip() or not 10 <= len(desc) <= 170:
            err(f"{path}: title/description missing or description length {len(desc)}")
        if h.h1 != 1:
            err(f"{path}: {h.h1} <h1>")
        if not h.meta.get("og:image", "").endswith(".png"):
            err(f"{path}: og:image")
        if '"@context":"https://schema.org"' not in html:
            err(f"{path}: no JSON-LD")
        lang = h.html_attrs.get("lang")
        if lang not in ("ar", "en") or h.html_attrs.get("dir") != ("rtl" if lang == "ar" else "ltr"):
            err(f"{path}: lang/dir {h.html_attrs}")
        for k, store in ((h.title, titles), (desc, descriptions), (canon, canonicals)):
            if k in store:
                err(f"{path}: duplicate of {store[k]}: {k[:60]}")
            store[k] = path
        page_alts = {l.get("hreflang"): l.get("href") for l in h.links if l.get("rel") == "alternate"}
        if page_alts != alts:
            err(f"{path}: hreflang in page {page_alts} != sitemap {alts}")
        hreflang[loc] = page_alts
    for loc, alts in hreflang.items():
        for lang, href in alts.items():
            if lang != "x-default" and hreflang.get(href, {}).get(lang) != href:
                err(f"{loc}: hreflang {lang} -> {href} has no return link")
            if lang != "x-default" and loc not in hreflang.get(href, {}).values():
                err(f"{loc}: {href} doesn't link back")

    for path, want in [("/this-page-does-not-exist", 404), ("/en/nope", 404), ("/blog/nope", 404), ("/docs/nope", 404),
                       ("/pricing/", 301), ("/en/pricing/", 301), ("/index.html", 301), ("/features/details", 301),
                       ("/signup", 200)]:
        st, hdrs, html = fetch(args.base, args.host, path)
        if st != want:
            err(f"{path}: {st}, expected {want}")
        if want == 404 and "<h1" not in html:
            err(f"{path}: the 404 page has no content")
        if path == "/signup" and "noindex" not in hdrs.get("X-Robots-Tag", ""):
            err("/signup: not noindex")

    if args.browser:
        from playwright.sync_api import sync_playwright

        port = args.base.rsplit(":", 1)[-1]
        with sync_playwright() as p:
            b = p.chromium.launch(args=[f"--host-resolver-rules=MAP {args.host} 127.0.0.1:{port}"])
            for loc, _ in urls + [(f"{SITE}/nope", {}), (f"{SITE}/en/nope", {})]:
                page = b.new_page()
                problems: list[str] = []
                page.on("pageerror", lambda e, pr=problems: pr.append(str(e)[:300]))
                page.on("console", lambda m, pr=problems: pr.append(m.text[:300]) if m.type == "error" and "hydrat" in m.text.lower() else None)
                page.goto(loc.replace("https://", "http://"), wait_until="networkidle")
                page.wait_for_timeout(300)
                for pr in problems:
                    err(f"{loc}: browser: {pr}")
                page.close()
            b.close()

    print(f"crawl-check: {len(urls)} sitemap URLs, {len(errors)} problem(s)")
    for e in errors:
        print("  -", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
