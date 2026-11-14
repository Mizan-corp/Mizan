"""Role definitions and default permissions."""

ROLE_LABELS = {
    "admin":         "مدير عام",
    "manager":       "مشرف",
    "cashier":       "كاشير",
    "storekeeper":   "أمين مخازن",
    "accountant":    "محاسب",
    "doctor":        "طبيب",
    "nurse":         "ممرض/ممرضة",
    "receptionist":  "موظف استقبال",
    "lab_tech":      "فني مختبر",
    "pharmacist":    "صيدلي",
}

# Default permissions per role (used when creating new users)
ROLE_DEFAULT_PERMISSIONS = {
    "admin": [
        "pos", "sales", "quotations", "inventory", "operations",
        "customers", "reports", "archive", "payroll", "users",
        "settings", "admin", "shifts", "finance", "clinic", "clinic:view", "clinic:manage",
        "clinic:doctor", "clinic:nurse", "clinic:dispense", "clinic:lab", "clinic:billing",
    ],
    "manager": [
        "pos", "sales", "quotations", "inventory", "operations",
        "customers", "reports", "archive", "shifts", "finance", "settings", "payroll",
        "clinic", "clinic:view", "clinic:manage", "clinic:billing", "clinic:all_patients", "clinic:privacy",
    ],
    "cashier": [
        "pos", "sales", "quotations", "customers", "shifts",
    ],
    "storekeeper": [
        "inventory", "operations", "archive",
    ],
    "accountant": [
        "reports", "finance", "archive", "customers", "inventory", "payroll",
        "clinic:billing",
    ],
    "doctor": [
        "clinic:view", "clinic:doctor",
        "patients", "reports",
    ],
    "nurse": [
        "clinic:view", "clinic:nurse",
        "patients",
    ],
    "receptionist": [
        "clinic:view", "clinic:manage", "clinic:billing",
        "patients", "customers",
    ],
    "lab_tech": [
        "clinic:view", "clinic:lab",
    ],
    "pharmacist": [
        "clinic:view", "clinic:dispense",
        "inventory", "pos",
    ],
}




# What a role name used to grant on its own, besides the list above (before ADR-006 phase 3 the
# clinic and the shift/branch checks looked at role names). Standard roles now hold these as
# permissions, so access stays the same while "permissions decide".
# The clinical roles hold only their own clinic permissions (#131): the umbrella "clinic" (every
# clinic action) stays with admin and manager. doctor: examine, prescribe, order tests (and book
# follow-ups); nurse: ward and queue; receptionist: front desk and billing; lab_tech: results;
# pharmacist: dispensing.
ROLE_IMPLIED_PERMISSIONS = {
    "manager": ["clinic", "supervise"],
    "doctor": ["clinic:view", "clinic:doctor"],
    "nurse": ["clinic:view", "clinic:nurse"],
    "receptionist": ["clinic:view", "clinic:manage", "clinic:billing"],
    "lab_tech": ["clinic:view", "clinic:lab"],
    "pharmacist": ["clinic:view", "clinic:dispense"],
    "accountant": ["clinic:view", "clinic:billing"],
}
FULL_ACCESS_ROLES = ("admin", "owner", "superadmin")  # held everything through a role-name bypass


def standard_permissions(role: str) -> list[str]:
    """A standard role's permissions. admin: every declared permission (no "*")."""
    from app.platform.permissions.access import all_permissions

    if role in FULL_ACCESS_ROLES:
        return all_permissions()
    return sorted(set(ROLE_DEFAULT_PERMISSIONS.get(role, [])) | set(ROLE_IMPLIED_PERMISSIONS.get(role, [])))
