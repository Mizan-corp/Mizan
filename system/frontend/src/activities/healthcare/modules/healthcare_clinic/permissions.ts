import { useAuth } from "@/stores/auth";

/** What the acting role may do in the clinic; mirrors the require_clinic_* guards in router.py (#131).
 *  The umbrella "clinic" (admin, manager) passes every action check, never the clinician check. */
export function useClinicPerms() {
  const can = useAuth((s) => s.can);
  const has = (...perms: string[]) => can(["clinic", ...perms].join("|"));
  return {
    manage: has("clinic:manage"),
    book: has("clinic:manage", "clinic:doctor"),
    queue: has("clinic:manage", "clinic:doctor", "clinic:nurse"),
    doctor: has("clinic:doctor"),
    ward: has("clinic:nurse", "clinic:manage"),
    dispense: has("clinic:dispense"),
    lab: has("clinic:lab"),
    billing: has("clinic:billing"),
    clinician: can("clinic:doctor|clinic:nurse"),
    privacy: can("clinic:privacy"),
  };
}

export type ClinicPerms = ReturnType<typeof useClinicPerms>;
