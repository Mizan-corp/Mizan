"""Dispatch orders (إذن صرف, operations) and drawer hand-overs (تسليم عهدة, pos), printed from what
they left behind: the archived document and, for a dispatch, its stock movements (the quantities
that really moved). The tables these routes once read (`dispatch_movements`, `dispatch_items`) never
existed in the schema, so both answered 500."""
from typing import Annotated

from fastapi import Depends, HTTPException, Path
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_print_user
from app.platform.permissions.access import can

from . import (_make_pdf, PaperSize, ar_egp, ar_num, fmt_date, fmt_dt, get_settings, guard, h, not_found, router, store_of,
               top_band, wrap)

# Dispatch orders: operations (or inventory), in a branch the goods left or reached.
PERMS = ("operations", "inventory")
DENIED = "ليس لديك صلاحية طباعة أوامر الصرف"
DocNumber = Annotated[str, Path(min_length=1, max_length=64)]


async def _archived(db: AsyncSession, doc_type: str, doc_number: str) -> dict | None:
    row = (await db.execute(text("""
        SELECT ad.*, u.full_name AS created_by_name FROM archived_documents ad
        LEFT JOIN users u ON u.id = ad.created_by
        WHERE ad.doc_type = :t AND ad.doc_number = :n ORDER BY ad.created_at DESC LIMIT 1
    """), {"t": doc_type, "n": doc_number})).mappings().first()
    if row is None:
        return None
    doc = dict(row)
    meta = doc.get("metadata")
    if isinstance(meta, str):
        import json

        try:
            meta = json.loads(meta)
        except ValueError:
            meta = None
    doc["meta"] = meta if isinstance(meta, dict) else {}
    return doc


def _signatures(*labels: tuple[str, str]) -> str:
    return '<div class="signatures">' + "".join(
        f'<div class="signature-item"><div class="label">{h(label)}</div><div class="signature-line"></div>'
        f'<div class="name">{h(name)}</div></div>' for label, name in labels) + "</div>"


@router.get("/dispatch/{doc_number}", response_class=HTMLResponse)
async def print_dispatch(doc_number: DocNumber,
                         db: AsyncSession = Depends(get_db), user=Depends(get_print_user)):
    store = store_of(await get_settings(db))
    doc = await _archived(db, "dispatch_order", doc_number)
    if doc is None:
        raise not_found("أمر الصرف")
    moves = (await db.execute(text("""
        SELECT CAST(sm.movement_type AS text) AS kind, sm.warehouse_id, w.name AS warehouse, p.name AS product_name,
               p.unit, SUM(sm.qty) AS qty
        FROM stock_movements sm
        JOIN products p ON p.id = sm.product_id
        LEFT JOIN warehouses w ON w.id = sm.warehouse_id
        WHERE sm.ref_id = :ref AND sm.ref_type = 'dispatch'
        GROUP BY 1, 2, 3, 4, 5 ORDER BY p.name
    """), {"ref": doc["ref_id"]})).mappings().all() if doc.get("ref_id") else []
    out = [m for m in moves if m["kind"] == "transfer_out"]
    into = next((m for m in moves if m["kind"] == "transfer_in"), None)
    await guard(db, user, PERMS, [m["warehouse_id"] for m in moves], DENIED)

    meta = doc["meta"]
    from_name = out[0]["warehouse"] if out else meta.get("from")
    to_name = into["warehouse"] if into else meta.get("to")
    rows_html = "".join(f"""<tr>
          <td style="color:#9ca3af;font-size:9px;text-align:center">{idx}</td>
          <td><div class="td-name">{h(m['product_name'])}</div></td>
          <td style="text-align:center;white-space:nowrap">{ar_num(float(m['qty']), 0)}</td>
          <td style="text-align:center;white-space:nowrap">{h(m['unit'])}</td>
        </tr>""" for idx, m in enumerate(out, 1))

    body = f"""
{top_band(store, 'أمر صرف', doc['doc_number'], fmt_date(doc['created_at']))}
<div class="body">
  <div class="parties">
    <div class="party-card buyer">
      <div class="party-label">صادر من</div>
      <div class="party-name">{h(from_name or '—')}</div>
    </div>
    <div class="party-card">
      <div class="party-label">وارد إلى</div>
      <div class="party-name">{h(to_name or '—')}</div>
    </div>
  </div>
  {f'<div class="note-section">{h(meta["notes"])}</div>' if meta.get('notes') else ''}
  <div class="tbl-label">الأصناف</div>
  <table>
    <thead><tr><th style="text-align:center">#</th><th style="width:100%">اسم الصنف</th><th style="text-align:center">الكمية</th><th style="text-align:center">الوحدة</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div style="margin-top:6px;font-size:11px;font-weight:700;text-align:left">إجمالي الأصناف: {ar_num(len(out), 0)}</div>
  {_signatures(("أمين المخازن", doc.get("created_by_name") or ""), ("المستلم", ""), ("مدير الفرع", ""))}
</div>"""
    return HTMLResponse(wrap(body, f"أمر صرف — {doc['doc_number']}"))


@router.get("/handover/{doc_number}", response_class=HTMLResponse)
async def print_handover(doc_number: DocNumber,
                         db: AsyncSession = Depends(get_db), user=Depends(get_print_user)):
    """A drawer hand-over between two cashiers (pos transfer_drawer): one of the two, or a manager or a
    holder of `supervise`, in the shift's branch."""
    store = store_of(await get_settings(db))
    doc = await _archived(db, "shift_handover", doc_number)
    if doc is None:
        raise not_found("مستند التسليم")
    meta = doc["meta"]
    shift = (await db.execute(text("""
        SELECT sh.warehouse_id, w.name AS warehouse FROM shifts sh LEFT JOIN warehouses w ON w.id = sh.warehouse_id
        WHERE sh.id = :id
    """), {"id": doc["ref_id"]})).mappings().first() if doc.get("ref_id") else None
    party = str(user.id) in (str(meta.get("from_user") or ""), str(meta.get("to_user") or ""))
    if not (party or user.is_manager or can(user, "supervise")):
        raise HTTPException(status_code=403, detail="لا يمكنك طباعة تسليم عهدة لست طرفًا فيه")
    await guard(db, user, ("shifts", "pos", "supervise"), [shift["warehouse_id"]] if shift else [])

    from_name, to_name = meta.get("from_user_name") or "—", meta.get("to_user_name") or "—"
    body = f"""
{top_band(store, 'تسليم عهدة', doc['doc_number'], fmt_date(doc['created_at']))}
<div class="body">
  <div class="parties">
    <div class="party-card buyer">
      <div class="party-label">المسَلِّم</div>
      <div class="party-name">{h(from_name)}</div>
    </div>
    <div class="party-card">
      <div class="party-label">المسَلَّم إليه</div>
      <div class="party-name">{h(to_name)}</div>
    </div>
  </div>
  <div class="meta-row">
    <div class="meta-cell"><div class="m-lbl">الفرع</div><div class="m-val">{h((shift or {}).get('warehouse') or '—')}</div></div>
    <div class="meta-cell"><div class="m-lbl">التاريخ</div><div class="m-val">{fmt_dt(doc['created_at'])}</div></div>
    <div class="meta-cell"><div class="m-lbl">مبلغ العهدة</div><div class="m-val">{ar_egp(float(doc.get('amount') or 0))}</div></div>
  </div>
  {f'<div class="note-section">{h(meta["notes"])}</div>' if meta.get('notes') else ''}
  {_signatures(("المسَلِّم", from_name), ("المسَلَّم إليه", to_name), ("مدير الفرع", ""))}
</div>"""
    return HTMLResponse(wrap(body, f"تسليم عهدة — {doc['doc_number']}"))


@router.get("/pdf/dispatch/{doc_number}")
async def pdf_dispatch(doc_number: DocNumber, paper_size: PaperSize = None,
                       db: AsyncSession = Depends(get_db), user=Depends(get_print_user)):
    html_resp = await print_dispatch(doc_number, db, user)
    return await _make_pdf(html_resp, "أمر صرف", f"dispatch_{doc_number}.pdf", db, paper_size)


@router.get("/pdf/handover/{doc_number}")
async def pdf_handover(doc_number: DocNumber, paper_size: PaperSize = None,
                       db: AsyncSession = Depends(get_db), user=Depends(get_print_user)):
    html_resp = await print_handover(doc_number, db, user)
    return await _make_pdf(html_resp, "تسليم عهدة", f"handover_{doc_number}.pdf", db, paper_size)
