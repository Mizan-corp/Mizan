import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { ErrorBox } from "@/components/ui";
import { errorMessage } from "../useClinicActions";

interface QueryLike {
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => unknown;
  fetchStatus?: string;
}

/** A clinic list's loading and error states (#48): the server's message and a retry, never a silent
 *  empty list. With no error and no loading, renders the list. */
export default function QueryState({
  query,
  what,
  children,
  className = "p-4",
}: {
  query: QueryLike;
  what: string;
  children: ReactNode;
  className?: string;
}) {
  if (query.isError) {
    return (
      <div className={className}>
        <ErrorBox
          message={`تعذر تحميل ${what}: ${errorMessage(query.error, "خطأ في الاتصال بالخادم")}`}
          onRetry={() => void query.refetch()}
        />
      </div>
    );
  }
  if (query.isLoading) {
    return (
      <div className={`${className} flex items-center justify-center gap-2 py-10 text-xs text-muted-foreground`} role="status" aria-busy="true">
        <RefreshCw className="size-4 animate-spin" />
        جارٍ تحميل {what}...
      </div>
    );
  }
  return <>{children}</>;
}

/** A small inline error with a retry, for a list inside a table or a dialog. */
export function InlineRetry({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <span role="alert" className="inline-flex flex-wrap items-center gap-2 text-xs text-destructive-ink">
      {message}
      <button type="button" onClick={onRetry} className="underline font-semibold hover:no-underline cursor-pointer">
        إعادة المحاولة
      </button>
    </span>
  );
}
