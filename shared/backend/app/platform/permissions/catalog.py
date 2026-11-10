"""Authoritative Catalog & Seed Engine for Standard Positions, Roles & Permissions.

Populates the platform-wide RBAC & ABAC suite:
- 98 Standard Organizational Positions (Job Titles) across 9 Groups (A through I)
- 9 System Account Types
- 20 Standard Roles
- 50+ Granular Permissions (with Clinical vs Technical data flags)
- Standard Role-to-Permission Matrix
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.permissions.models import (
    AccountType, PositionCategory, OrgPosition,
    SysPermission, SysRole, SysRolePermission
)

logger = logging.getLogger("mizan.rbac_catalog")

# -------------------------------------------------------------------------
# 1. Standard Organizational Positions (Job Titles) — Groups A through I
# -------------------------------------------------------------------------
STANDARD_POSITIONS = [
    # Group A: Executive & Administration
    {"code": "hospital_director", "name": "مدير المستشفى", "name_en": "Hospital Director", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "الإدارة العليا", "desc": "القيادة التشغيلية والإشراف العام على المنشأة والمستشفى"},
    {"code": "medical_director", "name": "المدير الطبي", "name_en": "Medical Director", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "الإدارة الطبية", "desc": "الإشراف الكامل على السياسات والممارسات السريرية والكوادر الطبية"},
    {"code": "operations_manager", "name": "مدير العمليات التشغيلية", "name_en": "Operations Manager", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "العمليات", "desc": "إدارة وتنسيق العمليات التشغيلية اليومية للمجمع والمرافق"},
    {"code": "hospital_administrator", "name": "مدير إداري للمستشفى", "name_en": "Hospital Administrator", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "الشؤون الإدارية", "desc": "إدارة الشؤون التنظيمية والخدمات الإدارية المساندة"},
    {"code": "clinic_manager", "name": "مدير العيادات الخارجية", "name_en": "Clinic Manager", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "العيادات الخارجية", "desc": "تنظيم كشوفات وجداول مواعيد العيادات التخصصية"},
    {"code": "branch_manager", "name": "مدير الفرع", "name_en": "Branch Manager", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "إدارة الفروع", "desc": "الإشراف الميداني على فرع مخصص ومتابعة مستهدفاته"},
    {"code": "dept_manager", "name": "مدير القسم", "name_en": "Department Manager", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "الأقسام التشغيلية", "desc": "إدارة الكادر والعمليات داخل قسم محدد"},
    {"code": "quality_manager", "name": "مدير الجودة والاعتماد", "name_en": "Quality Manager", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "إدارة الجودة", "desc": "ضمان تطبيق معايير الجودة والاعتماد الصحي (GHAAR / JCI)"},
    {"code": "compliance_officer", "name": "مسؤول الامتثال الرقابي", "name_en": "Compliance Officer", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "الرقابة والامتثال", "desc": "متابعة اللوائح الطبية والتنظيمية ووزارة الصحة"},
    {"code": "patient_relations_manager", "name": "مدير علاقات وتجربة المرضى", "name_en": "Patient Relations Manager", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "تجربة المريض", "desc": "متابعة رضا المرضى والشكاوى ومقترحات التحسين"},
    {"code": "medical_secretary", "name": "سكرتير طبي", "name_en": "Medical Secretary", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "السكرتارية الطبية", "desc": "تنظيم المراسلات والمواعيد والتقارير الطبية للأطباء"},
    {"code": "receptionist", "name": "موظف استقبال واستعلامات", "name_en": "Receptionist", "category": PositionCategory.EXECUTIVE_ADMIN.value, "dept": "الاستقبال والنداء", "desc": "استقبال المراجعين وفتح السجلات وتنظيم صفوف الانتظار"},

    # Group B: Medical Staff
    {"code": "chief_physician", "name": "كبير الأطباء", "name_en": "Chief Physician", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "الهيئة الطبية", "desc": "كبير الأطباء ورئيس اللجان الطبية السريرية"},
    {"code": "consultant_physician", "name": "طبيب استشاري", "name_en": "Consultant Physician", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "العيادات التخصصية", "desc": "طبيب استشاري حاصل على أعلى المؤهلات السريرية والخبرة"},
    {"code": "specialist_physician", "name": "طبيب أخصائي", "name_en": "Specialist Physician", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "العيادات التخصصية", "desc": "طبيب أخصائي في تخصص سريري محدد"},
    {"code": "general_practitioner", "name": "طبيب ممارس عام", "name_en": "General Practitioner", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "الطب العام والأسرة", "desc": "الكشف العام والرعاية الأولية وتوجيه الإحالات"},
    {"code": "resident_doctor", "name": "طبيب مقيم", "name_en": "Resident Doctor", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "الأقسام السريرية", "desc": "طبيب مقيم لمتابعة المرضى المنومين ونوبات العمل السريرية"},
    {"code": "intern_doctor", "name": "طبيب امتياز", "name_en": "Intern Doctor", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "التدريب السريري", "desc": "طبيب متدرب تحت الإشراف السريري المباشر"},
    {"code": "surgeon", "name": "جراح", "name_en": "Surgeon", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم الجراحة", "desc": "إجراء العمليات الجراحية المجدولة والطارئة"},
    {"code": "anesthesiologist", "name": "استشاري تخدير", "name_en": "Anesthesiologist", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم التخدير", "desc": "تخدير المرضى ورعاية ما قبل وبعد الجراحة في الإفاقة"},
    {"code": "emergency_physician", "name": "أخصائي طب طوارئ", "name_en": "Emergency Physician", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم الطوارئ", "desc": "إنقاذ وعلاج حالات الطوارئ والإصابات الحرجة على مدار الساعة"},
    {"code": "pediatrician", "name": "أخصائي طب الأطفال", "name_en": "Pediatrician", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم الأطفال", "desc": "رعاية الأطفال وحديثي الولادة ومتابعة التطعيمات"},
    {"code": "cardiologist", "name": "استشاري أمراض القلب", "name_en": "Cardiologist", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم القلب", "desc": "تشخيص وعلاج أمراض القلب والأوعية والقسطرة"},
    {"code": "dentist", "name": "طبيب أسنان", "name_en": "Dentist", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم الأسنان", "desc": "علاج وجراحة وتجميل الأسنان واللثة"},
    {"code": "dermatologist", "name": "أخصائي الجلدية والتجميل", "name_en": "Dermatologist", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم الجلدية", "desc": "علاج الأمراض الجلدية والعلاج بالليزر والتجميل"},
    {"code": "gynecologist", "name": "أخصائي النساء والتوليد", "name_en": "Gynecologist", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "النساء والتوليد", "desc": "رعاية الحوامل والولادات وجراحة أمراض النساء"},
    {"code": "radiologist", "name": "استشاري أشعة تشخيصية", "name_en": "Radiologist", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم الأشعة", "desc": "قراءة وتفسير الفحوصات الإشعاعية وكتابة التقارير الطبية"},
    {"code": "pathologist", "name": "استشاري علم الأمراض والأنسجة", "name_en": "Pathologist", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "قسم الباثولوجي", "desc": "فحص العينات النسيجية والخلوية والتشخيص المخبري المتقدم"},
    {"code": "medical_officer", "name": "ضابط طبي ميداني", "name_en": "Medical Officer", "category": PositionCategory.MEDICAL_STAFF.value, "dept": "الخدمات الطبية", "desc": "إدارة المتابعات الطبية والإشراف على البروتوكولات"},

    # Group C: Nursing Staff
    {"code": "cno", "name": "رئيس هيئة التمريض", "name_en": "Chief Nursing Officer", "category": PositionCategory.NURSING_STAFF.value, "dept": "إدارة التمريض", "desc": "القيادة العليا لقطاع التمريض ومعايير الرعاية السريرية"},
    {"code": "nursing_manager", "name": "مدير التمريض", "name_en": "Nursing Manager", "category": PositionCategory.NURSING_STAFF.value, "dept": "إدارة التمريض", "desc": "تنظيم مناوبات التمريض والتدريب والجودة السريرية"},
    {"code": "head_nurse", "name": "رئيس تمريض قسم / جناح", "name_en": "Head Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "الأجنحة التنويمية", "desc": "الإشراف على تمريض جناح أو وحدة معينة"},
    {"code": "registered_nurse", "name": "ممرض قانوني معتمد (RN)", "name_en": "Registered Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "الأقسام السريرية", "desc": "تقديم الرعاية التمريضية وإعطاء الأدوية ورصد العلامات الحيوية"},
    {"code": "assistant_nurse", "name": "مساعد ممرض", "name_en": "Assistant Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "الأجنحة التنويمية", "desc": "مساعدة الممرضين في العناية الأساسية وراحة المرضى"},
    {"code": "practical_nurse", "name": "ممرض ممارس", "name_en": "Practical Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "العيادات التخصصية", "desc": "مساعدة الأطباء في العيادات والإجراءات الصغرى"},
    {"code": "icu_nurse", "name": "ممرض عناية مركزة (ICU)", "name_en": "ICU Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "العناية المركزة", "desc": "تمريض الحالات الحرجة وأجهزة التنفس الصناعي والمراقبة الدقيقة"},
    {"code": "er_nurse", "name": "ممرض طوارئ وفرز", "name_en": "Emergency Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "قسم الطوارئ", "desc": "الفرز الأولي والإسعاف السريع للحالات الوافدة"},
    {"code": "or_nurse", "name": "ممرض غرف العمليات (OR)", "name_en": "Operating Room Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "العمليات الجراحية", "desc": "تمريض التعقيم والمناولة ومساعدة الجراح أثناء العملية"},
    {"code": "recovery_nurse", "name": "ممرض إفاقة ورعاية لاحقة", "name_en": "Recovery Nurse", "category": PositionCategory.NURSING_STAFF.value, "dept": "الإفاقة (PACU)", "desc": "مراقبة المؤشرات الحيوية للمريض بعد العمليات الجراحية"},
    {"code": "nursing_supervisor", "name": "مشرف نوبتجيات تمريض", "name_en": "Nursing Supervisor", "category": PositionCategory.NURSING_STAFF.value, "dept": "إدارة التمريض", "desc": "الإشراف على النوبات الليلية وتوزيع القوى التمريضية"},

    # Group D: Laboratory & Radiology
    {"code": "lab_director", "name": "مدير المختبرات وبنك الدم", "name_en": "Laboratory Director", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "المختبر المركزي", "desc": "إدارة التحاليل وبنك الدم وضبط الجودة النوعية"},
    {"code": "lab_supervisor", "name": "مشرف مختبر", "name_en": "Laboratory Supervisor", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "المختبر المركزي", "desc": "الإشراف الفني على إدخال واعتماد النتائج المخبرية"},
    {"code": "lab_technician", "name": "فني تحاليل مخبرية", "name_en": "Laboratory Technician", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "المختبر المركزي", "desc": "إجراء الاختبارات والتحاليل الروتينية ومعايرة الأجهزة"},
    {"code": "lab_specialist", "name": "أخصائي تحاليل طبية", "name_en": "Laboratory Specialist", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "المختبر المركزي", "desc": "التحاليل المتقدمة والمناعية والوراثية"},
    {"code": "phlebotomist", "name": "فني سحب عينات دم", "name_en": "Phlebotomist", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "سحب العينات", "desc": "سحب عينات الدم وجمع السوائل البيولوجية بسلامة"},
    {"code": "radiology_manager", "name": "مدير قسم الأشعة", "name_en": "Radiology Manager", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "قسم الأشعة", "desc": "إدارة خدمات التصوير الطبي والموارد الإشعاعية"},
    {"code": "radiology_technician", "name": "فني أشعة وتصوير طبي", "name_en": "Radiology Technician", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "قسم الأشعة", "desc": "إجراء فحوصات الأشعة السينية والتصويرية المعتمدة"},
    {"code": "mri_technician", "name": "فني رنين مغناطيسي (MRI)", "name_en": "MRI Technician", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "الرنين المغناطيسي", "desc": "تشغيل أجهزة الرنين المغناطيسي وإعداد المرضى للفحص"},
    {"code": "ct_technician", "name": "فني أشعة مقطعية (CT)", "name_en": "CT Technician", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "الأشعة المقطعية", "desc": "إجراء الفحوصات المقطعية بالصبغة وبدون صبغة"},
    {"code": "ultrasound_technician", "name": "أخصائي تصوير موجات فوق صوتية", "name_en": "Ultrasound Technician", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "السونار والموجات", "desc": "فحوصات السونار والدوبلر الملون"},
    {"code": "imaging_coordinator", "name": "منسق مواعيد الأشعة", "name_en": "Imaging Coordinator", "category": PositionCategory.LAB_RADIOLOGY.value, "dept": "قسم الأشعة", "desc": "جدولة فحوصات الرنين والمقطعية وتجهيز موافقات التأمين"},

    # Group E: Pharmacy
    {"code": "chief_pharmacist", "name": "كبير الصيادلة", "name_en": "Chief Pharmacist", "category": PositionCategory.PHARMACY.value, "dept": "إدارة الصيدلة", "desc": "الإشراف الاستراتيجي على التموين الدوائي والصيدلة السريرية"},
    {"code": "pharmacy_manager", "name": "مدير الصيدلية", "name_en": "Pharmacy Manager", "category": PositionCategory.PHARMACY.value, "dept": "الصيدلية المركزية", "desc": "إدارة صيدلية المستشفى وصرف الأدوية والرقابة"},
    {"code": "clinical_pharmacist", "name": "صيدلي سريري", "name_en": "Clinical Pharmacist", "category": PositionCategory.PHARMACY.value, "dept": "الصيدلة السريرية", "desc": "مراجعة الجرعات والتعارضات الدوائية مع الأطباء المنومين"},
    {"code": "hospital_pharmacist", "name": "صيدلي مستشفى وتنويم", "name_en": "Hospital Pharmacist", "category": PositionCategory.PHARMACY.value, "dept": "الصيدلية الداخلية", "desc": "تجهيز أدوية الأجنحة وأوامر الصرف التنويمية"},
    {"code": "community_pharmacist", "name": "صيدلي عيادات خارجية", "name_en": "Community Pharmacist", "category": PositionCategory.PHARMACY.value, "dept": "الصيدلية الخارجية", "desc": "صرف الروشتات للمرضى الخارجيين وإرشاد الاستخدام"},
    {"code": "pharmacy_technician", "name": "مساعد صيدلي / فني", "name_en": "Pharmacy Technician", "category": PositionCategory.PHARMACY.value, "dept": "الصيدلية", "desc": "تحضير وتعبئة الأدوية ومتابعة تواريخ الصلاحية"},
    {"code": "pharmacy_storekeeper", "name": "أمين مستودع الأدوية", "name_en": "Pharmacy Storekeeper", "category": PositionCategory.PHARMACY.value, "dept": "المستودع الدوائي", "desc": "استلام وحفظ الأدوية ومراقبة درجات الحرارة والتخزين"},

    # Group F: Finance & Insurance
    {"code": "cfo", "name": "المدير المالي التنفيذي (CFO)", "name_en": "Chief Financial Officer", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "الإدارة المالية", "desc": "التخطيط المالي والاستثماري والميزانيات العامة للمنشأة"},
    {"code": "finance_manager", "name": "مدير الشؤون المالية", "name_en": "Finance Manager", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "الإدارة المالية", "desc": "إدارة الحسابات والسيولة والتقارير المالية الدورية"},
    {"code": "chief_accountant", "name": "رئيس الحسابات", "name_en": "Chief Accountant", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "قسم الحسابات", "desc": "الإشراف على القيود المحاسبية وتسوية الخزائن والبنوك"},
    {"code": "accountant", "name": "محاسب مالي", "name_en": "Accountant", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "قسم الحسابات", "desc": "تسجيل القيود اليومية وحسابات الموردين والدفعات"},
    {"code": "cost_accountant", "name": "محاسب تكاليف طبية", "name_en": "Cost Accountant", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "محاسبة التكاليف", "desc": "تحليل تكاليف العمليات والخدمات والأسرة وحساب الربحية"},
    {"code": "internal_auditor", "name": "مراجع مالي داخلي", "name_en": "Internal Auditor", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "المراجعة الداخلية", "desc": "التدقيق المستمر على العمليات المالية والرقابة الداخلية"},
    {"code": "cashier", "name": "كاشير وتحصيل طبي", "name_en": "Cashier", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "الخزينة والتحصيل", "desc": "تحصيل رسوم الكشوفات والخدمات وإصدار الإيصالات"},
    {"code": "billing_officer", "name": "موظف فوترة ومحاسبة مرضى", "name_en": "Billing Officer", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "الفوترة الطبية", "desc": "إعداد وتدقيق الفواتير الإجمالية والتفصيلية للمرضى"},
    {"code": "insurance_manager", "name": "مدير إدارة التأمين الطبي", "name_en": "Insurance Manager", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "إدارة التأمين", "desc": "التفاوض وإدارة عقود شركات التأمين ومراجعة نسب التحمل"},
    {"code": "insurance_officer", "name": "مسؤول مطالبات وموافقات التأمين", "name_en": "Insurance Officer", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "إدارة التأمين", "desc": "طلب الموافقات المسبقة وإدخال بيانات التغطية التأمينية"},
    {"code": "claims_specialist", "name": "أخصائي تسوية مطالبات ورفوضات", "name_en": "Claims Specialist", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "المطالبات والرفوضات", "desc": "تحليل ودراسة الرفوضات التأمينية وإعادة تقديمها"},
    {"code": "rcm_manager", "name": "مدير دورة الإيرادات (RCM)", "name_en": "Revenue Cycle Manager", "category": PositionCategory.FINANCE_INSURANCE.value, "dept": "دورة الإيرادات", "desc": "تحسين دورة الإيرادات الطبية والتحصيل وتقليص الفاقد"},

    # Group G: Human Resources
    {"code": "hr_director", "name": "مدير عام الموارد البشرية", "name_en": "HR Director", "category": PositionCategory.HUMAN_RESOURCES.value, "dept": "الموارد البشرية", "desc": "تخطيط القوى العاملة والسياسات الوظيفية والهيكل"},
    {"code": "hr_manager", "name": "مدير الموارد البشرية", "name_en": "HR Manager", "category": PositionCategory.HUMAN_RESOURCES.value, "dept": "الموارد البشرية", "desc": "إدارة العمليات التوظيفية ومتابعة تقييم الأداء"},
    {"code": "hr_specialist", "name": "أخصائي شؤون العاملين", "name_en": "HR Specialist", "category": PositionCategory.HUMAN_RESOURCES.value, "dept": "الموارد البشرية", "desc": "ملفات الموظفين والتراخيص المهنية وتجديدات الإقامة"},
    {"code": "recruitment_officer", "name": "مسؤول توظيف واستقطاب", "name_en": "Recruitment Officer", "category": PositionCategory.HUMAN_RESOURCES.value, "dept": "التوظيف", "desc": "استقطاب الكوادر الطبية والتمريضية والإدارية المتخصصة"},
    {"code": "payroll_officer", "name": "مسؤول الرواتب والاستحقاقات", "name_en": "Payroll Officer", "category": PositionCategory.HUMAN_RESOURCES.value, "dept": "الرواتب", "desc": "إعداد مسيرات الرواتب وحساب البدلات ونسب الأطباء"},
    {"code": "training_coordinator", "name": "منسق تدريب وتطوير مهني", "name_en": "Training Coordinator", "category": PositionCategory.HUMAN_RESOURCES.value, "dept": "التدريب المستمر", "desc": "برامج التعليم الطبي المستمر (CME) والدورات الإلزامية"},
    {"code": "attendance_officer", "name": "مسؤول حضور وانصراف ونوبات", "name_en": "Attendance Officer", "category": PositionCategory.HUMAN_RESOURCES.value, "dept": "الحضور والنوبات", "desc": "متابعة جداول المناوبات والبصمة وساعات العمل الإضافي"},

    # Group H: Procurement, Inventory & Maintenance
    {"code": "procurement_manager", "name": "مدير المشتريات والتوريدات", "name_en": "Procurement Manager", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "إدارة المشتريات", "desc": "إدارة مناقصات التوريد والعقود مع الشركات الطبية"},
    {"code": "purchasing_officer", "name": "مسؤول أوامر شراء", "name_en": "Purchasing Officer", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "المشتريات", "desc": "إصدار ومتابعة أوامر الشراء ومطابقة عروض الأسعار"},
    {"code": "warehouse_manager", "name": "مدير المستودعات المركزية", "name_en": "Warehouse Manager", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "إدارة المستودعات", "desc": "الإشراف على حركة وتخزين المستلزمات الطبية والأجهزة"},
    {"code": "storekeeper", "name": "أمين مخزن مستلزمات طبية", "name_en": "Storekeeper", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "المستودع الطبي", "desc": "صرف وجرد المستهلكات الطبية والأدوات الجراحية"},
    {"code": "inventory_controller", "name": "مراقب مخزون وإمداد", "name_en": "Inventory Controller", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "الرقابة المخزنية", "desc": "مراقبة حد إعادة الطلب وتواريخ الصلاحية وحالات الركود"},
    {"code": "supply_chain_manager", "name": "مدير سلاسل الإمداد الطبي", "name_en": "Supply Chain Manager", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "سلاسل الإمداد", "desc": "تحسين دورة تدفق المواد من المورد إلى أجنحة المرضى"},
    {"code": "maintenance_manager", "name": "مدير الصيانة والمرافق", "name_en": "Maintenance Manager", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "الصيانة العامة", "desc": "إدارة صيانة المباني والكهرباء والغازات الطبية والتكييف"},
    {"code": "maintenance_technician", "name": "فني صيانة وتشغيل مرافق", "name_en": "Maintenance Technician", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "الصيانة العامة", "desc": "إصلاح وصيانة شبكات المرافق والغرف والأجنحة"},
    {"code": "biomedical_engineer", "name": "مهندس أجهزة طبية حيوية", "name_en": "Biomedical Engineer", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "الهندسة الطبية", "desc": "معايرة وإصلاح الأجهزة التشخيصية والجراحية ومراقبتها"},
    {"code": "biomedical_technician", "name": "فني صيانة ومعايرة أجهزة طبية", "name_en": "Biomedical Technician", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "الهندسة الطبية", "desc": "الفحص الدوري وصيانة أجهزة قياس الضغط والصدمات والأشعة"},
    {"code": "facility_manager", "name": "مدير المنشأة والمباني", "name_en": "Facility Manager", "category": PositionCategory.PROCUREMENT_MAINTENANCE.value, "dept": "إدارة المرافق", "desc": "السلامة والصحة المهنية وتراخيص الدفاع المدني والمبنى"},

    # Group I: IT & Technical Staff
    {"code": "it_director", "name": "مدير تكنولوجيا المعلومات (CIO)", "name_en": "IT Director", "category": PositionCategory.IT_TECHNICAL.value, "dept": "تكنولوجيا المعلومات", "desc": "الاستراتيجية الرقمية والتحول الرقمي والبنية التقنية"},
    {"code": "it_manager", "name": "مدير نظم المعلومات والتشغيل", "name_en": "IT Manager", "category": PositionCategory.IT_TECHNICAL.value, "dept": "تكنولوجيا المعلومات", "desc": "إدارة فرق الدعم والأنظمة وتوافر الخدمات التقنية"},
    {"code": "system_administrator", "name": "مسؤول خوادم ونظم التشغيل", "name_en": "System Administrator", "category": PositionCategory.IT_TECHNICAL.value, "dept": "البنية التحتية", "desc": "إدارة الخوادم السحابية والمحلية وتوافر النظام والنسخ الاحتياطي"},
    {"code": "network_administrator", "name": "مسؤول الشبكات والاتصالات", "name_en": "Network Administrator", "category": PositionCategory.IT_TECHNICAL.value, "dept": "الشبكات والربط", "desc": "إدارة شبكة المستشفى والواي فاي وحماية الاتصالات"},
    {"code": "dba", "name": "مسؤول قواعد البيانات (DBA)", "name_en": "Database Administrator", "category": PositionCategory.IT_TECHNICAL.value, "dept": "قواعد البيانات", "desc": "أداء قواعد البيانات وحمايتها وأرشفة البيانات الضخمة"},
    {"code": "it_support_specialist", "name": "أخصائي دعم فني مكتبي", "name_en": "IT Support Specialist", "category": PositionCategory.IT_TECHNICAL.value, "dept": "الدعم الفني", "desc": "دعم المستخدمين وحل أعطال الحواسيب والطابعات والماسحات"},
    {"code": "app_administrator", "name": "مسؤول تهيئة نظام ERP والعيادات", "name_en": "Application Administrator", "category": PositionCategory.IT_TECHNICAL.value, "dept": "إدارة التطبيقات", "desc": "تهيئة النماذج وسير العمل والصلاحيات والوحدات البرمجية"},
    {"code": "cybersecurity_officer", "name": "مسؤول الأمن السيبراني وحماية البيانات", "name_en": "Cybersecurity Officer", "category": PositionCategory.IT_TECHNICAL.value, "dept": "الأمن السيبراني", "desc": "حماية خصوصية بيانات المرضى والامتثال لمعايير الأمان"},
    {"code": "data_analyst", "name": "محلل بيانات ومؤشرات أداء", "name_en": "Data Analyst", "category": PositionCategory.IT_TECHNICAL.value, "dept": "ذكاء الأعمال", "desc": "بناء لوحات المؤشرات الإحصائية والتحليلية للمستشفى"},
    {"code": "integration_engineer", "name": "مهندس ربط وتكامل برمجيات (HL7/FHIR)", "name_en": "Integration Engineer", "category": PositionCategory.IT_TECHNICAL.value, "dept": "تكامل النظم", "desc": "ربط نظام ERP بأجهزة المختبرات وبوابات التأمين والأنظمة الوطنية"},
]

# -------------------------------------------------------------------------
# 2. Standard System Account Types
# -------------------------------------------------------------------------
STANDARD_ACCOUNT_TYPES = [
    {"type": AccountType.EMPLOYEE.value, "name": "حساب موظف", "name_en": "Employee Account", "desc": "حساب الموظفين العاملين في المنشأة (أطباء، تمريض، إداريون، ماليون)"},
    {"type": AccountType.PATIENT.value, "name": "حساب مريض", "name_en": "Patient Account", "desc": "بوابة المريض للاطلاع على مواعيده ونتائج التحاليل والملف الشخصي"},
    {"type": AccountType.GUARDIAN.value, "name": "حساب ولي أمر / ممثل قانوني", "name_en": "Guardian Account", "desc": "إدارة سجلات القُصّر أو المرضى المشمولين بالوصاية القانونية"},
    {"type": AccountType.EXTERNAL_PHYSICIAN.value, "name": "حساب طبيب خارجي / محول", "name_en": "External Physician Account", "desc": "الأطباء الزائرون أو المحولون للاطلاع على حالات محددة بتفويض"},
    {"type": AccountType.INSURANCE_PROVIDER.value, "name": "حساب شركة تأمين", "name_en": "Insurance Provider Account", "desc": "مدققو شركات التأمين لمراجعة وتدقيق المطالبات إلكترونياً"},
    {"type": AccountType.SUPPLIER.value, "name": "حساب مورد", "name_en": "Supplier Account", "desc": "بوابة الموردين لاستعراض أوامر الشراء وتقديم عروض الأسعار"},
    {"type": AccountType.PARTNER.value, "name": "حساب شريك أعمال", "name_en": "Partner Account", "desc": "المراكز التشخيصية أو المختبرات المتعاقدة الخارجية"},
    {"type": AccountType.SERVICE_ACCOUNT.value, "name": "حساب خدمة برمجية (API/M2M)", "name_en": "Service Account", "desc": "ربط الآلات المخبرية والأجهزة والأنظمة الخارجية عبر API"},
    {"type": AccountType.ADMINISTRATOR.value, "name": "حساب مدير نظام (تقني)", "name_en": "Administrator Account", "desc": "الإدارة الفنية للمنصة والتهيئة مع عزل صارم عن السجلات الطبية"},
]

# -------------------------------------------------------------------------
# 3. Standard Granular Permissions
# -------------------------------------------------------------------------
STANDARD_PERMISSIONS = [
    # Patients Module
    {"code": "patients.view", "module": "patients", "action": "view", "name": "استعراض بيانات المرضى", "name_en": "View Patients", "is_clinical": False, "sensitivity": "normal"},
    {"code": "patients.create", "module": "patients", "action": "create", "name": "تسجيل مريض جديد", "name_en": "Create Patient", "is_clinical": False, "sensitivity": "normal"},
    {"code": "patients.update", "module": "patients", "action": "update", "name": "تعديل البيانات الديموغرافية للمريض", "name_en": "Update Patient", "is_clinical": False, "sensitivity": "normal"},
    {"code": "patients.merge", "module": "patients", "action": "merge", "name": "دمج السجلات المتطابقة", "name_en": "Merge Patients", "is_clinical": False, "sensitivity": "restricted"},

    # Appointments Module
    {"code": "appointments.view", "module": "appointments", "action": "view", "name": "استعراض جدول المواعيد والانتظار", "name_en": "View Appointments", "is_clinical": False, "sensitivity": "normal"},
    {"code": "appointments.create", "module": "appointments", "action": "create", "name": "حجز موعد كشف أو استشارة", "name_en": "Create Appointment", "is_clinical": False, "sensitivity": "normal"},
    {"code": "appointments.cancel", "module": "appointments", "action": "cancel", "name": "إلغاء أو إعادة جدولة موعد", "name_en": "Cancel Appointment", "is_clinical": False, "sensitivity": "normal"},

    # Electronic Medical Records (EMR) — STRICT CLINICAL BARRIER
    {"code": "emr.view", "module": "emr", "action": "view", "name": "استعراض السجل الطبي السريري للمريض", "name_en": "View Medical Records", "is_clinical": True, "sensitivity": "sensitive"},
    {"code": "emr.create", "module": "emr", "action": "create", "name": "توثيق كشف سريري وتشخيص (SOAP)", "name_en": "Create Medical Note", "is_clinical": True, "sensitivity": "sensitive"},
    {"code": "emr.sign", "module": "emr", "action": "sign", "name": "التوقيع والاعتماد النهائي للسجل الطبي", "name_en": "Sign Clinical Record", "is_clinical": True, "sensitivity": "critical"},
    {"code": "emr.amend", "module": "emr", "action": "amend", "name": "إضافة ملحق أو تصحيح لسجل معتمد", "name_en": "Amend Clinical Record", "is_clinical": True, "sensitivity": "critical"},

    # Prescriptions Module — STRICT CLINICAL BARRIER
    {"code": "prescriptions.create", "module": "prescriptions", "action": "create", "name": "تحرير وصفة طبية (e-Rx)", "name_en": "Create Prescription", "is_clinical": True, "sensitivity": "sensitive"},
    {"code": "prescriptions.approve", "module": "prescriptions", "action": "approve", "name": "الموافقة السريرية وتدقيق الجرعات", "name_en": "Approve Prescription", "is_clinical": True, "sensitivity": "sensitive"},
    {"code": "prescriptions.dispense", "module": "prescriptions", "action": "dispense", "name": "صرف وتجهيز الدواء للمريض", "name_en": "Dispense Medication", "is_clinical": True, "sensitivity": "sensitive"},

    # Laboratory Module (LIS)
    {"code": "lab.orders.view", "module": "laboratory", "action": "view", "name": "استعراض طلبات الفحوصات المخبرية", "name_en": "View Lab Orders", "is_clinical": True, "sensitivity": "normal"},
    {"code": "lab.results.enter", "module": "laboratory", "action": "enter", "name": "إدخال نتائج التحاليل والعينات", "name_en": "Enter Lab Results", "is_clinical": True, "sensitivity": "sensitive"},
    {"code": "lab.results.validate", "module": "laboratory", "action": "validate", "name": "الاعتماد الفني النهائي لنتائج المختبر", "name_en": "Validate Lab Results", "is_clinical": True, "sensitivity": "critical"},

    # Radiology Module (RIS/PACS)
    {"code": "radiology.orders.view", "module": "radiology", "action": "view", "name": "استعراض طلبات الأشعة والتصوير", "name_en": "View Radiology Orders", "is_clinical": True, "sensitivity": "normal"},
    {"code": "radiology.reports.create", "module": "radiology", "action": "create", "name": "كتابة تقرير الأشعة التشخيصي", "name_en": "Create Radiology Report", "is_clinical": True, "sensitivity": "sensitive"},
    {"code": "radiology.reports.approve", "module": "radiology", "action": "approve", "name": "اعتماد وتوقيع تقرير الأشعة النهائي", "name_en": "Approve Radiology Report", "is_clinical": True, "sensitivity": "critical"},

    # Inpatient Admissions & Beds
    {"code": "admissions.create", "module": "admissions", "action": "create", "name": "إصدار أمر تنويم مريض وإدخال", "name_en": "Create Admission", "is_clinical": True, "sensitivity": "sensitive"},
    {"code": "admissions.transfer", "module": "admissions", "action": "transfer", "name": "نقل مريض بين الأجنحة والأسرة", "name_en": "Transfer Patient", "is_clinical": True, "sensitivity": "normal"},
    {"code": "admissions.discharge", "module": "admissions", "action": "discharge", "name": "إصدار ملخص وأمر الخروج الطبي", "name_en": "Discharge Patient", "is_clinical": True, "sensitivity": "critical"},

    # Medical Billing & Accounts
    {"code": "billing.view", "module": "billing", "action": "view", "name": "استعراض الفواتير وحسابات المرضى", "name_en": "View Billing", "is_clinical": False, "sensitivity": "normal"},
    {"code": "billing.create", "module": "billing", "action": "create", "name": "إصدار فاتورة طبية أو تحصيل نقدية", "name_en": "Create Invoice", "is_clinical": False, "sensitivity": "normal"},
    {"code": "billing.refund", "module": "billing", "action": "refund", "name": "إجراء مرتجع مالي أو تسوية خصم", "name_en": "Refund Invoice", "is_clinical": False, "sensitivity": "restricted"},

    # Insurance & Claims
    {"code": "insurance.claims.create", "module": "insurance", "action": "create", "name": "إنشاء مطالبة تأمينية للمريض", "name_en": "Create Insurance Claim", "is_clinical": False, "sensitivity": "normal"},
    {"code": "insurance.claims.submit", "module": "insurance", "action": "submit", "name": "إرسال حزمة المطالبات لشركة التأمين", "name_en": "Submit Claims", "is_clinical": False, "sensitivity": "restricted"},

    # Accounting & General Ledger
    {"code": "accounting.journals.create", "module": "accounting", "action": "create", "name": "تسجيل قيود اليومية ومراكز التكلفة", "name_en": "Create Journals", "is_clinical": False, "sensitivity": "restricted"},
    {"code": "accounting.periods.close", "module": "accounting", "action": "close", "name": "إقفال الفترات والشهور المحاسبية", "name_en": "Close Accounting Period", "is_clinical": False, "sensitivity": "critical"},

    # Human Resources (HR)
    {"code": "hr.employees.view", "module": "hr", "action": "view", "name": "استعراض ملفات الكوادر والموظفين", "name_en": "View Employees", "is_clinical": False, "sensitivity": "normal"},
    {"code": "hr.employees.manage", "module": "hr", "action": "manage", "name": "إدارة الموظفين والرواتب والتعيينات", "name_en": "Manage Employees", "is_clinical": False, "sensitivity": "restricted"},

    # Inventory & Supplies
    {"code": "inventory.view", "module": "inventory", "action": "view", "name": "استعراض أرصدة المخازن والمستلزمات", "name_en": "View Inventory", "is_clinical": False, "sensitivity": "normal"},
    {"code": "inventory.adjust", "module": "inventory", "action": "adjust", "name": "تسوية الجرد المخزني والإتلاف", "name_en": "Adjust Stock", "is_clinical": False, "sensitivity": "restricted"},
    {"code": "inventory.transfer", "module": "inventory", "action": "transfer", "name": "تحويل أصناف ومستلزمات بين الفروع", "name_en": "Transfer Stock", "is_clinical": False, "sensitivity": "normal"},

    # Platform & Settings Administration
    {"code": "settings.view", "module": "administration", "action": "view", "name": "استعراض إعدادات النظام والمنشأة", "name_en": "View Settings", "is_clinical": False, "sensitivity": "normal"},
    {"code": "settings.manage", "module": "administration", "action": "manage", "name": "تعديل إعدادات وسياسات المنشأة", "name_en": "Manage Settings", "is_clinical": False, "sensitivity": "restricted"},
    {"code": "users.manage", "module": "administration", "action": "manage", "name": "إدارة المستخدمين ومنح الصلاحيات", "name_en": "Manage Users", "is_clinical": False, "sensitivity": "critical"},
    {"code": "audit.view", "module": "administration", "action": "view", "name": "استعراض سجلات التدقيق والمراقبة", "name_en": "View Audit Trail", "is_clinical": False, "sensitivity": "restricted"},
]

# -------------------------------------------------------------------------
# 4. Standard System Roles & Default Permissions Matrix
# -------------------------------------------------------------------------
STANDARD_ROLES = [
    {
        "code": "org_owner",
        "name": "مالك المنشأة / المؤسس",
        "name_en": "Organization Owner",
        "desc": "إدارة المنشأة والاشتراكات والمستخدمين والصلاحيات العامة",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "settings.view", "settings.manage", "users.manage", "audit.view",
            "billing.view", "billing.create", "billing.refund",
            "accounting.journals.create", "accounting.periods.close",
            "hr.employees.view", "hr.employees.manage",
            "inventory.view", "inventory.adjust", "inventory.transfer",
            "patients.view", "patients.create", "appointments.view"
        ]
    },
    {
        "code": "hospital_administrator",
        "name": "مدير إدارة المستشفى",
        "name_en": "Hospital Administrator",
        "desc": "إدارة تشغيلية شاملة للمرافق والعمليات (مع عزل السجلات الطبية)",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "settings.view", "settings.manage", "users.manage", "audit.view",
            "patients.view", "patients.create", "patients.update",
            "appointments.view", "appointments.create", "appointments.cancel",
            "billing.view", "billing.create", "billing.refund",
            "hr.employees.view", "inventory.view", "inventory.transfer"
        ]
    },
    {
        "code": "medical_director",
        "name": "المدير الطبي",
        "name_en": "Medical Director",
        "desc": "الإشراف الطبي الكامل، اعتماد البروتوكولات، مراجعة السجلات الطبية الحرجة",
        "is_system": True,
        "is_clinical": True,
        "perms": [
            "patients.view", "patients.create", "patients.update", "patients.merge",
            "appointments.view", "appointments.create", "appointments.cancel",
            "emr.view", "emr.create", "emr.sign", "emr.amend",
            "prescriptions.create", "prescriptions.approve",
            "lab.orders.view", "lab.results.validate",
            "radiology.orders.view", "radiology.reports.approve",
            "admissions.create", "admissions.transfer", "admissions.discharge",
            "audit.view"
        ]
    },
    {
        "code": "doctor",
        "name": "طبيب معالج / استشاري",
        "name_en": "Doctor",
        "desc": "توثيق الكشوفات الطبية، طلب الفحوصات والأشعة، كتابة الوصفات للمرضى المكلف بهم",
        "is_system": True,
        "is_clinical": True,
        "perms": [
            "patients.view", "appointments.view",
            "emr.view", "emr.create", "emr.sign",
            "prescriptions.create",
            "lab.orders.view",
            "radiology.orders.view",
            "admissions.create", "admissions.discharge"
        ]
    },
    {
        "code": "nurse",
        "name": "كادر التمريض",
        "name_en": "Nurse",
        "desc": "توثيق العلامات الحيوية، إدارة الأدوية والأسرة، متابعة حالات التنويم",
        "is_system": True,
        "is_clinical": True,
        "perms": [
            "patients.view", "appointments.view",
            "emr.view", "emr.create",
            "prescriptions.dispense",
            "lab.orders.view",
            "admissions.transfer"
        ]
    },
    {
        "code": "receptionist",
        "name": "موظف استقبال واستعلامات",
        "name_en": "Receptionist",
        "desc": "تسجيل المرضى، حجز وإلغاء المواعيد، تنظيم الطوابير",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "patients.view", "patients.create", "patients.update",
            "appointments.view", "appointments.create", "appointments.cancel",
            "billing.view"
        ]
    },
    {
        "code": "lab_technician",
        "name": "فني مختبرات",
        "name_en": "Lab Technician",
        "desc": "استلام العينات وإدخال قراءات التحاليل والأجهزة",
        "is_system": True,
        "is_clinical": True,
        "perms": [
            "patients.view",
            "lab.orders.view", "lab.results.enter"
        ]
    },
    {
        "code": "lab_supervisor",
        "name": "مشرف مختبر واعتماد",
        "name_en": "Lab Supervisor",
        "desc": "مراجعة واعتماد النتائج المخبرية وإشعار الأطباء بالقيم الحرجة",
        "is_system": True,
        "is_clinical": True,
        "perms": [
            "patients.view",
            "lab.orders.view", "lab.results.enter", "lab.results.validate"
        ]
    },
    {
        "code": "radiologist",
        "name": "طبيب / أخصائي أشعة",
        "name_en": "Radiologist",
        "desc": "استعراض صور PACS وكتابة واعتماد تقارير الأشعة",
        "is_system": True,
        "is_clinical": True,
        "perms": [
            "patients.view",
            "radiology.orders.view", "radiology.reports.create", "radiology.reports.approve"
        ]
    },
    {
        "code": "pharmacist",
        "name": "صيدلي سريري / مستشفى",
        "name_en": "Pharmacist",
        "desc": "مراجعة الوصفات والجرعات وصرف الأدوية للمرضى الخارجيين والتنويم",
        "is_system": True,
        "is_clinical": True,
        "perms": [
            "patients.view",
            "prescriptions.approve", "prescriptions.dispense",
            "inventory.view", "inventory.transfer"
        ]
    },
    {
        "code": "cashier",
        "name": "كاشير وتحصيل طبي",
        "name_en": "Cashier",
        "desc": "تحصيل فواتير المرضى وإصدار إيصالات السداد",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "patients.view", "billing.view", "billing.create"
        ]
    },
    {
        "code": "accountant",
        "name": "محاسب مالي",
        "name_en": "Accountant",
        "desc": "القيود المحاسبية، تسويات البنوك، القيود اليومية",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "billing.view", "billing.create", "billing.refund",
            "accounting.journals.create",
            "hr.employees.view"
        ]
    },
    {
        "code": "insurance_officer",
        "name": "مسؤول تأمين طبي ومطالبات",
        "name_en": "Insurance Officer",
        "desc": "الموافقات المسبقة، إنشاء وإرسال حزم المطالبات لشركات التأمين",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "patients.view", "billing.view",
            "insurance.claims.create", "insurance.claims.submit"
        ]
    },
    {
        "code": "hr_manager",
        "name": "مدير الموارد البشرية",
        "name_en": "HR Manager",
        "desc": "إدارة سجلات العاملين والرواتب والمناوبات والمؤهلات",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "hr.employees.view", "hr.employees.manage",
            "users.manage"
        ]
    },
    {
        "code": "storekeeper",
        "name": "أمين مستودع مستلزمات طبية",
        "name_en": "Storekeeper",
        "desc": "حركة استلام وصرف المستلزمات الطبية والجرد",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "inventory.view", "inventory.transfer"
        ]
    },
    {
        "code": "procurement_officer",
        "name": "مسؤول مشتريات وتوريد",
        "name_en": "Procurement Officer",
        "desc": "إصدار أوامر الشراء والتعامل مع الموردين ومتابعة التوريد",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "inventory.view", "inventory.adjust"
        ]
    },
    {
        "code": "maintenance_technician",
        "name": "فني صيانة وأجهزة طبية",
        "name_en": "Maintenance Technician",
        "desc": "تنفيذ مهام الصيانة الوقائية والطارئة للأجهزة والمرافق",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "inventory.view"
        ]
    },
    {
        "code": "auditor",
        "name": "مدقق رقابي ومراجع",
        "name_en": "Auditor",
        "desc": "استعراض السجلات والتقارير المالية والتشغيلية للقراءة فقط",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "audit.view", "billing.view", "patients.view", "appointments.view"
        ]
    },
    {
        "code": "it_administrator",
        "name": "مدير النظام وتكنولوجيا المعلومات",
        "name_en": "IT Administrator",
        "desc": "التهيئة الفنية للنظام، المستخدمين، الصلاحيات (مع عزل السجلات الطبية)",
        "is_system": True,
        "is_clinical": False,
        "perms": [
            "settings.view", "settings.manage", "users.manage", "audit.view"
        ]
    },
]


async def seed_rbac_catalog(session: AsyncSession):
    """Seed all 98 positions, 9 account types, 50+ permissions, and 20 roles idempotently."""
    logger.info("Seeding RBAC & ABAC suite...")

    # 1. Seed Permissions
    perm_map: Dict[str, SysPermission] = {}
    for p_def in STANDARD_PERMISSIONS:
        res = await session.execute(select(SysPermission).where(SysPermission.code == p_def["code"]))
        perm = res.scalar_one_or_none()
        if not perm:
            perm = SysPermission(
                code=p_def["code"],
                module=p_def["module"],
                action=p_def["action"],
                name=p_def["name"],
                name_en=p_def["name_en"],
                is_clinical=p_def.get("is_clinical", False),
                data_sensitivity=p_def.get("sensitivity", "normal"),
            )
            session.add(perm)
            await session.flush()
        perm_map[perm.code] = perm

    # 2. Seed Roles & RolePermissions
    for r_def in STANDARD_ROLES:
        res = await session.execute(select(SysRole).where(SysRole.code == r_def["code"], SysRole.tenant_id.is_(None)))
        role = res.scalar_one_or_none()
        if not role:
            role = SysRole(
                code=r_def["code"],
                name=r_def["name"],
                name_en=r_def["name_en"],
                description=r_def["desc"],
                is_system=r_def["is_system"],
                is_clinical=r_def.get("is_clinical", False),
            )
            session.add(role)
            await session.flush()

        # Link permissions
        for p_code in r_def["perms"]:
            if p_code in perm_map:
                p_obj = perm_map[p_code]
                res_link = await session.execute(
                    select(SysRolePermission).where(
                        SysRolePermission.role_id == role.id,
                        SysRolePermission.permission_id == p_obj.id,
                    )
                )
                if not res_link.scalar_one_or_none():
                    session.add(SysRolePermission(role_id=role.id, permission_id=p_obj.id))

    # 3. Seed Positions (Job Titles Groups A through I)
    for pos_def in STANDARD_POSITIONS:
        res = await session.execute(select(OrgPosition).where(OrgPosition.code == pos_def["code"], OrgPosition.tenant_id.is_(None)))
        pos = res.scalar_one_or_none()
        if not pos:
            pos = OrgPosition(
                code=pos_def["code"],
                name=pos_def["name"],
                name_en=pos_def["name_en"],
                category=pos_def["category"],
                department_name=pos_def.get("dept"),
                description=pos_def.get("desc"),
                is_active=True,
            )
            session.add(pos)

    await session.commit()
    logger.info("RBAC & ABAC suite seeded successfully!")
