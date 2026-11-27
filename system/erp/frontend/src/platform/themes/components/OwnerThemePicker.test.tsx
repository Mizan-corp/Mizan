// @vitest-environment jsdom
// Owner appearance picker: Classic is the default, nothing saves until Save, back-to-Classic
// sends the Classic payload, and the Studio button opens Studio in a new tab.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const h = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { get: h.get, put: h.put }, ApiError: class extends Error {} }));
vi.mock("@/stores/auth", () => ({ useAuth: (sel: any) => sel({ can: () => true, tenant: null, setTenant: vi.fn() }) }));
vi.mock("@/stores/ui", () => ({ useUiStore: () => ({ layoutMode: "sidebar", setLayoutMode: vi.fn() }), LAYOUT_MODES: [{ id: "sidebar", name: "الشريط الجانبي (Sidebar)" }] }));
vi.mock("@/components/ui", () => ({
  Button: (p: any) => <button {...p} />, Spinner: () => <i />, useToast: () => ({ toast: vi.fn() }),
  Badge: () => null, ConfirmDialog: () => null, Modal: () => null,
}));

import { CLASSIC_DRAFT, CLASSIC_THEME_ID, OwnerThemePicker, STUDIO_URL, savePayload } from "./OwnerThemePicker";

const sw = ["#651e2c", "#faf6f0", "#2f1419", "#c9a", "#fff"];
function routes(path: string) {
  if (path === "/themes") return Promise.resolve({ current: "mizan", items: [
    { id: "mizan", name: "ميزان", swatches: sw, current: true }, { id: "cobalt", name: "كوبالت", swatches: sw, current: false }] });
  if (path === "/themes/palettes") return Promise.resolve({ items: [{ id: "ocean", swatches: sw }], families: ["Manrope", "Tajawal"] });
  return Promise.resolve({ id: "mizan", palette: "", fonts: {} });
}
function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><OwnerThemePicker /></QueryClientProvider>);
}
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("savePayload", () => {
  it("sends only chosen fonts and an empty palette for the theme's own colours", () => {
    expect(savePayload(CLASSIC_DRAFT)).toEqual({ id: CLASSIC_THEME_ID, palette: "", fonts: {} });
    expect(savePayload({ theme: "cobalt", palette: "ocean", body: "Tajawal", display: "" }))
      .toEqual({ id: "cobalt", palette: "ocean", fonts: { body: "Tajawal" } });
  });
});

describe("OwnerThemePicker", () => {
  it("starts on Classic with Save disabled, and saves nothing until Save", async () => {
    h.get.mockImplementation(routes);
    mount();
    await screen.findByTestId("owner-theme-picker");
    expect(screen.getByRole("button", { name: "تم الحفظ" })).toHaveProperty("disabled", true);
    fireEvent.click(screen.getByRole("button", { name: /كوبالت/ }));
    expect(h.put).not.toHaveBeenCalled();
    h.put.mockResolvedValue({ id: "cobalt" });
    fireEvent.click(screen.getByRole("button", { name: "حفظ المظهر" }));
    await waitFor(() => expect(h.put).toHaveBeenCalledWith("/themes/current", { id: "cobalt", palette: "", fonts: {} }));
  });
  it("back to Classic sends the Classic payload", async () => {
    h.get.mockImplementation(routes);
    h.put.mockResolvedValue({ id: "mizan" });
    mount();
    await screen.findByTestId("owner-theme-picker");
    fireEvent.click(screen.getByRole("button", { name: /كوبالت/ }));
    fireEvent.click(screen.getByRole("button", { name: /رجوع إلى الكلاسيكي/ }));
    await waitFor(() => expect(h.put).toHaveBeenCalledWith("/themes/current", savePayload(CLASSIC_DRAFT)));
  });
  it("opens Studio in a new tab", async () => {
    h.get.mockImplementation(routes);
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    mount();
    await screen.findByTestId("owner-theme-picker");
    fireEvent.click(screen.getByRole("button", { name: /تعديل أكثر في الاستوديو/ }));
    expect(open).toHaveBeenCalledWith(STUDIO_URL, "_blank", "noopener,noreferrer");
  });
});
