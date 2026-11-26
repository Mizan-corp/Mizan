import { useState } from "react";
import AppShell from "./components/AppShell";
import {
  INITIAL_ORGANIZATION,
  INITIAL_FACILITIES,
  INITIAL_BUILDINGS,
  INITIAL_DEPARTMENTS,
  INITIAL_UNITS,
  INITIAL_ROOMS,
  INITIAL_SERVICE_LOCATIONS,
  INITIAL_SCHEDULE,
  INITIAL_HOLIDAYS,
  INITIAL_ACTIVITY_LOGS
} from "./mockData";
import {
  HealthcareOrganization,
  HealthcareFacilityItem,
  BuildingItem,
  FloorItem,
  DepartmentItem,
  UnitItem,
  RoomItem,
  ServiceLocationItem,
  OperatingDaySchedule,
  HolidayException,
  FacilityActivityLogItem,
  RoomAvailabilityStatus
} from "./types";

// Screens
import Screen01_Dashboard from "./screens/Screen01_Dashboard";
import Screen02_OrgProfile from "./screens/Screen02_OrgProfile";
import Screen03_Facilities from "./screens/Screen03_Facilities";
import Screen04_CreateFacility from "./screens/Screen04_CreateFacility";
import Screen05_FacilityDetails from "./screens/Screen05_FacilityDetails";
import Screen06_BuildingsFloors from "./screens/Screen06_BuildingsFloors";
import Screen07_Departments from "./screens/Screen07_Departments";
import Screen08_UnitsRooms from "./screens/Screen08_UnitsRooms";
import Screen09_ServiceLocations from "./screens/Screen09_ServiceLocations";
import Screen10_OperatingSchedule from "./screens/Screen10_OperatingSchedule";
import Screen11_FacilitySettings from "./screens/Screen11_FacilitySettings";

export default function FacilityManagementView() {
  // Master State
  const [organization, setOrganization] = useState<HealthcareOrganization>(INITIAL_ORGANIZATION);
  const [facilities, setFacilities] = useState<HealthcareFacilityItem[]>(INITIAL_FACILITIES);
  const [buildings, setBuildings] = useState<BuildingItem[]>(INITIAL_BUILDINGS);
  const [departments, setDepartments] = useState<DepartmentItem[]>(INITIAL_DEPARTMENTS);
  const [units, setUnits] = useState<UnitItem[]>(INITIAL_UNITS);
  const [rooms, setRooms] = useState<RoomItem[]>(INITIAL_ROOMS);
  const [serviceLocations, setServiceLocations] = useState<ServiceLocationItem[]>(INITIAL_SERVICE_LOCATIONS);
  const [schedule, setSchedule] = useState<OperatingDaySchedule[]>(INITIAL_SCHEDULE);
  const [holidays, setHolidays] = useState<HolidayException[]>(INITIAL_HOLIDAYS);
  const [activityLogs, setActivityLogs] = useState<FacilityActivityLogItem[]>(INITIAL_ACTIVITY_LOGS);

  // Navigation & Context State
  const [activeScreenId, setActiveScreenId] = useState<string>("dashboard");
  const [currentFacilityId, setCurrentFacilityId] = useState<string | "all">("all");
  const [editingFacility, setEditingFacility] = useState<HealthcareFacilityItem | null>(null);

  // Selected Facility for Details view
  const selectedFacility =
    facilities.find((f) => f.id === currentFacilityId) || facilities[0];

  // Helper to log actions
  const logAction = (
    action: string,
    entityType: FacilityActivityLogItem["entityType"],
    entityName: string,
    details: string,
    facId?: string
  ) => {
    const newLog: FacilityActivityLogItem = {
      id: `act-${Date.now()}`,
      facilityId: facId || currentFacilityId !== "all" ? (facId || currentFacilityId) : facilities[0].id,
      facilityName: facilities.find((f) => f.id === (facId || currentFacilityId))?.name || "المجموعة العامة",
      action,
      actorName: "د. أسامة حسني",
      actorRole: "مدير النظام الطبي",
      entityType,
      entityName,
      timestamp: new Date().toISOString(),
      details,
    };
    setActivityLogs((prev) => [newLog, ...prev]);
  };

  // Facility handlers
  const handleSaveFacility = (newOrUpdated: HealthcareFacilityItem) => {
    const exists = facilities.some((f) => f.id === newOrUpdated.id);
    if (exists) {
      setFacilities((prev) => prev.map((f) => (f.id === newOrUpdated.id ? newOrUpdated : f)));
      logAction("تحديث بيانات منشأة", "facility", newOrUpdated.name, `تم تعديل بيانات منشأة ${newOrUpdated.name}`, newOrUpdated.id);
    } else {
      setFacilities((prev) => [newOrUpdated, ...prev]);
      logAction("إنشاء منشأة جديدة", "facility", newOrUpdated.name, `تم تسجيل المنشأة الكودية ${newOrUpdated.code}`, newOrUpdated.id);
    }
    setCurrentFacilityId(newOrUpdated.id);
    setActiveScreenId("facility_details");
    setEditingFacility(null);
  };

  // Buildings & Floors handlers
  const handleAddBuilding = (newBuilding: BuildingItem) => {
    setBuildings((prev) => [...prev, newBuilding]);
    logAction("إضافة مبنى جديد", "building", newBuilding.name, `تمت إضافة مبنى ${newBuilding.name} للمنشأة`, newBuilding.facilityId);
  };

  const handleAddFloor = (buildingId: string, newFloor: FloorItem) => {
    setBuildings((prev) =>
      prev.map((b) =>
        b.id === buildingId ? { ...b, floors: [...b.floors, newFloor], floorsCount: b.floors.length + 1 } : b
      )
    );
    logAction("إضافة طابق", "building", newFloor.name, `تمت إضافة ${newFloor.name} للمبنى`, newFloor.facilityId);
  };

  // Department handlers
  const handleAddDepartment = (newDept: DepartmentItem) => {
    setDepartments((prev) => [...prev, newDept]);
    logAction("إضافة قسم طبي", "department", newDept.name, `تم اعتماد قسم ${newDept.name} التابع للمنشأة`, newDept.facilityId);
  };

  // Units & Rooms handlers
  const handleAddUnit = (newUnit: UnitItem) => {
    setUnits((prev) => [...prev, newUnit]);
    logAction("إضافة وحدة سريرية", "unit", newUnit.name, `تم إنشاء وحدة ${newUnit.name}`, newUnit.facilityId);
  };

  const handleAddRoom = (newRoom: RoomItem) => {
    setRooms((prev) => [...prev, newRoom]);
    logAction("إضافة غرفة سريرية", "room", newRoom.name, `تم تسجيل غرفة ${newRoom.code} بالوحدة`, newRoom.facilityId);
  };

  const handleUpdateRoomStatus = (roomId: string, status: RoomAvailabilityStatus) => {
    setRooms((prev) =>
      prev.map((r) => (r.id === roomId ? { ...r, availability: status } : r))
    );
  };

  // Service Locations handlers
  const handleAddServiceLocation = (newLoc: ServiceLocationItem) => {
    setServiceLocations((prev) => [...prev, newLoc]);
    logAction("إضافة نقطة خدمة طبية", "room", newLoc.name, `تم تسجيل نقطة تقديم الخدمة ${newLoc.name}`, newLoc.facilityId);
  };

  const handleUpdateServiceLocationStatus = (
    id: string,
    status: "active" | "temporarily_closed" | "maintenance"
  ) => {
    setServiceLocations((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status } : s))
    );
  };

  // Holidays handlers
  const handleAddHoliday = (newHol: HolidayException) => {
    setHolidays((prev) => [...prev, newHol]);
    logAction("تسجيل عطلة رسمية", "schedule", newHol.title, `تمت جدولة إغلاق عطلة: ${newHol.title}`, newHol.facilityId);
  };

  const handleDeleteHoliday = (id: string) => {
    setHolidays((prev) => prev.filter((h) => h.id !== id));
  };

  // Breadcrumbs Generator
  const getBreadcrumbs = () => {
    const list: Array<{ label: string; screenId?: string }> = [
      { label: "ميزان كير", screenId: "dashboard" },
    ];

    if (activeScreenId === "dashboard") {
      list.push({ label: "لوحة التحكم والمؤشرات" });
    } else if (activeScreenId === "org_profile") {
      list.push({ label: "ملف المنظمة والاعتمادات" });
    } else if (activeScreenId === "facilities") {
      list.push({ label: "إدارة المنشآت الطبية" });
    } else if (activeScreenId === "create_facility") {
      list.push({ label: "المنشآت", screenId: "facilities" });
      list.push({ label: editingFacility ? "تعديل منشأة" : "إضافة منشأة جديدة" });
    } else if (activeScreenId === "facility_details") {
      list.push({ label: "المنشآت", screenId: "facilities" });
      list.push({ label: selectedFacility?.name || "تفاصيل المنشأة" });
    } else if (activeScreenId === "buildings") {
      list.push({ label: "المباني والطوابق" });
    } else if (activeScreenId === "departments") {
      list.push({ label: "الأقسام الطبية والإدارية" });
    } else if (activeScreenId === "units_rooms") {
      list.push({ label: "الوحدات والغرف السريرية" });
    } else if (activeScreenId === "service_locations") {
      list.push({ label: "نقاط تقديم الخدمات الطبية" });
    } else if (activeScreenId === "operating_hours") {
      list.push({ label: "ساعات العمل والمناوبات" });
    } else if (activeScreenId === "holidays") {
      list.push({ label: "العطلات والاستثناءات" });
    } else if (activeScreenId === "facility_settings") {
      list.push({ label: "إعدادات المنشأة" });
    } else if (activeScreenId === "users_access") {
      list.push({ label: "المستخدمون وصلاحيات المنشأة" });
    } else if (activeScreenId === "audit_logs") {
      list.push({ label: "سجل التدقيق الإداري" });
    }

    return list;
  };

  return (
    <AppShell
      organization={organization}
      facilities={facilities}
      currentFacilityId={currentFacilityId}
      onSelectFacility={(facId) => {
        setCurrentFacilityId(facId);
        if (facId !== "all" && activeScreenId === "facilities") {
          setActiveScreenId("facility_details");
        }
      }}
      activeScreenId={activeScreenId}
      onNavigate={(screenId) => {
        setActiveScreenId(screenId);
        if (screenId === "create_facility") setEditingFacility(null);
      }}
      breadcrumbs={getBreadcrumbs()}
      onQuickAction={(action) => {
        if (action === "add_facility") {
          setEditingFacility(null);
          setActiveScreenId("create_facility");
        } else if (action === "add_department") {
          setActiveScreenId("departments");
        } else if (action === "add_room") {
          setActiveScreenId("units_rooms");
        }
      }}
    >
      {/* ─── SCREEN 01: DASHBOARD ────────────────────────────────────── */}
      {activeScreenId === "dashboard" && (
        <Screen01_Dashboard
          organization={organization}
          facilities={facilities}
          departments={departments}
          activityLogs={activityLogs}
          onSelectFacility={(facId) => {
            setCurrentFacilityId(facId);
            setActiveScreenId("facility_details");
          }}
          onNavigate={setActiveScreenId}
        />
      )}

      {/* ─── SCREEN 02: ORGANIZATION PROFILE ─────────────────────────── */}
      {activeScreenId === "org_profile" && (
        <Screen02_OrgProfile
          organization={organization}
          onUpdateOrganization={(updated) => {
            setOrganization(updated);
            logAction("تحديث بيانات المنظمة", "facility", updated.displayName, "تم تحديث الملف القانوني والاعتمادات");
          }}
        />
      )}

      {/* ─── SCREEN 03: FACILITIES MANAGEMENT ────────────────────────── */}
      {activeScreenId === "facilities" && (
        <Screen03_Facilities
          facilities={facilities}
          onSelectFacility={(facId) => {
            setCurrentFacilityId(facId);
            setActiveScreenId("facility_details");
          }}
          onNavigate={setActiveScreenId}
          onAddFacility={() => {
            setEditingFacility(null);
            setActiveScreenId("create_facility");
          }}
          onEditFacility={(fac) => {
            setEditingFacility(fac);
            setActiveScreenId("create_facility");
          }}
        />
      )}

      {/* ─── SCREEN 04: CREATE / EDIT FACILITY ───────────────────────── */}
      {activeScreenId === "create_facility" && (
        <Screen04_CreateFacility
          organization={organization}
          existingFacilities={facilities}
          initialData={editingFacility}
          onSave={handleSaveFacility}
          onCancel={() => setActiveScreenId("facilities")}
        />
      )}

      {/* ─── SCREEN 05: FACILITY DETAILS PROFILE ─────────────────────── */}
      {activeScreenId === "facility_details" && (
        <Screen05_FacilityDetails
          facility={selectedFacility}
          organization={organization}
          buildings={buildings}
          departments={departments}
          units={units}
          rooms={rooms}
          serviceLocations={serviceLocations}
          activityLogs={activityLogs}
          onNavigate={setActiveScreenId}
          onEditFacility={(fac) => {
            setEditingFacility(fac);
            setActiveScreenId("create_facility");
          }}
          onBackToFacilities={() => setActiveScreenId("facilities")}
        />
      )}

      {/* ─── SCREEN 06: BUILDINGS & FLOORS ───────────────────────────── */}
      {activeScreenId === "buildings" && (
        <Screen06_BuildingsFloors
          buildings={buildings}
          facilities={facilities}
          departments={departments}
          rooms={rooms}
          currentFacilityId={currentFacilityId}
          onAddBuilding={handleAddBuilding}
          onAddFloor={handleAddFloor}
        />
      )}

      {/* ─── SCREEN 07: DEPARTMENTS MANAGEMENT ───────────────────────── */}
      {activeScreenId === "departments" && (
        <Screen07_Departments
          departments={departments}
          facilities={facilities}
          buildings={buildings}
          currentFacilityId={currentFacilityId}
          onAddDepartment={handleAddDepartment}
          onNavigate={setActiveScreenId}
        />
      )}

      {/* ─── SCREEN 08: UNITS & ROOMS ────────────────────────────────── */}
      {activeScreenId === "units_rooms" && (
        <Screen08_UnitsRooms
          units={units}
          rooms={rooms}
          departments={departments}
          facilities={facilities}
          currentFacilityId={currentFacilityId}
          onAddUnit={handleAddUnit}
          onAddRoom={handleAddRoom}
          onUpdateRoomStatus={handleUpdateRoomStatus}
        />
      )}

      {/* ─── SCREEN 09: SERVICE LOCATIONS ────────────────────────────── */}
      {activeScreenId === "service_locations" && (
        <Screen09_ServiceLocations
          serviceLocations={serviceLocations}
          facilities={facilities}
          departments={departments}
          rooms={rooms}
          currentFacilityId={currentFacilityId}
          onAddServiceLocation={handleAddServiceLocation}
          onUpdateStatus={handleUpdateServiceLocationStatus}
        />
      )}

      {/* ─── SCREEN 10: OPERATING SCHEDULE & HOLIDAYS ────────────────── */}
      {(activeScreenId === "operating_hours" || activeScreenId === "holidays") && (
        <Screen10_OperatingSchedule
          schedule={schedule}
          holidays={holidays}
          facilities={facilities}
          departments={departments}
          currentFacilityId={currentFacilityId}
          onUpdateSchedule={(newSched) => {
            setSchedule(newSched);
            logAction("تحديث ساعات العمل", "schedule", "جدول العمل الأسبوعي", "تم تحديث ورديات العمل وساعات الاستقبال");
          }}
          onAddHoliday={handleAddHoliday}
          onDeleteHoliday={handleDeleteHoliday}
        />
      )}

      {/* ─── SCREEN 11: FACILITY SETTINGS ────────────────────────────── */}
      {activeScreenId === "facility_settings" && (
        <Screen11_FacilitySettings
          facility={selectedFacility}
          onUpdateFacility={(updated) => {
            setFacilities((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
            logAction("تحديث إعدادات المنشأة", "facility", updated.name, "تم تحديث سياسات الحجز والترقيم والإشعارات", updated.id);
          }}
        />
      )}

      {/* ─── USERS & ACCESS (GOVERNANCE ROUTE) ───────────────────────── */}
      {activeScreenId === "users_access" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
            <div>
              <h2 className="text-xl font-bold text-[#0F172A]">المستخدمون وصلاحيات المنشأة (Users & Access)</h2>
              <p className="text-xs text-[#64748B]">إدارة نفاذ الكوادر الطبية والإدارية وفق هيكل الصلاحيات RBAC / ABAC المعتمد.</p>
            </div>
          </div>
          <div className="p-8 text-center bg-white rounded-xl border border-[#E2E8F0] text-xs text-[#64748B] space-y-3">
            <p>
              يتم إدارة تعيينات الكوادر الطبية والمناوبات عبر موديول الصلاحيات وحوكمة النفاذ المرتبط بنطاق منشأة:{" "}
              <strong className="text-[#0F172A]">{selectedFacility?.name}</strong>.
            </p>
            <button
              onClick={() => setActiveScreenId("facilities")}
              className="px-4 py-2 rounded-lg bg-[#1E3A8A] text-white font-semibold"
            >
              العودة لقائمة المنشآت
            </button>
          </div>
        </div>
      )}

      {/* ─── AUDIT LOGS (GOVERNANCE ROUTE) ───────────────────────────── */}
      {activeScreenId === "audit_logs" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
            <div>
              <h2 className="text-xl font-bold text-[#0F172A]">سجل التدقيق الإداري والتشغيلي (Audit Trail)</h2>
              <p className="text-xs text-[#64748B]">توثيق غير قابل للتعديل لكافة العمليات الإدارية، تعديلات التراخيص، وهيكل المنشآت.</p>
            </div>
            <span className="text-xs font-mono font-bold bg-[#F1F5F9] text-[#475569] px-2.5 py-1 rounded-lg">
              {activityLogs.length} عملية مسجلة
            </span>
          </div>

          <div className="rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-2xs">
            <table className="w-full text-right text-xs">
              <thead className="bg-[#F8FAFC] text-[#475569] font-bold border-b border-[#E2E8F0]">
                <tr>
                  <th className="py-2.5 px-4">الإجراء</th>
                  <th className="py-2.5 px-4">الكيان المتأثر</th>
                  <th className="py-2.5 px-4">المنشأة</th>
                  <th className="py-2.5 px-4">المسؤول والدور</th>
                  <th className="py-2.5 px-4">التفاصيل</th>
                  <th className="py-2.5 px-4">التوقيت</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {activityLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-[#F8FAFC]">
                    <td className="py-2.5 px-4 font-bold text-[#0F172A]">{log.action}</td>
                    <td className="py-2.5 px-4 font-medium text-[#1E3A8A]">{log.entityName}</td>
                    <td className="py-2.5 px-4 text-[#475569]">{log.facilityName}</td>
                    <td className="py-2.5 px-4">
                      <div className="font-semibold text-[#0F172A]">{log.actorName}</div>
                      <div className="text-[10px] text-[#64748B]">{log.actorRole}</div>
                    </td>
                    <td className="py-2.5 px-4 text-[#64748B]">{log.details}</td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-[#64748B]">
                      {new Date(log.timestamp).toLocaleString("ar-EG")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </AppShell>
  );
}
