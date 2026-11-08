/**
 * HLT-01 — Healthcare Organization & Facility Management
 * Core TypeScript Domain Models and Interfaces
 */

export type FacilityType =
  | "hospital"
  | "medical_center"
  | "clinic"
  | "diagnostic_center"
  | "specialized_center";

export type FacilityStatus =
  | "active"
  | "inactive"
  | "under_construction"
  | "suspended";

export type DepartmentCategory =
  | "clinical"
  | "diagnostic"
  | "surgical"
  | "emergency"
  | "administrative"
  | "support_services";

export type UnitType =
  | "outpatient_clinic"
  | "inpatient_ward"
  | "icu_ccu"
  | "day_surgery"
  | "imaging_suite"
  | "laboratory_section"
  | "pharmacy_dispensary"
  | "emergency_bay"
  | "administrative_office";

export type RoomType =
  | "consultation_room"
  | "examination_room"
  | "procedure_room"
  | "operating_theatre"
  | "recovery_room"
  | "blood_draw_station"
  | "xray_room"
  | "mri_suite"
  | "ct_suite"
  | "ultrasound_room"
  | "isolation_room"
  | "nursing_station"
  | "doctor_office"
  | "waiting_lounge";

export type RoomAvailabilityStatus =
  | "available"
  | "occupied"
  | "reserved"
  | "sanitizing"
  | "maintenance"
  | "out_of_service";

export type ServiceDeliveryType =
  | "consultation"
  | "diagnostic_imaging"
  | "laboratory_test"
  | "surgical_procedure"
  | "wound_care"
  | "vaccination"
  | "dialysis"
  | "physiotherapy"
  | "emergency_triage";

export interface OperatingDaySchedule {
  day: "saturday" | "sunday" | "monday" | "tuesday" | "wednesday" | "thursday" | "friday";
  dayNameAr: string;
  dayNameEn: string;
  isOpen: boolean;
  shifts: Array<{
    id: string;
    name: string;
    startTime: string; // "08:00"
    endTime: string;   // "16:00"
    breakStartTime?: string;
    breakEndTime?: string;
  }>;
}

export interface HolidayException {
  id: string;
  facilityId: string;
  title: string;
  startDate: string;
  endDate: string;
  isFullClosure: boolean;
  specialHours?: { open: string; close: string };
  reason: string;
  appliesToAllDepartments: boolean;
  affectedDepartmentIds?: string[];
}

export interface HealthcareOrganization {
  id: string;
  legalName: string;
  displayName: string;
  code: string;
  type: string;
  logoUrl?: string;
  description: string;
  website: string;
  contactEmail: string;
  phone: string;
  registrationNumber: string;
  taxId: string;
  healthcareLicenseNumber: string;
  registrationAuthority: string;
  issueDate: string;
  expiryDate: string;
  documents: Array<{ id: string; name: string; size: string; type: string; uploadDate: string }>;
  address: {
    country: string;
    governorate: string;
    city: string;
    district: string;
    street: string;
    postalCode: string;
    primaryAddress: string;
    billingAddress: string;
  };
  regionalSettings: {
    currency: string;
    timeZone: string;
    defaultLanguage: string;
    dateFormat: string;
    timeFormat: string;
    fiscalYearStart: string;
  };
  preferences: {
    defaultFacilityId: string;
    autoNotifyOnStatusChange: boolean;
    requireDepartmentSignoff: boolean;
    numberingPrefix: string;
  };
}

export interface HealthcareFacilityItem {
  id: string;
  code: string;
  name: string;
  nameEn: string;
  type: FacilityType;
  status: FacilityStatus;
  description: string;
  logoUrl?: string;
  location: {
    country: string;
    governorate: string;
    city: string;
    district: string;
    address: string;
    postalCode: string;
  };
  administration: {
    managerName: string;
    managerEmail: string;
    managerPhone: string;
    medicalDirector: string;
    adminContact: string;
  };
  operations: {
    timeZone: string;
    currency: string;
    language: string;
    is24HoursEmergency: boolean;
    workingDays: string[];
    standardHours: string;
  };
  stats: {
    departmentCount: number;
    buildingCount: number;
    unitCount: number;
    roomCount: number;
    activeServicesCount: number;
    staffCount: number;
  };
  createdAt: string;
  updatedAt: string;
}

export interface BuildingItem {
  id: string;
  facilityId: string;
  code: string;
  name: string;
  nameEn: string;
  floorsCount: number;
  locationWithinFacility: string;
  managerName: string;
  status: "active" | "maintenance" | "renovation";
  notes?: string;
  floors: FloorItem[];
}

export interface FloorItem {
  id: string;
  buildingId: string;
  facilityId: string;
  floorNumber: number; // 0 = Ground Floor, 1 = First, etc.
  name: string;
  nameEn: string;
  departmentsCount: number;
  unitsCount: number;
  roomsCount: number;
  status: "active" | "restricted" | "closed";
}

export interface DepartmentItem {
  id: string;
  facilityId: string;
  facilityName: string;
  code: string;
  name: string;
  nameEn: string;
  category: DepartmentCategory;
  parentDepartmentId?: string;
  buildingId: string;
  buildingName: string;
  floorId: string;
  floorName: string;
  managerName: string;
  managerTitle: string;
  staffCount: number;
  unitsCount: number;
  status: "active" | "inactive" | "on_hold";
  description: string;
  availableServices: string[];
  operatingHours: string;
}

export interface UnitItem {
  id: string;
  facilityId: string;
  departmentId: string;
  departmentName: string;
  code: string;
  name: string;
  nameEn: string;
  unitType: UnitType;
  assignedManager: string;
  roomsCount: number;
  status: "active" | "inactive" | "maintenance";
  description?: string;
}

export interface RoomItem {
  id: string;
  facilityId: string;
  departmentId: string;
  unitId: string;
  unitName: string;
  floorId: string;
  code: string;
  name: string;
  roomType: RoomType;
  capacity: number;
  availability: RoomAvailabilityStatus;
  equipmentReferences: string[];
  notes?: string;
}

export interface ServiceLocationItem {
  id: string;
  code: string;
  name: string;
  facilityId: string;
  facilityName: string;
  departmentId: string;
  departmentName: string;
  unitId: string;
  unitName: string;
  roomId: string;
  roomCode: string;
  supportedServices: ServiceDeliveryType[];
  assignedStaff: string[];
  availabilitySchedule: string;
  status: "active" | "temporarily_closed" | "maintenance";
}

export interface FacilityActivityLogItem {
  id: string;
  facilityId: string;
  facilityName: string;
  action: string;
  actorName: string;
  actorRole: string;
  entityType: "facility" | "department" | "building" | "unit" | "room" | "schedule";
  entityName: string;
  timestamp: string;
  details: string;
}
