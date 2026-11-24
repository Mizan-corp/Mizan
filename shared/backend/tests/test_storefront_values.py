"""Typed display values never imply a sale, public grant or network request."""
import importlib.util,sys,unittest
from decimal import Decimal
from test_storefront_runtime import r,A,ROOT
spec=importlib.util.spec_from_file_location('values',ROOT/'app/framework/storefront_values.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class ValuesTests(unittest.TestCase):
 def test_exact_money_and_unambiguous_display(self):
  self.assertEqual(v.money_value(Decimal('12.5'),'EGP'),{'schema':v.MONEY_SCHEMA,'amount':'12.50','currency':'EGP'});self.assertEqual(v.money_text(v.money_value('0','USD')),'0.00 USD')
 def test_no_float_rounding_fx_or_unknown_currency(self):
  for amount,currency in [(1.2,'EGP'),(True,'EGP'),('1.001','EGP'),('-1','EGP'),('NaN','EGP'),('Infinity','USD'),('10000000000','EGP'),('1','EGP<script>'),('1',{}),({},'EGP')]:
   with self.assertRaises(r.ProjectionInvalid):v.money_value(amount,currency)
  with self.assertRaises(r.ProjectionInvalid):v.check_money({'schema':v.MONEY_SCHEMA,'amount':'1','currency':'EGP'})
  with self.assertRaises(r.ProjectionInvalid):v.check_money({**v.money_value('1','EGP'),'tax_included':True})
 def test_tenant_owned_storage_shapes(self):
  for url in [f'/uploads/t/{A}/product_image/test-1.png',f'https://abc.public.blob.vercel-storage.com/t/{A}/product_image/test-2.webp']:
   self.assertEqual(v.check_media(v.media_value(url,'Product',A),A)['src'],url)
 def test_unsafe_or_private_media_refused(self):
  urls=['javascript:alert(1)','data:image/png;base64,abc','https://attacker.invalid/item.png',f'https://abc.public.blob.vercel-storage.com/private/t/{A}/product_image/x.png',f'/uploads/t/{A}/clinical/x.png',f'/uploads/t/{A}/product_image/../x.png',f'/uploads/t/{A}/product_image/%2e%2e.png',f'https://abc.public.blob.vercel-storage.com:bad/t/{A}/product_image/x.png',f'https://u:p@abc.public.blob.vercel-storage.com/t/{A}/product_image/x.png',f'/uploads/t/{A}/product_image/x.svg',f'/uploads/t/{A}/product_image/x.png?token=secret',f'/uploads/t/{A}/product_image/x.png#fragment']
  for url in urls:
   with self.subTest(url=url),self.assertRaises(r.ProjectionInvalid):v.media_value(url,'Product',A)
  with self.assertRaises(r.ProjectionInvalid):v.check_media({'schema':v.MEDIA_SCHEMA,'src':f'/uploads/t/{A}/product_image/x.png','alt':'Name','token':'secret'},A)
if __name__=='__main__':unittest.main()
