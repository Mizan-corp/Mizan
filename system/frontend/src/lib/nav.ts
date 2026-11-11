/**
 * Menus come from the backend (ADR-006 phase 5): modules declare their screens, the activity
 * arranges them, and each role can have its own home, menu and dashboard (the builder edits it).
 * /settings/screens returns what the role the user acts as may see; this file only maps icon
 * names to components.
 */
import { useQuery } from "@tanstack/react-query";
import {
  Archive, ArrowLeftRight, Bed, Blocks, Boxes, Briefcase, Building, Building2, Calendar, ChartColumn,
  ChefHat, Clock, Compass, Contact, Dumbbell, Factory, Flame, FlaskConical, Globe, GraduationCap,
  HardHat, HeartPulse, Hotel, Landmark, LayoutDashboard, LayoutGrid, Microscope, Package, Palette, Pill,
  Printer, Receipt, Scale, Scissors, Settings, Shield, ShieldCheck, ShoppingCart, Stethoscope, Store,
  Ticket, Tractor, Truck, UserCog, Users, Utensils, Wallet, Warehouse, Wrench, Zap, Circle,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";

export const ICONS: Record<string, LucideIcon> = {
  Archive, ArrowLeftRight, Bed, Blocks, Boxes, Briefcase, Building, Building2, Calendar, ChartColumn,
  BarChart3: ChartColumn, ChefHat, Clock, Compass, Contact, Dumbbell, Factory, Flame, FlaskConical, Globe,
  GraduationCap, HardHat, HeartPulse, Hotel, Landmark, LayoutDashboard, LayoutGrid, Microscope, Package,
  Palette, Pill, Printer, Receipt, Scale, Scissors, Settings, Shield, ShieldCheck, ShoppingCart,
  Stethoscope, Store, Ticket, Tractor, Truck, UserCog, Users, Utensils, Wallet, Warehouse, Wrench, Zap,
};

export function iconFor(name: string | null | undefined): LucideIcon {
  return (name && ICONS[name]) || Circle;
}

export interface ScreenItem { id: string; path: string; label: string; icon: string | null; module?: string }
export interface MenuGroup { id: string; label: string; items: ScreenItem[] }
export interface DashboardWidget { id: string; label: string; size: "s" | "m" | "l" | null; module: string }
export interface RoleScreens {
  home: string;
  menu: MenuGroup[];
  dashboard: DashboardWidget[];
  screens: ScreenItem[];
  custom: boolean;
}

/** The acting role's home, menu, dashboard and available screens. */
export function useRoleScreens() {
  const roleId = useAuth((s) => s.user?.acting_role?.id ?? "none");
  return useQuery({
    queryKey: ["role-screens", roleId],
    queryFn: () => api.get<RoleScreens>("/settings/screens"),
    staleTime: 5 * 60_000,
  });
}
