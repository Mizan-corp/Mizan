"""Consulting: demo data for a new workspace. CATALOG: category -> item names (Arabic trade
names), turned into products by modules/general/inventory/seed.py."""

CATALOG: list[tuple[str, list[str]]] = [
    ('خدمات استشارية', ['استشارة إدارية وتطوير أعمال', 'دراسة جدوى تسويقية', 'إعداد خطة تشغيل سنوية']),
    ('عقود تشغيل وصيانة', ['عقد صيانة شبكات وحواسب', 'عقد دعم فني شهري', 'تأمين ودعم أنظمة سحابية']),
    ('خدمات مهنية ومشاريع', ['إشراف هندسي وتنفيذي', 'خدمات تسويق وحملات رقمية', 'تصميم هوية بصرية متكاملة']),
]
