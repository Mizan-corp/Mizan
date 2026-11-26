"""Contract tests only, no persistence/API/stock/accounting/UI claim."""
import importlib.util,sys,unittest
from pathlib import Path
from uuid import uuid4
s=importlib.util.spec_from_file_location('actuals_contract',Path(__file__).resolve().parents[1]/'app/activities/general/modules/helpdesk/actuals_contract.py');c=importlib.util.module_from_spec(s);sys.modules[s.name]=c;s.loader.exec_module(c)
class ActualsTests(unittest.TestCase):
 def rate(self,amount='12.5000',currency='EGP',basis='per_hour'):
  return dict(amount=amount,currency=currency,basis=basis,provenance='Explicit isolated test rate, not payroll policy')
 def labor(self,**kw):return dict(line_id=str(uuid4()),performed_on='2026-11-24',kind='labor',description='Inspection and repair',technician_id=str(uuid4()),quantity='1.500',unit='hour',**kw)
 def material(self,**kw):return dict(line_id=str(uuid4()),performed_on='2026-11-24',kind='material',description='Installed replacement',product_id=str(uuid4()),warehouse_id=str(uuid4()),quantity='2.000',unit='piece',material_use='installed',**kw)
 def sheet(self,lines):return c.ExecutionWorksheet(operation_id=uuid4(),expected_revision=0,source_module='real_estate',source_id=uuid4(),site_work='Site execution record',lines=lines)
 def summary(self,lines):return c.summarize(self.sheet(lines),can_view_cost=True,can_view_selling=True)
 def test_unknown_is_not_zero(self):
  out=self.summary([self.labor(),self.material()]);self.assertEqual(out['cost']['missing_rate_lines'],2);self.assertEqual(out['cost']['known_subtotals'],[]);self.assertEqual(out['cost']['status'],'incomplete')
 def test_exact_separate_basis_and_currency(self):
  out=self.summary([self.labor(cost=self.rate(),selling=self.rate('40')),self.material(cost=self.rate('2.3456','USD','per_unit'))]);self.assertEqual(out['cost']['known_subtotals'],[{'currency':'EGP','usage':'performed_or_used','amount':'18.75'},{'currency':'USD','usage':'performed_or_used','amount':'4.69'}]);self.assertEqual(out['selling']['known_subtotals'][0]['amount'],'60.00');self.assertEqual(out['selling']['missing_rate_lines'],1)
 def test_explicit_zero_valid_with_provenance(self):
  self.assertEqual(self.summary([self.labor(cost=self.rate('0'))])['cost']['status'],'recorded_unposted')
 def test_references_positive_bounded_and_no_effect_fields(self):
  for patch in [{'quantity':'-1'},{'quantity':'0'},{'quantity':'1.0001'},{'quantity':'NaN'},{'technician_id':None},{'unit':'piece'},{'stock_posted':True},{'tenant_id':str(uuid4())}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):self.sheet([{**self.labor(),**patch}])
  for patch in [{'product_id':None},{'warehouse_id':None},{'material_use':None},{'cost':self.rate(basis='per_hour')}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):self.sheet([{**self.material(),**patch}])
 def test_return_not_automatic_credit_or_stock(self):
  material=self.material(cost=self.rate('10',basis='per_unit'));returned={**self.material(cost=self.rate('10',basis='per_unit')),'material_use':'returned'};out=self.summary([material,returned]);self.assertEqual([x['amount'] for x in out['cost']['known_subtotals']],['20.00','20.00']);self.assertEqual(out['posting_state'],{'stock':'unposted','accounting':'unposted','invoice':'not_created'})
 def test_corrections_preserve_original_and_prevent_double_count(self):
  a=self.labor(cost=self.rate());b={**a,'line_id':str(uuid4()),'quantity':'2','corrects_line_id':a['line_id']};out=self.summary([a,b]);self.assertEqual(out['active_lines'],1);self.assertEqual(out['superseded_lines'],1);self.assertEqual(out['cost']['known_subtotals'][0]['amount'],'25.00');self.assertEqual(a['quantity'],'1.500')
  for lines in [[a,a],[b,a],[a,b,{**self.labor(),'corrects_line_id':a['line_id']}],[a,{**self.material(),'corrects_line_id':a['line_id']}]]:
   with self.assertRaises(ValueError):self.sheet(lines)
 def test_cost_visibility_is_independent_from_execution_and_selling(self):
  out=c.summarize(self.sheet([self.labor(cost=self.rate(),selling=self.rate('50'))]),can_view_cost=False,can_view_selling=True);self.assertNotIn('cost',out);self.assertIn('selling',out)
 def test_bad_rates_and_missing_provenance(self):
  for patch in [{'amount':'-1'},{'amount':'Infinity'},{'amount':'0.00001'},{'currency':'XXX'},{'provenance':''},{'provenance':'  '},{'basis':'per_unit'}]:
   with self.assertRaises(ValueError):self.sheet([self.labor(cost={**self.rate(),**patch})])
 def test_never_reports_completion_or_posted_final_price(self):
  out=self.summary([self.labor(cost=self.rate(),selling=self.rate())]);self.assertEqual(out['operational_completion'],'not_changed');self.assertEqual(out['cost']['status'],'recorded_unposted');self.assertNotIn('total',out);self.assertNotIn('profit',out)
if __name__=='__main__':unittest.main()
