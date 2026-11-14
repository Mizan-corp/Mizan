import { TablePagination } from "@/components/app/shared";
import type { PagingControl } from "../ClinicContext";

// The pager under a server-paged clinic list (#39), with how many rows matched.
export default function ListPager({ paging, total, pages }: { paging: PagingControl; total: number; pages: number }) {
  return (
    <div className="px-4 py-3 border-t border-border/60 space-y-1">
      <p className="text-xs text-muted-foreground">
        إجمالي النتائج: <span className="num font-semibold text-foreground">{total}</span>
      </p>
      <TablePagination page={paging.page} pages={pages} onPage={paging.setPage}
        pageSize={paging.pageSize} onPageSize={paging.setPageSize} />
    </div>
  );
}
