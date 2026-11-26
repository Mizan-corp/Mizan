# Backend Engineering Rules for Antigravity

- **Async Database Sessions:** All SQLAlchemy database operations use async/await (`session.execute`, `session.commit`).
- **Pydantic Validation:** request bodies and responses are Pydantic v2 schemas, never ORM models.
- **Idempotent Migrations:** schema changes are appended to `MIGRATIONS` in `system/core/backend/app/db/migrations.py` (applied by `python manage.py db migrate`, and in production by the release workflow) with idempotent SQL (`IF NOT EXISTS`). New workspace tables get RLS in the same migration.
- **Models match migrations:** a model declares its migration's primary key and database defaults (`server_default`), because `create_all` builds local, CI and on-site tables first.
- **Error Handling:** raise `HTTPException` with an Arabic message in `detail` (English in the admin API and the public developer contracts) and the right status code.
