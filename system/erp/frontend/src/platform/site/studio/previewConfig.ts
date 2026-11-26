/** Build-time preview configuration only. Never read destinations or tokens from URLs. */
export const HOSTED_API = 'https://api.allmizan.live/api';
export type PreviewConfig = { apiBase: string; label: string };
export function previewConfig(value: unknown): PreviewConfig {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Preview configuration is missing.');
  const data = value as Record<string, unknown>;
  if (Object.keys(data).some(key => !['apiBase', 'label'].includes(key))) throw Error('Unknown preview configuration.');
  // One origin for HttpOnly session cookies. Cross-origin APIs need a reviewed deployment
  // proxy, not client-controlled hosts or browser-visible permanent credentials.
  // The one other allowed value is the production API origin the ERP itself uses (single
  // sign-on with the ERP session token, never a cookie or a URL-supplied host).
  if (data.apiBase !== '/api' && data.apiBase !== HOSTED_API) throw Error('Preview requires the same-origin /api route or the production API.');
  if (typeof data.label !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9 .-]{0,59}$/.test(data.label)) throw Error('A plain preview label is required.');
  return { apiBase: data.apiBase, label: data.label };
}
