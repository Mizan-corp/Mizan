"""Human Resources & Payroll Module Models."""
from app.modules.general.hr.models.employee import Employee
from app.modules.general.hr.models.hr_attendance import HrAttendance
from app.modules.general.hr.models.hr_advance import HrAdvance
from app.modules.general.hr.models.payroll import HrEmployee, HrPayrollPeriod, HrPayrollEntry
from app.modules.general.hr.models.hr_shift import HrShift
from app.modules.general.hr.models.hr_settings import HrSettings

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
