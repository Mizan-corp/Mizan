# tenancy

Workspaces: `service.py` creates them (signup, owner and admin panels, on-site setup). Isolation (the workspace in context, the ORM filter, RLS binding): `context.py`.

The workspace's clock (`clock.py`, PLAT-8): the time zone every workspace works in (Africa/Cairo; no
setting yet, and when one comes it is read there only). `today()`, `current_month()`,
`local_date()`, `day_start()`, `day_bounds()` and `stamp()` decide report days, the current month
of closed periods (`require_open_period`, finance periods, payroll), posting dates of the ledger and
the dates printed on documents. Never use the server's clock (`datetime.now()`, `date.today()`,
`CURRENT_DATE`) for a workspace's day: servers run in UTC. Tests freeze time by replacing `clock.now`.
