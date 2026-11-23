"""Local development preview bridge. Not an authenticated production API or site service.
Uses the S2 renderer from MIZAN_SITE_BACKEND (path to shared/backend on its branch).
Read one bounded JSON request from stdin and write one HTML document to stdout.
"""
import json
import os
import sys

backend = os.environ.get('MIZAN_SITE_BACKEND')
if not backend:
    raise SystemExit('Set MIZAN_SITE_BACKEND to shared/backend from feat/s2-page-engine')
sys.path.insert(0, backend)
from app.platform.site.render import render_document  # noqa: E402

payload = sys.stdin.read(200001)
if len(payload) > 200000:
    raise SystemExit('Preview payload exceeds 200 KB')
data = json.loads(payload)
if data.get('device') not in ('desktop', 'tablet', 'mobile') or data.get('lang') not in ('ar', 'en'):
    raise SystemExit('Unsupported preview device or language')
print(render_document(data['tree'], data.get('meta', {}), data.get('theme'), data['lang'], data['device']))
