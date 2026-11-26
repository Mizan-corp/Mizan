// Printing and downloading a document, with its errors shown to the user (REP-18): openPrintDoc
// and downloadExport throw an ApiError with the server's Arabic message; these show it as a toast.
import { toast } from "sonner";
import { ApiError, DocumentError, downloadExport, openPrintDoc } from "@/lib/api";

type Params = Record<string, string | number | undefined>;

export function documentErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.message) return err.message;
  return "تعذر فتح المستند. حاول مرة أخرى.";
}

export function showDocumentError(err: unknown): void {
  toast.error(documentErrorMessage(err));
}

/** Open a print page or PDF in a new tab; a failure is a toast, never an unhandled rejection. */
export function printDocument(path: string, params?: Params): Promise<void> {
  return openPrintDoc(path, params).catch(showDocumentError);
}

/** Download a file (an export, a PDF); a failure is a toast. */
export function downloadFile(path: string, params?: Params, filename?: string): Promise<void> {
  return downloadExport(path, params, filename).catch(showDocumentError);
}

/** Calls that weren't given a handler (a print button calling openPrintDoc directly): their
 * DocumentError still reaches the user, once, instead of the console only. Other rejections are
 * left alone. */
export function installDocumentErrorHandler(target: Pick<Window, "addEventListener"> = window): void {
  target.addEventListener("unhandledrejection", (event: PromiseRejectionEvent) => {
    if (event.reason instanceof DocumentError) {
      event.preventDefault();
      showDocumentError(event.reason);
    }
  });
}
