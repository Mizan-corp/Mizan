// Bounded inline icon set for icon_list blocks: no icon font, no network fetch.
// Mirrored in shared/backend/app/platform/site/render.py (_ICON_MARKUP); keep entries identical.
export const ICON_MARKUP: Record<string, string> = {
  Wrench: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.8 2.8-2-2 2.8-2.8z"/>',
  Laptop: '<rect x="4" y="5" width="16" height="10" rx="1.5"/><path d="M2 19h20"/>',
  Smartphone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18.5h2"/>',
  ShieldCheck: '<path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3z"/><path d="M9 12l2 2 4-4"/>',
  Truck: '<path d="M1.5 7H14v9H1.5z"/><path d="M14 10h4l3 3v3h-7"/><circle cx="6" cy="18" r="1.6"/><circle cx="17.5" cy="18" r="1.6"/>',
  Check: '<path d="M4 12.5l5 5L20 6.5"/>',
  Star: '<path d="M12 3l2.7 5.6 6.1.8-4.5 4.2 1.1 6-5.4-2.9L6.6 19.6l1.1-6L3.2 9.4l6.1-.8z"/>',
  Headphones: '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><path d="M4 14h3v6H6a2 2 0 0 1-2-2v-4z"/><path d="M20 14h-3v6h1a2 2 0 0 0 2-2v-4z"/>',
  Cpu: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10.5" y="10.5" width="3" height="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  BatteryCharging: '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/><path d="M11 9l-2.5 3.5H11l-1 3 4-4.5h-2.5L13 9z"/>',
  Camera: '<path d="M4 7h3l2-2h6l2 2h3v12H4z"/><circle cx="12" cy="13" r="3.2"/>',
  Home: '<path d="M3 11l9-8 9 8"/><path d="M5 9.5V20h14V9.5"/>',
  Mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 7l8.5 6 8.5-6"/>',
  MapPin: '<path d="M12 21s-6-5.2-6-10a6 6 0 0 1 12 0c0 4.8-6 10-6 10z"/><circle cx="12" cy="11" r="2.2"/>',
  ArrowRight: '<path d="M4 12h16"/><path d="M13 5l7 7-7 7"/>',
  Sparkles: '<path d="M12 4l1.7 4.3L18 10l-4.3 1.7L12 16l-1.7-4.3L6 10l4.3-1.7z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  Clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  CreditCard: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
  Package: '<path d="M12 3l8 4v10l-8 4-8-4V7z"/><path d="M4 7l8 4 8-4"/><path d="M12 11v10"/>',
  Heart: '<path d="M12 20s-7-4.4-9-9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.6-9 9-9 9z"/>',
  ShoppingBag: '<path d="M16 10a4 4 0 0 1-8 0M3.103 6.034h17.794M3.4 5.467a2 2 0 0 0-.4 1.2V20a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6.667a2 2 0 0 0-.4-1.2l-2-2.667A2 2 0 0 0 17 2H7a2 2 0 0 0-1.6.8z"/>',
  BookOpen: '<path d="M12 5v16M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"/>',
  Stethoscope: '<path d="M11 2v2M5 2v2M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1M8 15a6 6 0 0 0 12 0v-3"/><circle cx="20" cy="10" r="2"/>',
  HardDriveDownload: '<path d="M12 2v8M16 6l-4 4-4-4"/><rect width="20" height="8" x="2" y="14" rx="2"/><path d="M6 18h.01M10 18h.01"/>',
  MemoryStick: '<path d="M12 12v-2M12 18v-2M16 12v-2M16 18v-2M2 11h1.5M20 18v-2M20.5 11H22M4 18v-2M8 12v-2M8 18v-2"/><rect x="2" y="6" width="20" height="10" rx="2"/>',
  MonitorCog: '<path d="M12 17v4M14.305 7.53l.923-.382M15.228 4.852l-.923-.383M16.852 3.228l-.383-.924M16.852 8.772l-.383.923M19.148 3.228l.383-.924M19.53 9.696l-.382-.924M20.772 4.852l.924-.383M20.772 7.148l.924.383M22 13v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7M8 21h8"/><circle cx="18" cy="6" r="3"/>',
  Network: '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3M12 12V8"/>',
  Globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20"/>',
  Building2: '<path d="M10 12h4M10 8h4M14 21v-3a2 2 0 0 0-4 0v3M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/>',
  MessageCircle: '<path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719"/>',
  Banknote: '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
};
export const FALLBACK_ICON = '<circle cx="12" cy="12" r="5"/>';
export function iconNames(): string[] { return Object.keys(ICON_MARKUP); }
export function IconGlyph({name}:{name:string}) {
  const inner = ICON_MARKUP[name] ?? FALLBACK_ICON; // unknown stored names render as a dot
  return <svg className="mz-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
    dangerouslySetInnerHTML={{__html: inner}} />;
}
