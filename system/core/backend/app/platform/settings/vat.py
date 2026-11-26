"""VAT on documents (ADR-014 D6): the workspace's VAT settings, the tax codes and their rates, and
the one way a line's tax is worked out. Every document (sale, return, purchase, purchase return,
expense) stores what this computes at the time of the document; nothing recomputes it later.

Settings (store_settings, the workspace's company settings): `vat_registered` (off by default),
`tax_number` (the Egyptian tax registration number, 9 digits) and `prices_include_vat` (on by
default: Egyptian shops price with VAT included).

Rounding: each line is rounded to the piastre, half up. With prices including VAT the line's net is
round(amount / (1 + rate)) and its tax is amount - net, so net + tax is always exactly what the
customer pays; with prices excluding VAT the tax is round(amount x rate) on top. A document's totals
are the sums of its lines. Discounts come first: the tax is on the amount after the line's own
discount and its share of the invoice discount (shared pro rata to the lines' amounts, rounded, the
remainder on the largest line).
"""
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
ZERO = Decimal("0")

# The one place the rates live (percent). Zero-rated goods are taxed at 0 % and still reported;
# exempt goods are outside VAT.
TAX_RATES: dict[str, Decimal] = {"standard": Decimal("14"), "zero": Decimal("0"), "exempt": Decimal("0")}
TAX_LABELS: dict[str, str] = {"standard": "خاضع للضريبة (14%)", "zero": "خاضع بنسبة صفر", "exempt": "معفى من الضريبة"}
DEFAULT_TAX_CODE = "standard"

_TAX_NUMBER = re.compile(r"^\d{9}$")


def money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT, ROUND_HALF_UP)


def tax_rate(code: str | None) -> Decimal:
    return TAX_RATES.get(code or "", ZERO)


def clean_tax_number(value) -> str:
    """The tax registration number as 9 digits (spaces and dashes dropped); '' when empty.
    Raises ValueError (Arabic) when it isn't 9 digits."""
    raw = re.sub(r"[\s\-–]", "", str(value or ""))
    raw = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if not raw:
        return ""
    if not _TAX_NUMBER.match(raw):
        raise ValueError("رقم التسجيل الضريبي يتكون من 9 أرقام (يمكن كتابته مثل 123-456-789)")
    return raw


def format_tax_number(value: str | None) -> str:
    v = str(value or "")
    return f"{v[:3]}-{v[3:6]}-{v[6:]}" if len(v) == 9 and v.isdigit() else v


def _bool(value, default: bool) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class VatSettings:
    registered: bool = False
    prices_include_vat: bool = True
    tax_number: str = ""


async def vat_settings(db: AsyncSession) -> VatSettings:
    rows = dict((await db.execute(text(
        "SELECT key, value FROM store_settings WHERE key IN ('vat_registered', 'prices_include_vat', 'tax_number')"
    ))).all())
    return VatSettings(registered=_bool(rows.get("vat_registered"), False),
                       prices_include_vat=_bool(rows.get("prices_include_vat"), True),
                       tax_number=str(rows.get("tax_number") or ""))


@dataclass(frozen=True)
class LineTax:
    tax_code: str | None  # None: no VAT on the document (the workspace isn't registered)
    tax_rate: Decimal
    net: Decimal          # the taxable value, after discounts, VAT excluded
    tax: Decimal

    @property
    def gross(self) -> Decimal:
        return self.net + self.tax


def line_tax(amount, code: str | None, registered: bool, inclusive: bool) -> LineTax:
    """The VAT of one line whose amount (after discounts, in the document's price terms) is `amount`."""
    amount = money(amount)
    if not registered:
        return LineTax(None, ZERO, amount, ZERO)
    code = code if code in TAX_RATES else DEFAULT_TAX_CODE
    rate = TAX_RATES[code]
    if not rate:
        return LineTax(code, rate, amount, ZERO)
    r = rate / 100
    if inclusive:
        net = (amount / (1 + r)).quantize(CENT, ROUND_HALF_UP)
        return LineTax(code, rate, net, amount - net)
    return LineTax(code, rate, amount, (amount * r).quantize(CENT, ROUND_HALF_UP))


def allocate(amounts: list[Decimal], total) -> list[Decimal]:
    """`total` (an invoice discount) shared over lines pro rata to their amounts, each share rounded
    to the piastre, the remainder on the largest line, so the shares add up to `total` exactly."""
    total = money(total)
    if not amounts:
        return []
    base = sum(amounts, ZERO)
    if not total:
        return [ZERO] * len(amounts)
    if base <= 0:
        shares = [ZERO] * len(amounts)
        shares[0] = total
        return shares
    shares = [(total * a / base).quantize(CENT, ROUND_HALF_UP) for a in amounts]
    largest = max(range(len(amounts)), key=lambda i: amounts[i])
    shares[largest] += total - sum(shares, ZERO)
    return shares


def document_taxes(lines: list[tuple[Decimal, str | None]], invoice_discount, settings: VatSettings,
                   inclusive: bool | None = None) -> list[LineTax]:
    """Each line's VAT for a document. `lines`: (amount after the line's own discount, tax code).
    The lines' amounts after discounts add up to the document's own rounded total (a weighed
    quantity can give a line a fraction of a piastre: the rounding difference goes on the largest
    line), so with prices including VAT the document's total is exactly what it was before VAT."""
    raw = [Decimal(str(a or 0)) for a, _ in lines]
    amounts = [money(a) for a in raw]
    shares = allocate(amounts, invoice_discount)
    bases = [a - s for a, s in zip(amounts, shares, strict=True)]
    if bases:
        diff = money(sum(raw, ZERO) - money(invoice_discount)) - sum(bases, ZERO)
        if diff:
            largest = max(range(len(bases)), key=lambda i: amounts[i])
            bases[largest] += diff
    inc = settings.prices_include_vat if inclusive is None else inclusive
    return [line_tax(b, code, settings.registered, inc) for b, (_, code) in zip(bases, lines, strict=True)]


def portion(total, before, now, of) -> Decimal:
    """The part of a line's `total` (its tax, or its value) that `now` units carry when `before`
    units were already taken out of `of`: cumulative and rounded, so taking every unit out, in any
    number of returns, adds up to `total` exactly."""
    total, before, now, of = money(total), Decimal(str(before)), Decimal(str(now)), Decimal(str(of))
    if of <= 0:
        return ZERO
    done = (total * before / of).quantize(CENT, ROUND_HALF_UP)
    if before + now >= of:
        return total - done
    return (total * (before + now) / of).quantize(CENT, ROUND_HALF_UP) - done


async def product_tax_codes(db: AsyncSession, product_ids) -> dict:
    ids = list({p for p in product_ids})
    if not ids:
        return {}
    rows = (await db.execute(text("SELECT id, tax_code FROM products WHERE id = ANY(:ids)"), {"ids": ids})).all()
    return {r.id: (r.tax_code or DEFAULT_TAX_CODE) for r in rows}
