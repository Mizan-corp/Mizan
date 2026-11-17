import { beforeEach, describe, expect, it, vi } from "vitest";

const shown: string[] = [];
vi.mock("sonner", () => ({ toast: { error: (m: string) => shown.push(m) } }));

import { ApiError, DocumentError } from "@/lib/api";
import { documentErrorMessage, installDocumentErrorHandler, showDocumentError } from "../documents";

type Handler = (e: { reason: unknown; preventDefault: () => void }) => void;

describe("print and export errors reach the user (REP-18)", () => {
  beforeEach(() => {
    shown.length = 0;
  });

  it("shows the server's Arabic message, or a general one", () => {
    expect(documentErrorMessage(new DocumentError(403, "ليس لديك صلاحية طباعة الفواتير"))).toBe("ليس لديك صلاحية طباعة الفواتير");
    expect(documentErrorMessage(new Error("boom"))).toBe("تعذر فتح المستند. حاول مرة أخرى.");
    showDocumentError(new ApiError(404, "الفرع غير موجود"));
    expect(shown).toEqual(["الفرع غير موجود"]);
  });

  it("an uncaught document error is shown; other rejections are left alone", () => {
    let handler: Handler | undefined;
    installDocumentErrorHandler({ addEventListener: (_: string, h: unknown) => { handler = h as Handler; } } as never);
    const prevented: unknown[] = [];
    handler!({ reason: new DocumentError(0, "تعذر الاتصال بالخادم"), preventDefault: () => prevented.push(1) });
    handler!({ reason: new ApiError(500, "not a document"), preventDefault: () => prevented.push(2) });
    expect(shown).toEqual(["تعذر الاتصال بالخادم"]);
    expect(prevented).toEqual([1]);
  });
});
