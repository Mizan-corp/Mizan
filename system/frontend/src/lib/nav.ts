import {
  Archive,
  ArrowLeftRight,
  BarChart3,
  Blocks,
  Boxes,
  Briefcase,
  ChefHat,
  Clock,
  Contact,
  GraduationCap,
  LayoutDashboard,
  LayoutGrid,
  Package,
  Pill,
  Receipt,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Store,
  Truck,
  UserCog,
  Wallet,
  Warehouse,
  Globe,
  Compass,
  Dumbbell,
  Hotel,
  Palette,
  Scale,
  Scissors,
  Stethoscope,
  Wrench,
  Factory,
  Utensils,
  FlaskConical,
  Printer,
  HardHat,
  Building2,
  Tractor,
  Zap,
  Landmark,
  Shield,
  Building,
  Ticket,
  Flame,
  Bed,
  Calendar,
  HeartPulse,
  Microscope,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  to: string;
  label: string;
  perm: string; // "" = always visible; checked against the user's real permissions
  module?: string; // "" or omitted = always active; otherwise checked against active_modules
  icon: LucideIcon;
  group: "main" | "stock" | "money" | "admin";
};

export const NAV_ITEMS: NavItem[] = [
  // Core & POS
  { to: "/", label: "لوحة التحكم", perm: "", module: "", icon: LayoutDashboard, group: "main" },
  { to: "/pos", label: "نقطة البيع", perm: "pos", module: "pos", icon: ShoppingCart, group: "main" },
  { to: "/sales", label: "المبيعات", perm: "sales", module: "pos", icon: Receipt, group: "main" },
  { to: "/shifts", label: "الورديات", perm: "shifts", module: "pos", icon: Clock, group: "main" },

  // Pharmacy & Dispensing Specialized Injections
  { to: "/pharmacy", label: "الصيدلية والروشتات", perm: "pos", module: "pharmacy", icon: Pill, group: "main" },

  // Restaurant & Hospitality Specialized Injections
  { to: "/restaurant/tables", label: "إدارة الطاولات والصالة", perm: "pos", module: "restaurant", icon: LayoutGrid, group: "main" },
  { to: "/restaurant/kitchen", label: "شاشة المطبخ (KDS)", perm: "pos", module: "restaurant", icon: ChefHat, group: "main" },

  // School & Education Specialized Injections
  { to: "/school/students", label: "شؤون الطلاب والأقساط", perm: "customers", module: "school", icon: GraduationCap, group: "main" },

  // Consulting & Professional Services
  { to: "/services", label: "الخدمات والاستشارات", perm: "customers", module: "services", icon: Briefcase, group: "main" },

  // Distribution & Supply Chain (Phase 2)
  { to: "/wholesale", label: "تجارة الجملة والتوزيع", perm: "sales", module: "wholesale", icon: Boxes, group: "stock" },
  { to: "/logistics", label: "الشحن والأسطول", perm: "operations", module: "logistics", icon: Truck, group: "main" },
  { to: "/wms", label: "مستودعات 3PL", perm: "inventory", module: "wms", icon: Warehouse, group: "stock" },
  { to: "/ecommerce", label: "المتجر الإلكتروني", perm: "sales", module: "ecommerce", icon: Globe, group: "main" },
  { to: "/storefront", label: "متجر المنشأة (Storefront)", perm: "sales", module: "storefront", icon: Store, group: "main" },

  // Service-Based Systems (Phase 3)
  { to: "/clinic", label: "العيادات والمستشفيات", perm: "customers", module: "clinic", icon: Stethoscope, group: "main" },
  { to: "/law", label: "المحاماة والقضايا", perm: "customers", module: "law", icon: Scale, group: "main" },
  { to: "/travel", label: "السياحة وحجوزات السفر", perm: "sales", module: "travel", icon: Compass, group: "main" },
  { to: "/hospitality", label: "الفنادق والضيافة (PMS)", perm: "operations", module: "hospitality", icon: Hotel, group: "main" },
  { to: "/gym", label: "الجيم واللياقة البدنية", perm: "customers", module: "gym", icon: Dumbbell, group: "main" },
  { to: "/salon", label: "الصالون والتجميل والسبا", perm: "pos", module: "salon", icon: Scissors, group: "main" },
  { to: "/agency", label: "الدعاية والإعلام والترجمة", perm: "operations", module: "agency", icon: Palette, group: "main" },
  { to: "/field-service", label: "الصيانة الميدانية (FSM)", perm: "operations", module: "field_service", icon: Wrench, group: "stock" },

  // Manufacturing & Industrial (Phase 4)
  { to: "/mfg", label: "التصنيع الميكانيكي (BOM/MRP)", perm: "operations", module: "mfg", icon: Factory, group: "stock" },
  { to: "/fod", label: "الصناعات الغذائية (HACCP)", perm: "operations", module: "fod", icon: Utensils, group: "stock" },
  { to: "/phm", label: "التصنيع الدوائي (cGMP)", perm: "operations", module: "phm", icon: FlaskConical, group: "stock" },
  { to: "/prn", label: "الطباعة والتغليف (Job Dockets)", perm: "operations", module: "prn", icon: Printer, group: "stock" },

  // Projects & Infrastructure (Phase 5)
  { to: "/cst", label: "المقاولات العامة والإنشاءات", perm: "operations", module: "cst", icon: HardHat, group: "stock" },
  { to: "/rec", label: "التطوير العقاري وإدارة الأملاك", perm: "operations", module: "rec", icon: Building2, group: "main" },
  { to: "/agr", label: "الزراعة وإدارة المزارع", perm: "operations", module: "agr", icon: Tractor, group: "stock" },
  { to: "/eng", label: "محطات الطاقة وتوليد الكهرباء", perm: "operations", module: "eng", icon: Zap, group: "stock" },

  // Specialized & Public Sector (Phase 6)
  { to: "/bnk", label: "البنوك والمؤسسات المصرفية", perm: "finance", module: "bnk", icon: Landmark, group: "money" },
  { to: "/ins", label: "التأمين وإدارة المطالبات", perm: "finance", module: "ins", icon: Shield, group: "money" },
  { to: "/gov", label: "القطاع الحكومي والمنظمات", perm: "operations", module: "gov", icon: Building, group: "main" },
  { to: "/ent", label: "الترفيه والفعاليات والملاهي", perm: "operations", module: "ent", icon: Ticket, group: "main" },
  { to: "/oil", label: "عمليات البترول والغاز", perm: "operations", module: "oil", icon: Flame, group: "stock" },

  // Stock & Inventory
  { to: "/products", label: "المنتجات", perm: "inventory", module: "inventory", icon: Package, group: "stock" },
  { to: "/inventory", label: "المخزون والتقييم", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
  { to: "/operations", label: "العمليات المخزنية", perm: "operations", module: "inventory", icon: ArrowLeftRight, group: "stock" },
  { to: "/purchases", label: "المشتريات والتوريد", perm: "purchases", module: "inventory", icon: Truck, group: "stock" },

  // Finance & AR/AP
  { to: "/customers", label: "العملاء (AR)", perm: "customers", module: "finance", icon: Contact, group: "money" },
  { to: "/suppliers", label: "الموردون (AP)", perm: "customers", module: "finance", icon: Truck, group: "money" },
  { to: "/finance", label: "المالية والخزائن", perm: "finance", module: "finance", icon: Wallet, group: "money" },
  { to: "/reports", label: "التقارير", perm: "reports", module: "core", icon: BarChart3, group: "money" },

  // HR & Payroll
  { to: "/hr", label: "الموظفون", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
  { to: "/hr/payroll", label: "الرواتب", perm: "payroll", module: "hr", icon: Wallet, group: "admin" },

  // Administration & Marketplace
  { to: "/modules", label: "سوق الوحدات والأنشطة", perm: "settings", module: "", icon: Blocks, group: "admin" },
  { to: "/archive", label: "الأرشيف", perm: "archive", module: "core", icon: Archive, group: "admin" },
  { to: "/users", label: "المستخدمون والصلاحيات", perm: "users", module: "core", icon: ShieldCheck, group: "admin" },
  { to: "/settings", label: "الإعدادات", perm: "settings", module: "core", icon: Settings, group: "admin" },
];

export const NAV_GROUPS: Record<NavItem["group"], string> = {
  main: "التشغيل والعمليات",
  stock: "المخزون والتوريد",
  money: "المال والعلاقات",
  admin: "الإدارة والنظام",
};

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

export function getSectorNavigation(
  sector: string | undefined,
  can: (perm: string) => boolean,
  hasModule: (mod: string) => boolean,
): NavGroup[] {
  // Helper to filter items cleanly
  const filterItems = (groups: NavGroup[]): NavGroup[] =>
    groups
      .map((g) => ({
        ...g,
        items: g.items.filter((item) => (!item.perm || can(item.perm)) && (!item.module || hasModule(item.module))),
      }))
      .filter((g) => g.items.length > 0);

  // 1. Healthcare & Clinics
  if (sector === "healthcare") {
    return filterItems([
      {
        id: "clinical",
        label: "العيادات والتشغيل الطبي",
        items: [
          { to: "/clinic", label: "لوحة التحكم الطبية", perm: "", module: "", icon: Stethoscope, group: "main" },
          { to: "/clinic?tab=appointments", label: "حجز المواعيد والانتظار", perm: "", module: "", icon: Calendar, group: "main" },
          { to: "/clinic?tab=patients", label: "سجلات وملفات المرضى (EMR)", perm: "", module: "", icon: Users, group: "main" },
          { to: "/clinic?tab=emr", label: "الكشوفات السريرية والتشخيص", perm: "", module: "", icon: HeartPulse, group: "main" },
          { to: "/clinic?tab=rx_labs", label: "الروشتات والوصفات الرقمية", perm: "", module: "", icon: Pill, group: "main" },
          { to: "/clinic?tab=labs", label: "الفحوصات والتحاليل المخبرية", perm: "", module: "", icon: Microscope, group: "main" },
          { to: "/clinic?tab=beds", label: "أسرّة التنويم والأجنحة", perm: "", module: "", icon: Bed, group: "main" },
        ],
      },
      {
        id: "pharmacy_supplies",
        label: "الصيدلية والمستلزمات الطبية",
        items: [
          { to: "/pharmacy", label: "صيدلية وصرف الأدوية", perm: "pos", module: "pharmacy", icon: Pill, group: "stock" },
          { to: "/inventory", label: "المخزون والمستلزمات الطبية", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
          { to: "/purchases", label: "طلبيات وتوريد الأدوية", perm: "purchases", module: "inventory", icon: Truck, group: "stock" },
        ],
      },
      {
        id: "medical_finance",
        label: "المالية والفوترة الطبية",
        items: [
          { to: "/clinic?tab=billing", label: "فواتير الكشوفات والتأمين", perm: "", module: "", icon: Receipt, group: "money" },
          { to: "/clinic?tab=claims", label: "مطالبات شركات التأمين", perm: "", module: "", icon: ShieldCheck, group: "money" },
          { to: "/customers", label: "حسابات المرضى والتعاقدات", perm: "customers", module: "finance", icon: Contact, group: "money" },
          { to: "/suppliers", label: "شركات الأدوية والموردين", perm: "customers", module: "finance", icon: Truck, group: "money" },
          { to: "/finance", label: "الخزائن والإيرادات الطبية", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "التقارير الطبية والمالية", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "medical_staff",
        label: "الكادر الطبي والإدارة",
        items: [
          { to: "/hr", label: "الأطباء وهيئة التمريض", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/shifts", label: "نوبتجيات ومناوبات الكادر", perm: "shifts", module: "core", icon: Clock, group: "admin" },
          { to: "/modules", label: "سوق الوحدات الطبية", perm: "settings", module: "", icon: Blocks, group: "admin" },
          { to: "/users", label: "المستخدمون وصلاحيات النظام", perm: "users", module: "core", icon: ShieldCheck, group: "admin" },
          { to: "/settings", label: "إعدادات العيادات والمجمع", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 2. Restaurants & Cafes
  if (sector === "restaurant") {
    return filterItems([
      {
        id: "dining",
        label: "الصالة والتشغيل الفندقي",
        items: [
          { to: "/restaurant/tables", label: "إدارة الطاولات والصالة", perm: "pos", module: "restaurant", icon: LayoutGrid, group: "main" },
          { to: "/restaurant/kitchen", label: "شاشة المطبخ (KDS)", perm: "pos", module: "restaurant", icon: ChefHat, group: "main" },
          { to: "/pos", label: "نقطة بيع المطعم والطلبات", perm: "pos", module: "pos", icon: ShoppingCart, group: "main" },
          { to: "/sales", label: "فواتير الطلبات والضيافة", perm: "sales", module: "pos", icon: Receipt, group: "main" },
        ],
      },
      {
        id: "kitchen_stock",
        label: "المطبخ والمخزون الغذائي",
        items: [
          { to: "/products", label: "قائمة المأكولات والمشروبات (Menu)", perm: "inventory", module: "inventory", icon: Utensils, group: "stock" },
          { to: "/inventory", label: "المكونات والمخزون الغذائي", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
          { to: "/purchases", label: "توريدات الأغذية والخضار", perm: "purchases", module: "inventory", icon: Truck, group: "stock" },
        ],
      },
      {
        id: "dining_finance",
        label: "المالية وحسابات العملاء",
        items: [
          { to: "/customers", label: "حسابات عملاء الشركات والولاء", perm: "customers", module: "finance", icon: Contact, group: "money" },
          { to: "/suppliers", label: "موردو اللحوم والأغذية", perm: "customers", module: "finance", icon: Truck, group: "money" },
          { to: "/finance", label: "الخزينة والمالية اليومية", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير المبيعات وهدر المطبخ", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "dining_staff",
        label: "الكادر والإدارة",
        items: [
          { to: "/hr", label: "الشيفات وطاقم الخدمة", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/shifts", label: "ورديات العمل", perm: "shifts", module: "pos", icon: Clock, group: "admin" },
          { to: "/settings", label: "إعدادات المطعم", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 3. Pharmacy & Medicine Dispensing
  if (sector === "pharmacy") {
    return filterItems([
      {
        id: "dispensing",
        label: "صيدلية وصرف الأدوية",
        items: [
          { to: "/pharmacy", label: "الصيدلية وصرف الروشتات", perm: "pos", module: "pharmacy", icon: Pill, group: "main" },
          { to: "/pos", label: "كاشير ونقطة بيع الأدوية", perm: "pos", module: "pos", icon: ShoppingCart, group: "main" },
          { to: "/sales", label: "مبيعات الأدوية والمستلزمات", perm: "sales", module: "pos", icon: Receipt, group: "main" },
        ],
      },
      {
        id: "pharmacy_stock",
        label: "الأدوية والتشغيلات والصلاحيات",
        items: [
          { to: "/products", label: "الأدوية والمستحضرات", perm: "inventory", module: "inventory", icon: Package, group: "stock" },
          { to: "/inventory", label: "مخزون الأدوية وتواريخ الصلاحية", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
          { to: "/suppliers", label: "شركات ومستودعات الأدوية", perm: "customers", module: "finance", icon: Truck, group: "stock" },
          { to: "/purchases", label: "طلبيات وتوريد الأدوية", perm: "purchases", module: "inventory", icon: Truck, group: "stock" },
        ],
      },
      {
        id: "pharmacy_finance",
        label: "التأمين والمالية",
        items: [
          { to: "/customers", label: "عملاء التأمين والنقدي", perm: "customers", module: "finance", icon: Contact, group: "money" },
          { to: "/finance", label: "الخزائن والمالية", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير الصيدلية والنواقص", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "pharmacy_admin",
        label: "فريق الصيادلة والإدارة",
        items: [
          { to: "/hr", label: "الصيادلة ومساعدو الصيدلي", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/shifts", label: "ورديات الصيدلية", perm: "shifts", module: "pos", icon: Clock, group: "admin" },
          { to: "/settings", label: "إعدادات الصيدلية", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 4. Schools & Education
  if (sector === "school") {
    return filterItems([
      {
        id: "academic",
        label: "شؤون الطلاب والأكاديميا",
        items: [
          { to: "/school/students", label: "سجلات الطلاب والقيد", perm: "customers", module: "school", icon: GraduationCap, group: "main" },
          { to: "/school/students?tab=admissions", label: "طلبات الالتحاق والقبول", perm: "customers", module: "school", icon: Users, group: "main" },
          { to: "/school/students?tab=buses", label: "حافلات النقل وخطوط السير", perm: "customers", module: "school", icon: Truck, group: "main" },
        ],
      },
      {
        id: "school_fees",
        label: "المصروفات والأقساط",
        items: [
          { to: "/school/students?tab=fees", label: "جدول الأقساط والمصروفات", perm: "finance", module: "school", icon: Receipt, group: "money" },
          { to: "/customers", label: "أولياء الأمور والجهات المانحة", perm: "customers", module: "finance", icon: Contact, group: "money" },
          { to: "/finance", label: "خزينة المدرسة والبنك", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير تحصيل الأقساط", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "school_staff",
        label: "الكادر التعليمي والإدارة",
        items: [
          { to: "/hr", label: "المعلمون والإداريون", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/hr/payroll", label: "مسيرات رواتب الكادر", perm: "payroll", module: "hr", icon: Wallet, group: "admin" },
          { to: "/settings", label: "إعدادات المدرسة والعام الدراسي", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 5. Gyms & Fitness Centers
  if (sector === "gym") {
    return filterItems([
      {
        id: "fitness",
        label: "الصالة والاشتراكات",
        items: [
          { to: "/gym", label: "لوحة تحكم الصالة والمشتركين", perm: "customers", module: "gym", icon: Dumbbell, group: "main" },
          { to: "/gym?tab=members", label: "سجلات الأعضاء والاشتراكات", perm: "customers", module: "gym", icon: Users, group: "main" },
          { to: "/gym?tab=access", label: "بوابات الدخول اللحظية", perm: "customers", module: "gym", icon: ShieldCheck, group: "main" },
          { to: "/gym?tab=pt", label: "حصص التدريب الخاص (PT)", perm: "customers", module: "gym", icon: Clock, group: "main" },
          { to: "/pos", label: "كافيتيريا ومكملات الجيم", perm: "pos", module: "pos", icon: ShoppingCart, group: "main" },
        ],
      },
      {
        id: "gym_stock",
        label: "المكملات والمخزون",
        items: [
          { to: "/products", label: "المكملات والبروتين والمشروبات", perm: "inventory", module: "inventory", icon: Package, group: "stock" },
          { to: "/inventory", label: "مخزون الكافيتيريا والمستودع", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
        ],
      },
      {
        id: "gym_finance",
        label: "الاشتراكات والمالية",
        items: [
          { to: "/sales", label: "فواتير الاشتراكات والخدمات", perm: "sales", module: "", icon: Receipt, group: "money" },
          { to: "/finance", label: "الخزينة والاشتراكات المجدولة", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير تجديد الاشتراكات", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "gym_staff",
        label: "المدربون والإدارة",
        items: [
          { to: "/hr", label: "المدربون وفريق الاستقبال", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/shifts", label: "ورديات الصالة", perm: "shifts", module: "core", icon: Clock, group: "admin" },
          { to: "/settings", label: "إعدادات باقات الاشتراكات", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 6. Salons & Spas
  if (sector === "salon") {
    return filterItems([
      {
        id: "beauty",
        label: "الصالون وحجز المواعيد",
        items: [
          { to: "/salon", label: "أجندة المواعيد وجدول الخدمة", perm: "pos", module: "salon", icon: Scissors, group: "main" },
          { to: "/pos", label: "كاشير الصالون وبيع المنتجات", perm: "pos", module: "pos", icon: ShoppingCart, group: "main" },
          { to: "/sales", label: "فواتير الخدمات والصبغات", perm: "sales", module: "pos", icon: Receipt, group: "main" },
          { to: "/customers", label: "سجلات العميلات وتفضيلات الخدمة", perm: "customers", module: "finance", icon: Contact, group: "main" },
        ],
      },
      {
        id: "salon_stock",
        label: "المستحضرات والمستهلكات",
        items: [
          { to: "/products", label: "مستحضرات التجميل والعناية", perm: "inventory", module: "inventory", icon: Package, group: "stock" },
          { to: "/inventory", label: "مخزون الصبغات والشامبوهات", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
        ],
      },
      {
        id: "salon_staff",
        label: "المصففون والعمولات",
        items: [
          { to: "/hr", label: "المصففون وأخصائيو التجميل", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/shifts", label: "ورديات العمل", perm: "shifts", module: "core", icon: Clock, group: "admin" },
          { to: "/finance", label: "الخزينة والعمولات اليومية", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/settings", label: "إعدادات باقات الصالون", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 7. Hotels & Hospitality PMS
  if (sector === "hotel") {
    return filterItems([
      {
        id: "hotel_ops",
        label: "الغرف والتسكين (PMS)",
        items: [
          { to: "/hospitality", label: "خريطة الغرف والتسكين", perm: "operations", module: "hospitality", icon: Hotel, group: "main" },
          { to: "/hospitality?tab=guests", label: "سجلات النزلاء والفواتير (Folio)", perm: "operations", module: "hospitality", icon: Users, group: "main" },
          { to: "/hospitality?tab=housekeeping", label: "التدبير المنزلي والنظافة", perm: "operations", module: "hospitality", icon: Bed, group: "main" },
          { to: "/restaurant/tables", label: "مطاعم وبوفيه الفندق", perm: "pos", module: "restaurant", icon: Utensils, group: "main" },
        ],
      },
      {
        id: "hotel_finance",
        label: "المالية والتدقيق الليلي",
        items: [
          { to: "/sales", label: "فواتير الإقامة والخدمات", perm: "sales", module: "", icon: Receipt, group: "money" },
          { to: "/customers", label: "شركات السياحة والحجوزات", perm: "customers", module: "finance", icon: Contact, group: "money" },
          { to: "/finance", label: "الخزائن والتدقيق الليلي", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير نسب الإشغال و RevPAR", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "hotel_admin",
        label: "فريق الفندق والإدارة",
        items: [
          { to: "/hr", label: "طاقم الاستقبال والخدمة", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/shifts", label: "ورديات الاستقبال والخدمة", perm: "shifts", module: "core", icon: Clock, group: "admin" },
          { to: "/settings", label: "إعدادات أسعار الغرف والمواسم", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 8. Wholesale & Distribution
  if (sector === "wholesale") {
    return filterItems([
      {
        id: "distribution",
        label: "الجملة ومبيعات التوزيع",
        items: [
          { to: "/wholesale", label: "لوحة الجملة وسلالم الأسعار", perm: "sales", module: "wholesale", icon: Boxes, group: "main" },
          { to: "/sales", label: "أوامر وفواتير البيع بالجملة", perm: "sales", module: "", icon: Receipt, group: "main" },
          { to: "/customers", label: "حسابات كبار العملاء والوكلاء", perm: "customers", module: "finance", icon: Contact, group: "main" },
        ],
      },
      {
        id: "bulk_stock",
        label: "المستودعات المركزية والتوريد",
        items: [
          { to: "/products", label: "دليل الأصناف والباركودات", perm: "inventory", module: "inventory", icon: Package, group: "stock" },
          { to: "/inventory", label: "أرصدة المستودعات والتحويلات", perm: "inventory", module: "inventory", icon: Warehouse, group: "stock" },
          { to: "/purchases", label: "أوامر الشراء من المصانع", perm: "purchases", module: "inventory", icon: Truck, group: "stock" },
        ],
      },
      {
        id: "wholesale_finance",
        label: "الائتمان وأوراق القبض",
        items: [
          { to: "/suppliers", label: "حسابات الموردين والمصانع", perm: "customers", module: "finance", icon: Truck, group: "money" },
          { to: "/finance", label: "الخزائن ومتابعة الشيكات والذمم", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير أعمار الديون والمبيعات", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "wholesale_admin",
        label: "المناديب والإدارة",
        items: [
          { to: "/hr", label: "سائقو سيارات التوزيع والمناديب", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/settings", label: "إعدادات سقوف الائتمان والأسعار", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 9. Construction & Contracting
  if (sector === "construction") {
    return filterItems([
      {
        id: "contracting",
        label: "المقايسات والمشاريع (BOQ)",
        items: [
          { to: "/cst", label: "لوحة المشاريع والمقايسات", perm: "operations", module: "cst", icon: HardHat, group: "main" },
          { to: "/cst?tab=boq", label: "جداول الكميات وبنود التكلفة", perm: "operations", module: "cst", icon: Boxes, group: "main" },
          { to: "/cst?tab=invoices", label: "المستخلصات الجارية والختامية", perm: "operations", module: "cst", icon: Receipt, group: "main" },
          { to: "/cst?tab=subcontractors", label: "مقاولو الباطن وحصر الأعمال", perm: "operations", module: "cst", icon: Users, group: "main" },
        ],
      },
      {
        id: "site_assets",
        label: "الموقع والمعدات والمخزن",
        items: [
          { to: "/inventory", label: "مخزن الموقع ومواد البناء", perm: "inventory", module: "inventory", icon: Warehouse, group: "stock" },
          { to: "/purchases", label: "توريدات الحديد والإسمنت والمواد", perm: "purchases", module: "inventory", icon: Truck, group: "stock" },
        ],
      },
      {
        id: "cst_finance",
        label: "المالية وتكاليف المشاريع",
        items: [
          { to: "/customers", label: "الملاك وجهات الإسناد", perm: "customers", module: "finance", icon: Contact, group: "money" },
          { to: "/suppliers", label: "موردو المواد ومقاولو الباطن", perm: "customers", module: "finance", icon: Truck, group: "money" },
          { to: "/finance", label: "العهد الموقعية والخزينة", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير ربحية المشاريع والتدفقات", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "cst_staff",
        label: "المهندسون وفريق التنفيذ",
        items: [
          { to: "/hr", label: "مهندسو المواقع والعمالة", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/settings", label: "إعدادات تكويد المشاريع", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 10. Real Estate & Property Management
  if (sector === "real_estate") {
    return filterItems([
      {
        id: "properties",
        label: "إدارة العقارات والوحدات",
        items: [
          { to: "/rec", label: "لوحة الأبراج والوحدات العقارية", perm: "operations", module: "rec", icon: Building2, group: "main" },
          { to: "/rec?tab=leases", label: "عقود الإيجار والتحصيل الدوري", perm: "operations", module: "rec", icon: Receipt, group: "main" },
          { to: "/rec?tab=maintenance", label: "بلاغات الصيانة والمرافق", perm: "operations", module: "rec", icon: Wrench, group: "main" },
          { to: "/customers", label: "دليل المستأجرين وسجلاتهم", perm: "customers", module: "finance", icon: Contact, group: "main" },
        ],
      },
      {
        id: "rec_finance",
        label: "المالية وحسابات الملاك",
        items: [
          { to: "/finance", label: "الخزينة وحافظة شيكات الإيجار", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/suppliers", label: "شركات صيانة المصاعد والمرافق", perm: "customers", module: "finance", icon: Truck, group: "money" },
          { to: "/reports", label: "كشوف حسابات الملاك وصافي الإيراد", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "rec_admin",
        label: "الإدارة والنظام",
        items: [
          { to: "/hr", label: "فريق الإشراف والتحصيل", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/settings", label: "إعدادات العقارات والعمولات", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 11. Manufacturing & Production
  if (sector === "discrete_mfg" || sector === "food_mfg" || sector === "pharma_mfg") {
    const primaryRoute = sector === "food_mfg" ? "/fod" : sector === "pharma_mfg" ? "/phm" : "/mfg";
    const primaryModule = sector === "food_mfg" ? "fod" : sector === "pharma_mfg" ? "phm" : "mfg";
    return filterItems([
      {
        id: "production",
        label: "التصنيع وخطوط الإنتاج",
        items: [
          { to: primaryRoute, label: "لوحة التحكم وأوامر الإنتاج", perm: "operations", module: primaryModule, icon: Factory, group: "main" },
          { to: `${primaryRoute}?tab=bom`, label: "شجرة المنتج والخامات (BOM)", perm: "operations", module: primaryModule, icon: Boxes, group: "main" },
          { to: `${primaryRoute}?tab=mrp`, label: "تخطيط متطلبات المواد (MRP)", perm: "operations", module: primaryModule, icon: ArrowLeftRight, group: "main" },
        ],
      },
      {
        id: "mfg_stock",
        label: "الخامات والمنتج التام",
        items: [
          { to: "/products", label: "المنتجات التامة ومواصفاتها", perm: "inventory", module: "inventory", icon: Package, group: "stock" },
          { to: "/inventory", label: "مستودعات الخامات ومستلزمات الإنتاج", perm: "inventory", module: "inventory", icon: Warehouse, group: "stock" },
          { to: "/purchases", label: "أوامر الشراء من الموردين", perm: "purchases", module: "inventory", icon: Truck, group: "stock" },
        ],
      },
      {
        id: "mfg_finance",
        label: "تكاليف الإنتاج والمالية",
        items: [
          { to: "/customers", label: "حسابات كبار العملاء والموزعين", perm: "customers", module: "finance", icon: Contact, group: "money" },
          { to: "/finance", label: "الخزائن وتكاليف التشغيل الصناعي", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير التكاليف الصناعية والإنتاجية", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "mfg_admin",
        label: "العمالة وخطوط التشغيل",
        items: [
          { to: "/hr", label: "مشغلو الماكينات وفنيو الورشة", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/shifts", label: "ورديات المصنع وخطوط الإنتاج", perm: "shifts", module: "core", icon: Clock, group: "admin" },
          { to: "/settings", label: "إعدادات مراكز التكلفة والمصنع", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 12. Field Service & Maintenance
  if (sector === "field_service") {
    return filterItems([
      {
        id: "fsm",
        label: "الصيانة والعمل الميداني",
        items: [
          { to: "/field-service", label: "أوامر الشغل وبلاغات الأعطال", perm: "operations", module: "field_service", icon: Wrench, group: "main" },
          { to: "/customers", label: "سجلات العملاء ومواقع التركيب", perm: "customers", module: "finance", icon: Contact, group: "main" },
          { to: "/sales", label: "فواتير الصيانة والزيارات", perm: "sales", module: "", icon: Receipt, group: "main" },
        ],
      },
      {
        id: "fsm_parts",
        label: "قطع الغيار والمخزن المتنقل",
        items: [
          { to: "/products", label: "كتالوج قطع الغيار والمعدات", perm: "inventory", module: "inventory", icon: Package, group: "stock" },
          { to: "/inventory", label: "مخزون المستودع وسيارة الفني", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
        ],
      },
      {
        id: "fsm_admin",
        label: "الفنيون والإدارة",
        items: [
          { to: "/hr", label: "الفنيون وفرق الصيانة", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/finance", label: "الخزينة وتحصيل الفنيين الميداني", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/settings", label: "إعدادات أنواع الأعطال والصيانة", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 13. Travel & Tourism Agencies
  if (sector === "travel") {
    return filterItems([
      {
        id: "tourism",
        label: "السياحة والرحلات",
        items: [
          { to: "/travel", label: "البرامج السياحية والأفواج", perm: "sales", module: "travel", icon: Compass, group: "main" },
          { to: "/sales", label: "فواتير الحجوزات والتذاكر", perm: "sales", module: "", icon: Receipt, group: "main" },
          { to: "/customers", label: "سجلات المسافرين والجوازات", perm: "customers", module: "finance", icon: Contact, group: "main" },
        ],
      },
      {
        id: "travel_finance",
        label: "المالية وشركات الطيران",
        items: [
          { to: "/suppliers", label: "خطوط الطيران والفنادق الشريكة", perm: "customers", module: "finance", icon: Truck, group: "money" },
          { to: "/finance", label: "الخزينة وحسابات وكلاء السفر", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير أرباح الأفواج والرحلات", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "travel_admin",
        label: "فريق الحجوزات والإدارة",
        items: [
          { to: "/hr", label: "موظفو الحجز ومسؤولو العلاقات", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/settings", label: "إعدادات برامج السفر والعمولات", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // 14. Logistics, Freight & 3PL
  if (sector === "logistics" || sector === "wms_3pl") {
    const isWms = sector === "wms_3pl";
    return filterItems([
      {
        id: "freight_ops",
        label: isWms ? "المستودعات والخدمات اللوجستية" : "الشحن وإدارة الأسطول",
        items: [
          { to: isWms ? "/wms" : "/logistics", label: isWms ? "لوحة المستودع والتخزين (3PL)" : "بوالص الشحن وتتبع المسارات", perm: "operations", module: isWms ? "wms" : "logistics", icon: isWms ? Warehouse : Truck, group: "main" },
          { to: "/sales", label: "فواتير الشحن والمناولة", perm: "sales", module: "", icon: Receipt, group: "main" },
          { to: "/customers", label: "عملاء الشحن والتخزين", perm: "customers", module: "finance", icon: Contact, group: "main" },
        ],
      },
      {
        id: "freight_stock",
        label: "المخزون ومواقع التخزين",
        items: [
          { to: "/inventory", label: "المخزون ومواقع الرفوف (Bins)", perm: "inventory", module: "inventory", icon: Boxes, group: "stock" },
        ],
      },
      {
        id: "freight_finance",
        label: "المالية وتكاليف النقل",
        items: [
          { to: "/finance", label: "الخزائن وتكاليف الوقود ومصاريف الطرق", perm: "finance", module: "finance", icon: Wallet, group: "money" },
          { to: "/reports", label: "تقارير الشحنات والمسارات اليومية", perm: "reports", module: "core", icon: BarChart3, group: "money" },
        ],
      },
      {
        id: "freight_admin",
        label: "السائقون والتشغيل",
        items: [
          { to: "/hr", label: "سائقو الشاحنات وعمال التحميل", perm: "payroll", module: "hr", icon: UserCog, group: "admin" },
          { to: "/settings", label: "إعدادات مناطق التوصيل والتسعير", perm: "settings", module: "core", icon: Settings, group: "admin" },
        ],
      },
    ]);
  }

  // Default Standard Navigation (Retail, Supermarket & General)
  const visible = NAV_ITEMS.filter((n) => (!n.perm || can(n.perm)) && (!n.module || hasModule(n.module)));
  return (Object.keys(NAV_GROUPS) as NavItem["group"][])
    .map((g) => ({
      id: g,
      label: NAV_GROUPS[g],
      items: visible.filter((n) => n.group === g),
    }))
    .filter((g) => g.items.length > 0);
}
