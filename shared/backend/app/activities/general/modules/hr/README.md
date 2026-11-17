# Human Resources & Payroll

سجلات الموظفين، مسيرات الرواتب الشهرية، الحضور والانصراف، والسلف والخصومات.

Module id `hr` (general, business). Depends on `core` and `finance`; posts to the ledger through
events the `accounting` module listens to (ADR-014). Routes keep their historical prefix `/hr`.

## Who can do what

| Permission | Grants | Standard roles |
|---|---|---|
| `payroll` | everything that shows or changes pay: employees, attendance, shifts, settings, advances, payroll entries, calculate and submit a month, the reports | admin, manager, accountant |
| `payroll:approve` | approve a month, reopen an approved month | admin, manager |
| `payroll:pay` | pay an approved month | admin, manager, accountant |

A cashier (or anyone without `payroll`) gets 403 on every `/hr` read. `GET /hr/employees` is also
open to `accounting:view` / `accounting:journal` (picking an employee as a journal line's party),
with names only, no pay. Reports open in a browser tab with a print token of a `payroll` holder.

## The month (`hr_payroll_periods`)

`draft` → `review` (submit) → `approved` → `paid`; an approved month can be reopened to `draft`, a
paid one never.

- Every change to a month takes its period row `FOR UPDATE`: calculate, entry edits, submit,
  approve, pay, reopen. A calculation can't race an approval.
- **Approved or paid = closed.** Its entries (`PUT /hr/payroll/{id}` → 409), attendance (manual
  save → 409; CSV rows of that month are skipped and listed) and advances/deductions/bonuses (add or
  cancel → 409) can't change until the month is reopened. Writers lock the period `FOR SHARE`, so
  the month can't be approved under them.
- Approve records the salaries as one approved expense (`payment_method = 'payroll'`) and the
  period's `approved_amount`, and posts `payroll.approved`. Pay moves exactly `approved_amount` out of
  the chosen safe or wallet (refused with 409 if the entries no longer add up to it) and leaves the
  expense's amount alone; it posts `payroll.paid`. Reopen cancels the expense and posts
  `payroll.reopened` (the approval is reversed).

## Entries (`hr_payroll_entries`)

Calculated by `services/payroll_engine.py` from attendance, the employee's shift and the HR
settings. `base_pay` is the base salary prorated to the hours worked; the net is
`base_pay − lateness − deductions − advances + overtime + extra days + bonus (+ drawer variance)`,
never below zero. A manager's adjustments (`PUT /hr/payroll/{id}`: bonus, deductions, drawer
variance, notes; no `status`) compose the net the same way, while the month is draft or in review.
A recalculation replaces bonus and deductions with the month's records and keeps the drawer
variance and notes.

## Attendance

One row per employee and day. A day saved by hand is `edited`, with `edited_by` (the user's id) and
`edit_reason`; a CSV import never overwrites an edited day. Times are wall-clock times stored with a
UTC marker (the engine drops the zone). CSV: UTF-8, up to 5 MB; an unreadable file is a 400.

## Advances, deductions, bonuses (`hr_advances`)

`record_type` is `سلفة` (cash paid now from a safe or wallet, posted `hr_advance.paid`, deducted from
the month's salary), `خصم` or `مكافأة` (change the salary only). The employee is checked in the
workspace before any money moves. `POST /hr/advances/{id}/cancel` cancels a record of an open month:
an advance's cash goes back to its safe or wallet (`hr_advance_cancel`) and its entry is reversed
(`hr_advance.cancelled`); payroll ignores cancelled records.

## Reports

`/hr/payroll/report/monthly`, `/hr/payroll/report/employee/{id}` (`report_type=detailed|ticket`)
and `/hr/attendance/report` render from the stored entries and their daily breakdown; an approved or
paid month only from them. A month not calculated yet is previewed with the engine. Every text is
HTML-escaped (`printing.routes.h`).

## Settings (`PUT /hr/settings`)

Typed: `days_in_month` (1–31), `grace_period_minutes`, `late_penalty_multiplier`,
`missing_checkout_penalty_hours`, `apply_missing_checkout_penalty`, `overtime_enabled`,
`weekend_paid`; anything else is a 422. A bad stored value falls back to the default. Each
workspace has its own values (`(tenant_id, key)` is unique; migration `v102_b_platform` removed the
baseline's primary key on `key` alone, which let only one workspace save a setting of a name).

The default month, "today" (the last day counted in the current month, an advance's date) and the
dates printed on reports come from the workspace's clock (`app/platform/tenancy/clock.py`), not the
server's.

## Tests

`system/backend/tests/test_hr_ready.py`, `test_money_flows_finance.py`, `test_accounting_postings_2.py`;
`e2e/api/test_hr.py`, `test_periods.py`, `test_security.py`, `test_sessions.py`.

## Known limits

Still hard-coded: Friday weekend, the 5 am day rollover, 4 paid leave days, the Egypt time zone
(HR-12). Lists aren't paged (HR-13). The audit log covers salary changes, entry edits and advances
(HR-14). Unrecovered advances are dropped when the net is clamped at zero (HR-9). Missing screens:
employee edit/deactivate, shifts, settings, CSV import, audit log, adjustments (HR-15).
