# Site analytics

The public website's own measurement (ADR-016): cookieless counters, no personal data.

- `models.py`: `site_analytics_daily`, one row per day × kind (`pageview`/`event`) × name × path ×
  language × referring host, with a count. Nothing identifies a visitor: no IP, user agent,
  cookie or id is stored. Migration v108.
- `service.py`: `record` (adds one; called by the website API's `POST /analytics/event`, which
  drops crawlers by user agent and rate-limits by address in memory) and `summary` (the totals
  the admin API's `GET /admoon/website/analytics` returns for the admin panel's Website page).
- Events: `whatsapp_click`, `phone_click`, `contact_submit`, `demo_request`, `signup_start`,
  `signup_complete`. GA4, when configured and accepted by the visitor, gets the same events in the
  browser (website/frontend/src/analytics/).
