"""Human Resources & Payroll Module Models."""
from app.activities.general.modules.hr.models.employee import Employee
from app.activities.general.modules.hr.models.hr_attendance import HrAttendance
from app.activities.general.modules.hr.models.hr_advance import HrAdvance
from app.activities.general.modules.hr.models.payroll import HrEmployee, HrPayrollPeriod, HrPayrollEntry
from app.activities.general.modules.hr.models.hr_shift import HrShift
from app.activities.general.modules.hr.models.hr_settings import HrSettings

__all__ = [
    "Employee",
    "HrAttendance",
    "HrAdvance",
    "HrEmployee",
    "HrPayrollPeriod",
    "HrPayrollEntry",
    "HrShift",
    "HrSettings",
]
