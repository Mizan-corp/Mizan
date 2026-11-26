"""Printable pages of the reports, built with the print system's helpers. Every text that comes from
the workspace (store, branch, category and product names, units) is escaped with `h()`."""
from app.platform.printing.routes import ar_egp, ar_num, h, wrap
from app.platform.tenancy import clock


def inventory_html(data: dict) -> str:
    with_cost = data["with_cost"]
    store = data["store"]
    now = clock.now()
    cols = 6 if with_cost else 5
    rows, current = [], None
    for idx, item in enumerate(data["items"], 1):
        if item["category"] != current:
            current = item["category"]
            rows.append(f'<tr style="background:#1e3a5f"><td colspan="{cols}" style="color:white;font-weight:700;'
                        f'padding:8px 14px;font-size:12px">{h(current)}</td></tr>')
        qty = item["qty"]
        value = item["cost_value"] if with_cost else item["retail_value"]
        cost_cell = f'<td style="text-align:center">{ar_egp(item["cost_price"])}</td>' if with_cost else ""
        rows.append(f"""<tr>
          <td style="color:#9ca3af;font-size:11px;text-align:center">{idx}</td>
          <td><div class="td-name">{h(item['name'])}</div><div style="font-size:10px;color:#9ca3af">{h(item['subcategory'])}</div></td>
          <td style="text-align:center">{ar_num(qty, 3 if qty % 1 else 0)} {h(item['unit'])}</td>
          {cost_cell}
          <td style="text-align:center">{ar_egp(item['retail_price'])}</td>
          <td style="text-align:left;{'color:#dc2626' if qty <= 0 else 'color:#1e3a5f'};font-weight:700">{ar_egp(value)}</td>
        </tr>""")
    summary = data["summary"]
    cost_meta = (f'<div class="meta-cell"><div class="m-lbl">قيمة التكلفة</div><div class="m-val">'
                 f'{ar_egp(summary["total_cost_value"])}</div></div>') if with_cost else ""
    cost_head = '<th style="text-align:center;width:100px">سعر التكلفة</th>' if with_cost else ""
    total = summary["total_cost_value"] if with_cost else summary["total_retail_value"]
    title = f"تقرير المخزون — {data['warehouse']}"
    body = f"""
<div class="top-band"><div class="brand"><div class="brand-text"><div class="co-name">{h(store.get('name') or 'Mizan')}</div>
<div class="co-sub">{h(store.get('address'))}</div></div></div>
<div class="doc-id"><div class="doc-type">{h(title)}</div><div class="doc-num">INV-RPT-{now.strftime('%Y%m%d')}</div>
<div class="doc-date">{now.strftime('%d / %m / %Y')}</div></div></div><div class="ribbon"></div>
<div class="body">
  <div class="meta-row">
    <div class="meta-cell"><div class="m-lbl">الفرع</div><div class="m-val">{h(data['warehouse'])}</div></div>
    <div class="meta-cell"><div class="m-lbl">عدد الأصناف</div><div class="m-val">{ar_num(summary['total_products'], 0)}</div></div>
    {cost_meta}
    <div class="meta-cell"><div class="m-lbl">قيمة البيع</div><div class="m-val">{ar_egp(summary['total_retail_value'])}</div></div>
  </div>
  <div class="tbl-label">بيان الأصناف</div>
  <table>
    <thead><tr>
      <th style="width:36px;text-align:center">#</th><th>الصنف</th><th style="text-align:center;width:90px">الكمية</th>
      {cost_head}<th style="text-align:center;width:100px">سعر البيع</th>
      <th style="text-align:left;width:120px">{'القيمة بالتكلفة' if with_cost else 'القيمة بسعر البيع'}</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot><tr style="background:#f1f5f9;font-weight:700">
      <td colspan="{cols - 1}" style="padding:10px 14px">الإجمالي</td>
      <td style="text-align:left;padding:10px 14px;font-weight:900">{ar_egp(total)}</td>
    </tr></tfoot>
  </table>
  <div class="no-print" style="margin-top:16px;text-align:center"><button onclick="window.print()">طباعة</button></div>
</div>
<div style="border-top:2px solid #94a3b8;padding:10px 36px;background:#f8fafc;font-size:10px;color:#6b7280">
  طُبع: {now.strftime('%Y/%m/%d  %H:%M')} — {h(store.get('name'))}
</div>"""
    return wrap(body, title)
