import type { ReferralPriority, ReferralStatus } from "./types";

// Referrals (#45): the Arabic labels of their priority and status.
export const PRIORITY_LABELS: Record<ReferralPriority, string> = { routine: "عادية", urgent: "عاجلة", emergency: "طارئة" };
export const STATUS_LABELS: Record<ReferralStatus, string> = {
  pending: "بانتظار الرد", accepted: "مقبولة", declined: "معتذر عنها", completed: "مكتملة",
};
