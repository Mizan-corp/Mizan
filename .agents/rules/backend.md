# Backend Engineering Rules for Antigravity

- **Async Database Sessions:** All SQLAlchemy database operations must use async/await (`session.execute`, `session.commit`).
- **Pydantic Validation:** All input request bodies and response schemas must be strictly defined with Pydantic v2.
- **Idempotent Migrations:** Schema changes appended to `scripts/migrate.py` must use idempotent SQL (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
- **Error Handling:** Raise `HTTPException` with localized Arabic messages in the `detail` property and standard HTTP status codes.
