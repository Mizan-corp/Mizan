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
  `payroll.reopened` (the approval is reversed). A month whose nets are all zero but whose salaries
  were earned (an advance recovered from them) still gets its expense (of 0) and its ledger entry.

## Entries (`hr_payroll_entries`)

Calculated by `services/payroll_engine.py` from attendance, the employee's shift and the HR
settings. `base_pay` is the base salary prorated to the hours worked; the net is
`base_pay − lateness − deductions − advances + overtime + extra days + bonus (+ drawer variance)`,
never below zero. Money is `Decimal` end to end (the engine included), rounded half up to the
piastre where it is stored; hours are numbers of hours. A manager's adjustments (`PUT /hr/payroll/{id}`: bonus, deductions, drawer
variance, notes; no `status`) compose the net the same way, while the month is draft or in review.
A recalculation replaces bonus and deductions with the month's records and keeps the drawer
variance and notes.

## Advances the month can't cover (HR-9)

The advances are deducted from what the month pays (`services/payroll.settle`). When they exceed
it, the net is 0 and the rest is `advances_carried` on the entry. Approving the month makes it an
open advance of the next month (`hr_advances`, record type سلفة, dated the next month's first day,
`carried_from_period_id` = the period; no cash moves, nothing is posted), which that month deducts
like any other. The ledger's approval entry recovers only what was deducted
(`advances − advances_carried`), so the employee's balance in employee advances is exactly what is
carried. A carried advance is cancelled only by reopening the month it came from (its cancel route
is a 409), and that month can't be reopened once the next one is approved or paid. Approving a month
whose carry would land in an approved or paid month is a 409.

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

## Lists

`GET /hr/attendance` and `GET /hr/advances` (filters `employee_id`, `month`) and `GET /hr/audit-log`
(`entity_type`) are paged: `{items, total, page, page_size}`, `page_size` up to 200, newest first.
`GET /hr/employees?include_inactive=true` lists the stopped employees too (with `payroll`), each
with its shift's name. `GET /hr/payroll/{id}/breakdown` gives the entry's days and how its net was
composed.

## Shifts

`GET /hr/shifts` (every shift, with how many active employees work it), `POST`, `PUT /hr/shifts/{id}`
(the fields sent), `DELETE /hr/shifts/{id}` (an unused shift is deleted; one an employee or an
attendance day names is stopped). An employee's shift is chosen from them (`shift_id`, checked in
the workspace: 404 otherwise) or typed (`shift_schedule`, "09:00-17:00"); the chosen one wins. The
engine counts whole hours (the minutes of a shift's times are ignored).

## Reports

`/hr/payroll/report/monthly`, `/hr/payroll/report/employee/{id}` (`report_type=detailed|ticket`)
and `/hr/attendance/report` render from the stored entries and their daily breakdown; an approved or
paid month only from them. A month not calculated yet is previewed with the engine. Every text is
HTML-escaped (`printing.routes.h`). Amounts carry the workspace's currency (store settings
`currency`, an ISO code shown by its Arabic short name; the Egyptian pound when unset); the
attendance report marks the workspace's weekend day; a payslip shows the advance carried to the
next month.

## Settings (`GET` / `PUT /hr/settings`)

Typed (`services/payroll_engine.SETTINGS`), each with its default, the value that used to be fixed
(HR-12): `days_in_month` (26; also the reports' month), `grace_period_minutes` (10),
`late_penalty_multiplier` (2), `missing_checkout_penalty_hours` (2),
`apply_missing_checkout_penalty`, `overtime_enabled`, `weekend_paid` (on), `weekend_day` (Python's
weekday, Friday 4), `day_start_hour` (5: a punch before it belongs to the previous day),
`paid_leave_days` (4 a month), `default_shift_start_hour` / `default_shift_end_hour` (9 and 21, for
an employee without a shift). `GET` returns them all, typed; anything else is a 422, and a bad stored
value falls back to the default. Each workspace has its own values (`(tenant_id, key)` is unique;
migration `v102_b_platform` removed the baseline's primary key on `key` alone, which let only one
workspace save a setting of a name). The manifest's unused `standard_work_hours` was removed (the
hours come from the shifts and the default shift).

The default month, "today" (the last day counted in the current month, an advance's date) and the
dates printed on reports come from the workspace's clock (`app/platform/tenancy/clock.py`), not the
server's.

## Tests

`system/backend/tests/test_hr_ready.py`, `test_c_hr.py`, `test_money_flows_finance.py`, `test_accounting_postings_2.py`;
`e2e/api/test_hr.py`, `test_periods.py`, `test_security.py`, `test_sessions.py`.

## Screens

`/hr` (`system/frontend/src/activities/general/modules/hr/HrPage.tsx`, tabs in `components/`):
employees (create, edit with hire date and shift, stop and bring back, an employee's detailed report
or payslip for a month), attendance (paged by month and employee, a day entered or corrected by
hand, the CSV import with its result, the month's report), advances / deductions / bonuses (paged,
Arabic types and statuses, carried ones marked), shifts, the payroll settings, the audit log.
`/hr/payroll` (`PayrollPage.tsx`): the month's steps with Arabic statuses (a period that can't be
read is an error, not a draft), each entry's adjustments (draft or review) and its days, the carried
advances, reopening with a confirmation. Money shows the workspace's currency.

## Known limits

Still fixed: the Egypt time zone. The engine counts shifts in whole hours. The audit log covers
salary changes, entry edits and advances (HR-14); employees' other edits and stops aren't logged.
The employees list isn't paged (HR-13). A carried advance of an employee who is stopped before the
next month waits in the advances list (and the ledger) until the employee is active again.
