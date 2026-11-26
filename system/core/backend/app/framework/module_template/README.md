# Module template

The standard module structure (docs/MODULE_STANDARD.md), as files. `app/framework/scaffold.py`
(`python manage.py module new|scaffold|check`) generates modules from it: `backend/` goes to
`app/activities/<activity>/modules/<id>/` (or `app/platform/<id>/`, `app/integrations/<id>/`),
`frontend/` to the matching folder under `system/erp/frontend/src/`.

Files end in `.tmpl` so they are never imported or linted as code. Placeholders: `{{id}}`,
`{{name}}`, `{{name_en}}`, `{{activity}}`, `{{kind}}`, `{{status}}`, `{{variant}}`.
`variants/{{variant}}/` is created once per variant the manifest declares (business modules).
