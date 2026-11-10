# Platform

The engine every workspace has, never switched off (ADR-006). Platform modules with a manifest
(`core`, `i18n`, `automation_worker` = the scheduler) are loaded like any module. The other
folders describe engines that still live elsewhere and move here in phase 2, or are still to be
built (`storage_quota`, `custom_fields`).
