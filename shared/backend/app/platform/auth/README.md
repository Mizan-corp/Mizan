# auth

Sign-in, sessions and users: `router.py` combines `routes/auth.py` (/auth, workspace sign-in), `routes/owner_login.py` (/account, owners on the app's /login) and `routes/users.py` (/users); `services/auth.py`, `services/owners.py`. Token and password helpers are still in `app/core/security.py`.
