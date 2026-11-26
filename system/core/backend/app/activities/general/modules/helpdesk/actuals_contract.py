"""Non-posting execution actuals contract. No stock, payroll, invoice or journal calls.

Measured actuals survive without an assumed rate. Cost and selling-rate snapshots
are distinct, currency-separated estimates, never a posted valuation or charge.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator

SUPPORTED = {'EGP','USD','EUR','GBP','SAR','AED','QAR'}

class RateSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    amount: Decimal = Field(ge=0,max_digits=18,decimal_places=4,allow_inf_nan=False)
    currency: str
    basis: Literal['per_hour','per_unit']
    provenance: str = Field(min_length=1,max_length=500)
    @model_validator(mode='after')
    def valid_currency(self):
        if self.currency not in SUPPORTED:raise ValueError('Unsupported snapshot currency')
        return self

class ActualLine(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    line_id: UUID
    performed_on: date
    kind: Literal['labor','material','task']
    description: str = Field(min_length=1,max_length=2000)
    technician_id: UUID | None = None
    product_id: UUID | None = None
    warehouse_id: UUID | None = None
    quantity: Decimal = Field(gt=0,max_digits=15,decimal_places=3,allow_inf_nan=False)
    unit: str = Field(min_length=1,max_length=32)
    material_use: Literal['installed','consumed','returned'] | None = None
    cost: RateSnapshot | None = None
    selling: RateSnapshot | None = None
    corrects_line_id: UUID | None = None
    @model_validator(mode='after')
    def coherent_line(self):
        if self.kind=='labor':
            if self.technician_id is None or self.unit!='hour':raise ValueError('Labor needs stable technician and hours')
            if self.product_id or self.warehouse_id or self.material_use:raise ValueError('Labor is not material')
        elif self.kind=='material':
            if self.product_id is None or self.warehouse_id is None or self.material_use is None:raise ValueError('Material needs product, source warehouse and usage')
            if self.technician_id:raise ValueError('Record technician on labor or task, not as inventory owner')
            if self.unit=='hour':raise ValueError('Material needs explicit item unit')
        elif self.product_id or self.warehouse_id or self.material_use:raise ValueError('Task is not a stock movement')
        for rate in [self.cost,self.selling]:
            if rate and rate.basis!=('per_hour' if self.kind=='labor' else 'per_unit'):raise ValueError('Rate basis must match measured actual')
        if self.corrects_line_id==self.line_id:raise ValueError('Line cannot correct itself')
        return self

class ExecutionWorksheet(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    operation_id: UUID
    expected_revision: int = Field(ge=0)
    source_module: Literal['field_service','real_estate']
    source_id: UUID
    site_work: str = Field(min_length=1,max_length=5000)
    lines: list[ActualLine] = Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def coherent_worksheet(self):
        ids=set();corrected=set()
        for line in self.lines:
            if line.line_id in ids:raise ValueError('Duplicate actual line identity')
            if line.corrects_line_id:
                if line.corrects_line_id not in ids or line.corrects_line_id in corrected:raise ValueError('Correction must refer to one prior unsuperseded line')
                prior=next(x for x in self.lines if x.line_id==line.corrects_line_id)
                if any(getattr(prior,k)!=getattr(line,k) for k in ['kind','technician_id','product_id','warehouse_id','unit','material_use']):raise ValueError('Correction cannot silently change resource or measurement identity')
                corrected.add(line.corrects_line_id)
            ids.add(line.line_id)
        return self

def summarize(worksheet: ExecutionWorksheet, *, can_view_cost: bool, can_view_selling: bool):
    """Project authorized worksheet only. Caller validates source/line references.

    Returns are separate positive buckets. They do not reduce installed usage or
    promise stock restoration. Partial known amounts are never called totals.
    """
    corrected={x.corrects_line_id for x in worksheet.lines if x.corrects_line_id}
    active=[x for x in worksheet.lines if x.line_id not in corrected]
    result={'posting_state':{'stock':'unposted','accounting':'unposted','invoice':'not_created'},
            'operational_completion':'not_changed','active_lines':len(active),'superseded_lines':len(corrected)}
    for name,allowed in [('cost',can_view_cost),('selling',can_view_selling)]:
        if not allowed:continue
        buckets=defaultdict(Decimal);missing=0
        for line in active:
            rate=getattr(line,name)
            if rate is None:missing+=1;continue
            usage='returned' if line.material_use=='returned' else 'performed_or_used'
            # Round monetary lines once for display, not a financial-posting rule.
            amount=(line.quantity*rate.amount).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            buckets[(rate.currency,usage)]+=amount
        result[name]={'status':'incomplete' if missing else 'recorded_unposted',
                      'missing_rate_lines':missing,
                      'known_subtotals':[{'currency':currency,'usage':usage,'amount':str(amount)} for (currency,usage),amount in sorted(buckets.items())],
                      'meaning':'Recorded snapshot basis only, not posted cost or final customer charge'}
    return result
