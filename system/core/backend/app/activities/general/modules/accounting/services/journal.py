"""Manual journal entries (ADR-014 D9) and reversing posted entries by hand (D1).

A holder of `accounting:journal` writes a **draft** (`acc_drafts` / `acc_draft_lines`), edits it as
often as needed, and **posts** it. Posting goes through `posting.post` (source `manual`, the draft's
id, event `post`), so it gets the same checks as every other entry: balanced, no group or stopped
account, not into a closed month. On top of those, a manual entry must keep the sub-ledgers matching
the ledger (D8, D9):

- receivables need a customer on the line, payables a supplier; a customer may only be named on
  receivables, a supplier on payables, an employee on employee advances or salaries payable;
- inventory can't be posted by hand (use a stock adjustment, which moves the quantities too);
- a cashier drawer's account can't either (its cash belongs to the open shift: use the drawer).

The operational balances follow the entry, in the same transaction, so the nightly reconciliation
keeps agreeing: a receivables line changes the customer's balance (with a `customer_adjustments` row),
a payables line the supplier's (with a `supplier_transactions` row), and a line on a safe's or a
wallet's account moves that safe or wallet (`finance.services.payments`, which refuses an overdraft).
Reversing a manual entry undoes them the same way.

Reversal (`reverse_entry`): manual entries (`accounting:journal`) and the opening entry
(`accounting:settings`, checked by the route) can be reversed here; a year-end closing only through
`/year-end/reverse`; a document's entry only by cancelling the document. Reversing twice returns the
first reversal and changes nothing more.
"""
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.models import Draft, DraftLine, Entry, Line
from app.activities.general.modules.accounting.services import posting
from app.activities.general.modules.accounting.services.chart import ensure_chart
from app.core.exceptions import BusinessError, NotFoundError

ZERO = Decimal("0")
CENT = Decimal("0.01")
SOURCE = "manual"
EVENT = "post"
MAX_LINES = 200
PARTY_TABLES = {"customer": "customers", "supplier": "suppliers", "employee": "hr_employees"}
PARTY_LABELS = {"customer": "العميل", "supplier": "المورد", "employee": "الموظف"}
# Which party a control account takes: required on receivables and payables, allowed on the
# employee accounts, refused on every other account.
PARTY_REQUIRED = {"receivables": "customer", "payables": "supplier"}
PARTY_ALLOWED = {"receivables": {"customer"}, "payables": {"supplier"},
                 "employee_advances": {"employee"}, "salaries_payable": {"employee"}}


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT)


def _money(v) -> float:
    return float(_q(v))


# ── checking lines ────────────────────────────────────────────────────────────────────────────

async def _accounts(db: AsyncSession, tenant_id: uuid.UUID, ids: set) -> dict:
    if not ids:
        return {}
    rows = (await db.execute(text("""
        SELECT a.id, a.code, a.name, a.is_group, a.active, a.role, m.kind AS money_kind, m.ref_id AS money_ref
        FROM acc_accounts a LEFT JOIN acc_money_accounts m ON m.account_id = a.id AND m.tenant_id = :t
        WHERE a.tenant_id = :t AND a.id = ANY(:ids)
    """), {"t": tenant_id, "ids": list(ids)})).mappings().all()
    return {r["id"]: dict(r) for r in rows}


async def _party_names(db: AsyncSession, lines: list[dict]) -> dict[tuple[str, uuid.UUID], str]:
    out = {}
    wanted: dict[str, set] = defaultdict(set)
    for ln in lines:
        if ln.get("party_type") in PARTY_TABLES and ln.get("party_id"):
            wanted[ln["party_type"]].add(ln["party_id"])
    for ptype, ids in wanted.items():
        rows = (await db.execute(text(f"SELECT id, name FROM {PARTY_TABLES[ptype]} WHERE id = ANY(:ids)"),  # noqa: S608 (fixed map)
                                 {"ids": list(ids)})).all()
        out.update({(ptype, r.id): r.name for r in rows})
    return out


async def problems(db: AsyncSession, tenant_id: uuid.UUID, on: date | None, lines: list[dict]) -> list[str]:
    """Why these lines can't be posted as a manual entry on `on` (empty: they can). Every rule of
    D9 and of the posting service, in Arabic, so a screen can list them before posting."""
    out: list[str] = []
    if on is not None:
        if on > posting.today():
            out.append("تاريخ القيد لا يمكن أن يكون في المستقبل")
        if await posting.period_closed(db, tenant_id, on):
            out.append(f"الفترة المحاسبية {on.strftime('%Y-%m')} مغلقة — اختر تاريخاً في فترة مفتوحة")
        opening_date = await db.scalar(text("""
            SELECT e.date FROM acc_entries e WHERE e.tenant_id = :t AND e.source_type = 'opening' AND e.event = 'opening'
              AND NOT EXISTS (SELECT 1 FROM acc_entries r WHERE r.reverses_id = e.id) ORDER BY e.date LIMIT 1
        """), {"t": tenant_id})
        if opening_date and on < opening_date:
            out.append(f"لا يمكن تسجيل قيد قبل تاريخ القيد الافتتاحي ({opening_date.isoformat()})")
    lines = [ln for ln in lines if _q(ln.get("debit")) or _q(ln.get("credit"))]
    if len(lines) < 2:
        out.append("القيد يحتاج سطرين على الأقل: مدين ودائن")
    debit = sum((_q(ln.get("debit")) for ln in lines), ZERO)
    credit = sum((_q(ln.get("credit")) for ln in lines), ZERO)
    if debit != credit:
        out.append(f"القيد غير متوازن: المدين {debit} والدائن {credit} (الفرق {abs(debit - credit)})")
    accounts = await _accounts(db, tenant_id, {ln["account_id"] for ln in lines})
    names = await _party_names(db, lines)
    for i, ln in enumerate(lines, 1):
        where = f"السطر {i}"
        if _q(ln.get("debit")) and _q(ln.get("credit")):
            out.append(f"{where}: السطر إما مدين أو دائن، لا الاثنان معاً")
        acc = accounts.get(ln["account_id"])
        if acc is None:
            out.append(f"{where}: الحساب غير موجود في دليل الحسابات")
            continue
        label = f"{where} ({acc['code']} {acc['name']})"
        if acc["is_group"]:
            out.append(f"{label}: لا يمكن الترحيل على حساب تجميعي، اختر حساباً فرعياً")
        if not acc["active"]:
            out.append(f"{label}: الحساب موقوف")
        if acc["role"] == "inventory":
            out.append(f"{label}: لا يُرحَّل على المخزون يدوياً — استخدم تسوية المخزون حتى تتحرك الكميات مع القيمة")
        if acc["money_kind"] == "drawer":
            out.append(f"{label}: درج الكاشير يتحرك من الوردية فقط (إيداع أو سحب من الدرج)")
        ptype, pid = ln.get("party_type"), ln.get("party_id")
        required = PARTY_REQUIRED.get(acc["role"] or "")
        allowed = PARTY_ALLOWED.get(acc["role"] or "", set())
        if required and not (ptype == required and pid):
            out.append(f"{label}: حدد {PARTY_LABELS[required]} على هذا السطر حتى يبقى رصيده مطابقاً للدفاتر")
        elif ptype and ptype not in allowed:
            out.append(f"{label}: لا يُذكر {PARTY_LABELS.get(ptype, 'طرف')} على هذا الحساب")
        if ptype and pid and (ptype, pid) not in names:
            out.append(f"{where}: {PARTY_LABELS.get(ptype, 'الطرف')} غير موجود")
        if ptype and not pid:
            out.append(f"{where}: اختر {PARTY_LABELS.get(ptype, 'الطرف')}")
    return out


# ── drafts ────────────────────────────────────────────────────────────────────────────────────

def _clean_lines(lines: list) -> list[dict]:
    out = []
    for ln in lines:
        row = ln if isinstance(ln, dict) else ln.model_dump()
        debit, credit = _q(row.get("debit")), _q(row.get("credit"))
        if debit < 0 or credit < 0:
            raise BusinessError("المبالغ لا تكون سالبة")
        if not debit and not credit:
            continue  # an empty line of the form
        if debit and credit:
            raise BusinessError("كل سطر إما مدين أو دائن، لا الاثنان معاً")
        party_type = row.get("party_type") or None
        out.append({"account_id": row["account_id"], "debit": debit, "credit": credit, "party_type": party_type,
                    "party_id": row.get("party_id") if party_type else None, "warehouse_id": row.get("warehouse_id")})
    if len(out) > MAX_LINES:
        raise BusinessError(f"القيد لا يزيد عن {MAX_LINES} سطراً")
    return out


async def _check_refs(db: AsyncSession, tenant_id: uuid.UUID, lines: list[dict], warehouse_id) -> None:
    """The accounts, parties and branches named exist in this workspace (structure only; the posting
    rules are listed by `problems` and enforced at posting)."""
    accounts = await _accounts(db, tenant_id, {ln["account_id"] for ln in lines})
    if len(accounts) != len({ln["account_id"] for ln in lines}):
        raise BusinessError("حساب غير موجود في دليل الحسابات")
    names = await _party_names(db, lines)
    for ln in lines:
        if ln["party_type"] and ln["party_id"] and (ln["party_type"], ln["party_id"]) not in names:
            raise BusinessError(f"{PARTY_LABELS[ln['party_type']]} غير موجود")
    branches = {ln["warehouse_id"] for ln in lines if ln["warehouse_id"]} | ({warehouse_id} if warehouse_id else set())
    if branches:
        found = await db.scalar(text("SELECT COUNT(*) FROM warehouses WHERE id = ANY(:ids)"), {"ids": list(branches)})
        if found != len(branches):
            raise BusinessError("الفرع غير موجود")


async def _draft(db: AsyncSession, tenant_id: uuid.UUID, draft_id: uuid.UUID, lock: bool = False) -> Draft:
    q = select(Draft).where(Draft.tenant_id == tenant_id, Draft.id == draft_id)
    draft = (await db.execute(q.with_for_update() if lock else q)).scalar_one_or_none()
    if draft is None:
        raise NotFoundError("القيد غير موجود")
    return draft


async def _draft_lines(db: AsyncSession, draft_id: uuid.UUID) -> list[DraftLine]:
    return list((await db.execute(select(DraftLine).where(DraftLine.draft_id == draft_id)
                                  .order_by(DraftLine.position))).scalars().all())


def _line_dict(ln: DraftLine) -> dict:
    return {"account_id": ln.account_id, "debit": ln.debit, "credit": ln.credit, "party_type": ln.party_type,
            "party_id": ln.party_id, "warehouse_id": ln.warehouse_id}


async def view(db: AsyncSession, tenant_id: uuid.UUID, draft: Draft) -> dict:
    rows = await _draft_lines(db, draft.id)
    lines = [_line_dict(r) for r in rows]
    accounts = await _accounts(db, tenant_id, {ln["account_id"] for ln in lines})
    names = await _party_names(db, lines)
    debit = sum((ln["debit"] for ln in lines), ZERO)
    credit = sum((ln["credit"] for ln in lines), ZERO)
    entry = None
    if draft.entry_id:
        e = await db.get(Entry, draft.entry_id)
        entry = {"id": e.id, "number": e.number, "date": e.date} if e else None
    return {
        "id": draft.id, "date": draft.date, "memo": draft.memo, "warehouse_id": draft.warehouse_id, "status": draft.status,
        "entry": entry, "created_by": draft.created_by, "created_at": draft.created_at, "updated_at": draft.updated_at,
        "posted_at": draft.posted_at,
        "lines": [{**ln, "debit": _money(ln["debit"]), "credit": _money(ln["credit"]),
                   "account_code": (accounts.get(ln["account_id"]) or {}).get("code"),
                   "account_name": (accounts.get(ln["account_id"]) or {}).get("name"),
                   "account_role": (accounts.get(ln["account_id"]) or {}).get("role"),
                   "party_name": names.get((ln["party_type"], ln["party_id"]))} for ln in lines],
        "total_debit": _money(debit), "total_credit": _money(credit), "difference": _money(debit - credit),
        "balanced": debit == credit and debit > 0,
        "problems": [] if draft.status != "draft" else await problems(db, tenant_id, draft.date, lines),
    }


async def save(db: AsyncSession, tenant_id: uuid.UUID, data, user_id: uuid.UUID | None,
               draft_id: uuid.UUID | None = None) -> Draft:
    """Create a draft, or replace a draft's date, memo, branch and lines. A posted entry is never
    edited (reverse it instead). Runs in the caller's transaction."""
    await ensure_chart(db, tenant_id)
    lines = _clean_lines(data.lines)
    await _check_refs(db, tenant_id, lines, data.warehouse_id)
    if draft_id is None:
        draft = Draft(id=uuid.uuid4(), tenant_id=tenant_id, date=data.date, memo=data.memo, warehouse_id=data.warehouse_id,
                      status="draft", created_by=user_id, updated_by=user_id)
        db.add(draft)
        await db.flush()
    else:
        draft = await _draft(db, tenant_id, draft_id, lock=True)
        if draft.status != "draft":
            raise BusinessError("القيد مُرحَّل ولا يُعدَّل. صحّحه بقيد عكسي")
        draft.date, draft.memo, draft.warehouse_id, draft.updated_by = data.date, data.memo, data.warehouse_id, user_id
        await db.execute(delete(DraftLine).where(DraftLine.draft_id == draft.id))
    for i, ln in enumerate(lines):
        db.add(DraftLine(id=uuid.uuid4(), tenant_id=tenant_id, draft_id=draft.id, position=i, **ln))
    await db.flush()
    return draft


async def remove(db: AsyncSession, tenant_id: uuid.UUID, draft_id: uuid.UUID) -> None:
    draft = await _draft(db, tenant_id, draft_id, lock=True)
    if draft.status != "draft":
        raise BusinessError("القيد مُرحَّل ولا يُحذف. صحّحه بقيد عكسي")
    await db.delete(draft)
    await db.flush()


async def list_drafts(db: AsyncSession, tenant_id: uuid.UUID, status: str = "draft", page: int = 1,
                      page_size: int = 50) -> dict:
    params = {"t": tenant_id, "st": status, "lim": page_size, "off": (page - 1) * page_size}
    total = await db.scalar(text("SELECT COUNT(*) FROM acc_drafts WHERE tenant_id = :t AND status = :st"), params)
    rows = (await db.execute(text("""
        SELECT d.id, d.date, d.memo, d.warehouse_id, d.status, d.entry_id, d.created_by, d.created_at, d.updated_at,
               u.full_name AS created_by_name, e.number AS entry_number,
               COALESCE((SELECT SUM(debit) FROM acc_draft_lines l WHERE l.draft_id = d.id), 0) AS debit,
               COALESCE((SELECT SUM(credit) FROM acc_draft_lines l WHERE l.draft_id = d.id), 0) AS credit,
               (SELECT COUNT(*) FROM acc_draft_lines l WHERE l.draft_id = d.id) AS line_count
        FROM acc_drafts d LEFT JOIN users u ON u.id = d.created_by LEFT JOIN acc_entries e ON e.id = d.entry_id
        WHERE d.tenant_id = :t AND d.status = :st
        ORDER BY d.updated_at DESC, d.id LIMIT :lim OFFSET :off
    """), params)).mappings().all()
    items = [{**dict(r), "debit": _money(r["debit"]), "credit": _money(r["credit"]),
              "balanced": _q(r["debit"]) == _q(r["credit"]) and _q(r["debit"]) > 0} for r in rows]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


# ── posting and reversing ─────────────────────────────────────────────────────────────────────

async def _sync_operational(db: AsyncSession, tenant_id: uuid.UUID, entry: Entry, user_id) -> None:
    """Bring the operational balances along with a manual entry (or its reversal): customers on
    receivables, suppliers on payables, safes and wallets on their own accounts."""
    from app.activities.general.modules.finance.services import payments

    rows = (await db.execute(select(Line).where(Line.entry_id == entry.id))).scalars().all()
    accounts = await _accounts(db, tenant_id, {r.account_id for r in rows})
    customers: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    suppliers: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    money: list[tuple[str, uuid.UUID, Decimal]] = []
    for r in rows:
        acc = accounts[r.account_id]
        net = Decimal(r.debit) - Decimal(r.credit)
        if acc["role"] == "receivables" and r.party_type == "customer" and r.party_id:
            customers[r.party_id] += net
        elif acc["role"] == "payables" and r.party_type == "supplier" and r.party_id:
            suppliers[r.party_id] -= net  # a supplier's balance is what we owe: credit minus debit
        elif acc["money_kind"] in ("safe", "wallet"):
            money.append((acc["money_kind"], acc["money_ref"], net))
    note = f"قيد يومية {entry.number}" + (f" — {entry.memo}" if entry.memo else "")
    for cid, delta in customers.items():
        if not delta:
            continue
        before = Decimal(await db.scalar(text("SELECT COALESCE(balance, 0) FROM customers WHERE id = :id FOR UPDATE"),
                                         {"id": cid}) or 0)
        await db.execute(text("""
            INSERT INTO customer_adjustments (id, tenant_id, customer_id, kind, amount, balance_before, balance_after, note, created_by)
            VALUES (:id, :t, :c, 'adjustment', :amt, :before, :after, :note, :uid)
        """), {"id": uuid.uuid4(), "t": tenant_id, "c": cid, "amt": delta, "before": before, "after": before + delta,
               "note": note, "uid": user_id})
        await db.execute(text("UPDATE customers SET balance = COALESCE(balance, 0) + :d WHERE id = :id"), {"d": delta, "id": cid})
    for sid, delta in suppliers.items():
        if not delta:
            continue
        await db.execute(text("SELECT 1 FROM suppliers WHERE id = :id FOR UPDATE"), {"id": sid})
        await db.execute(text("""
            INSERT INTO supplier_transactions (id, tenant_id, supplier_id, amount, type, reference_doc, notes, created_by)
            VALUES (:id, :t, :s, :amt, :type, :ref, :note, :uid)
        """), {"id": uuid.uuid4(), "t": tenant_id, "s": sid, "amt": abs(delta), "type": "debit" if delta > 0 else "credit",
               "ref": entry.number, "note": note, "uid": user_id})
        await db.execute(text("UPDATE suppliers SET balance = COALESCE(balance, 0) + :d WHERE id = :id"), {"d": delta, "id": sid})
    # Money in first, so a transfer between two safes in one entry checks the giving safe's balance.
    for kind, ref, net in sorted(money, key=lambda m: m[2] < 0):
        ids = {"safe_id": ref, "wallet_id": None} if kind == "safe" else {"safe_id": None, "wallet_id": ref}
        if net > 0:
            await payments.money_in(db, net, **ids, ref_type="acc_entry", ref_id=entry.id, note=note, user_id=user_id)
        elif net < 0:
            await payments.money_out(db, -net, **ids, ref_type="acc_entry", ref_id=entry.id, note=note, user_id=user_id)


async def post_draft(db: AsyncSession, tenant_id: uuid.UUID, draft_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
    """Post a draft as a journal entry. Posting an already posted draft returns its entry."""
    draft = await _draft(db, tenant_id, draft_id, lock=True)
    if draft.status == "posted":
        entry = await db.get(Entry, draft.entry_id)
        return {"draft_id": draft.id, "entry": {"id": entry.id, "number": entry.number, "date": entry.date}, "already": True}
    lines = [_line_dict(r) for r in await _draft_lines(db, draft.id)]
    why = await problems(db, tenant_id, draft.date, lines)
    if why:
        raise BusinessError(why[0] if len(why) == 1 else "لا يمكن ترحيل القيد: " + "؛ ".join(why[:4]))
    entry = await posting.post(
        db, tenant_id, SOURCE, draft.id, EVENT, draft.date,
        [posting.PostLine(ln["account_id"], debit=_q(ln["debit"]), credit=_q(ln["credit"]), party_type=ln["party_type"],
                          party_id=ln["party_id"], warehouse_id=ln["warehouse_id"]) for ln in lines],
        memo=draft.memo or "قيد يومية يدوي", warehouse_id=draft.warehouse_id, user_id=user_id)
    await _sync_operational(db, tenant_id, entry, user_id)
    draft.status, draft.entry_id, draft.posted_by, draft.posted_at = "posted", entry.id, user_id, datetime.now(UTC)
    await db.flush()
    return {"draft_id": draft.id, "entry": {"id": entry.id, "number": entry.number, "date": entry.date}, "already": False}


async def entry_or_404(db: AsyncSession, tenant_id: uuid.UUID, entry_id: uuid.UUID) -> Entry:
    entry = (await db.execute(select(Entry).where(Entry.tenant_id == tenant_id, Entry.id == entry_id))).scalar_one_or_none()
    if entry is None:
        raise NotFoundError("القيد غير موجود")
    return entry


def reversal_kind(entry: Entry) -> str:
    """Who may reverse this entry by hand: 'journal' (a manual entry), 'opening' (the opening entry,
    accounting:settings); anything else raises with the way to undo it."""
    if entry.event == "reverse" or entry.reverses_id is not None:
        raise BusinessError("هذا قيد عكسي ولا يُعكس. سجّل قيداً يدوياً جديداً إن لزم")
    if entry.source_type == SOURCE:
        return "journal"
    if entry.source_type == "opening":
        return "opening"
    if entry.source_type == "year_end":
        raise BusinessError("قيد إقفال السنة يُعكس من شاشة إقفال الفترات (عكس إقفال السنة)")
    raise BusinessError("هذا قيد مستند تلقائي: يُعكس بإلغاء المستند نفسه (الفاتورة، المصروف، الحركة…) حتى يبقى المستند والقيد متطابقين")


async def reverse_entry(db: AsyncSession, tenant_id: uuid.UUID, entry: Entry, on: date | None, memo: str | None,
                        user_id: uuid.UUID | None) -> dict:
    """Reverse a manual or opening entry, dated `on` (a manual entry: today by default; the opening
    entry: its own date by default, so the ledger has no opening at all until a new one is posted).
    Idempotent: a second call returns the first reversal."""
    kind = reversal_kind(entry)
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"acc_reverse:{entry.id}"})
    existing = (await db.execute(select(Entry).where(Entry.tenant_id == tenant_id, Entry.reverses_id == entry.id))).scalars().first()
    if existing is not None:
        return {"reversed": entry.number, "entry": {"id": existing.id, "number": existing.number, "date": existing.date},
                "already": True}
    on = on or (entry.date if kind == "opening" else posting.today())
    if on > posting.today():
        raise BusinessError("تاريخ القيد العكسي لا يمكن أن يكون في المستقبل")
    if on < entry.date:
        raise BusinessError(f"تاريخ القيد العكسي لا يسبق تاريخ القيد الأصلي ({entry.date.isoformat()})")
    reason = (memo or "").strip()
    rev = await posting.reverse(db, entry, on=on, user_id=user_id,
                                memo=f"عكس القيد {entry.number} — {reason}" if reason else None)
    if kind == "journal":
        await _sync_operational(db, tenant_id, rev, user_id)
    return {"reversed": entry.number, "entry": {"id": rev.id, "number": rev.number, "date": rev.date}, "already": False}
