# Developers

The developer portal's accounts (ADR-007 D5), served by the website API (`/developers`, see
`website/backend/website_api/routers/developers.py`) at `dev.allmizan.live`.

- `models.py`: `developer_users` (separate from owner accounts), `developer_teams` (a team's handle
  is its modules' namespace), `developer_team_members` (owner or member), `developer_keys`
  (public keys and Mizan's `MZD1` certificates; `revoked_at`), `developer_cli_tokens` (SHA-256
  only). Migration v72.
- `service.py`: signup and sign-in (sessions scoped `developer`, or CLI tokens `mzd_`), teams and
  members, certifying and revoking keys, CLI tokens, `key_revoked` and `verify_upload` (what every
  package upload goes through). Messages in English unless the client asks for Arabic.
