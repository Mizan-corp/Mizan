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
        "*", "pos", "sales", "quotations", "inventory", "operations",
        "customers", "reports", "archive", "payroll", "users",
        "settings", "admin", "shifts", "finance", "clinic", "clinic:view", "clinic:manage",
        "clinic:doctor", "clinic:nurse", "clinic:dispense", "clinic:lab", "clinic:billing",
    ],
    "manager": [
        "pos", "sales", "quotations", "inventory", "operations",
        "customers", "reports", "archive", "shifts", "finance", "settings", "payroll",
        "clinic", "clinic:view", "clinic:manage", "clinic:billing",
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
        "clinic", "clinic:view", "clinic:manage", "clinic:doctor", "clinic:nurse", "clinic:lab",
        "patients", "reports", "finance",
    ],
    "nurse": [
        "clinic", "clinic:view", "clinic:nurse", "clinic:manage",
        "patients",
    ],
    "receptionist": [
        "clinic", "clinic:view", "clinic:manage", "clinic:billing",
        "patients", "customers",
    ],
    "lab_tech": [
        "clinic", "clinic:view", "clinic:manage", "clinic:lab",
    ],
    "pharmacist": [
        "clinic", "clinic:view", "clinic:manage", "clinic:dispense",
        "inventory", "pos",
    ],
}


