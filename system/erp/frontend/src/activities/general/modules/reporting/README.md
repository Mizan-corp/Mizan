# Reporting engine (screens)

`reporting`, a module of the `general` activity: the fixed reports' screens and the dashboard's
sales widgets. The backend, its rules and permissions:
`system/core/backend/app/activities/general/modules/reporting/README.md`. Custom and scheduled reports
(SRS XMOD-04, CORE-10) are not built yet.

- `api.ts`: the reports' shapes (money as decimal strings) and the widgets' queries.
- `widgets.tsx`: today's revenue, the month's sales, the 14-day trend.
- `components/FinanceReports.tsx`: profit (ledger or documents), cash flow, debts' aging (customers
  and suppliers, an invoice list per customer) and the company overview, each with its filters, CSV
  export and print (the accounting module's `RangeFilters` and `ExportButtons`).
- `components/LedgerReports.tsx`: the day's items and the periodic (weekly / monthly / yearly) ledger.
- `lib.ts`: labels and the rows each report exports (tested in `__tests__/lib.test.ts`).

The page itself is `screens/ReportsPage.tsx` (`/reports`, permission `reports`; the
financial tabs need `reports:finance`, the overview also every branch).
