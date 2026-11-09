/**
 * How this build of the app is deployed (ADR-005). The cloud build talks to
 * mizan-co-api; the on-premise build (single device / LAN) is served by the
 * install's own server, from the same address, and has no owner accounts.
 */
export const IS_ON_PREMISE = import.meta.env.VITE_DEPLOYMENT === "onprem";
