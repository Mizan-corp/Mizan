# Background Automation & Cron Worker

جدولة وأتمتة العمليات اليومية: إغلاق الورديات التلقائي منتصف الليل، متابعة اشتراكات المستأجرين، وإنشاء التقارير والتنبيهات الدورية.

## Module ID
`automation_worker`

## Category
system

## Dependencies
core

## Jobs
`runner.JOB_REGISTRY` lists every job; the server's timers run them by group
(`deploy/server/mizan-cron.sh`). Nightly: `auto_close_shifts`, `generate_daily_metrics_digest`,
`purge_removed_module_data`, `measure_storage`, `accounting_reconciliation`, `recurring_expenses`,
`idempotency_cleanup` (the `Idempotency-Key` answers older than 7 days, every workspace:
`app/framework/idempotency.purge_old`).
