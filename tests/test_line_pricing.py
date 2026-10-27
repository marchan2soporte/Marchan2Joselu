import tempfile,unittest
from pathlib import Path
from store import Store
import cash_register,line_pricing,permissions,button_layout,printing

class LinePricingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.s=Store(Path(self.tmp.name)/'db.sqlite');self.n=0
  cash_register.mutate(self.s,'cash_open',{'opening':'100','request_id':'open-pricing-test'},1)
  self.oid=self.s.mutate('open',{'direct':True},1)['order_id']
 def key(self):self.n+=1;return 'pricing-request-'+str(self.n)
 def add(self,qty=1):return self.s.mutate('add',{'order_id':self.oid,'format_id':1,'qty':qty},1)['line_id']
 def price(self,lid,kind='percent',value='10',action='line_discount',**extra):
  l=next(l for l in self.s.receipt(self.oid)['lines'] if l['id']==lid)
  data=dict(line_id=lid,kind=kind,value=value,expected_revision=l['pricing_revision'],expected_price=l['price'],expected_qty=l['qty'],request_id=self.key());data.update(extra)
  return line_pricing.mutate(self.s,action,data,1)
 def line(self,lid):return next(l for l in self.s.receipt(self.oid)['lines'] if l['id']==lid)
 def weighted(self,price='20',extras=''):
  pid=self.s.mutate('product',{'name':'PRODUCTO PESADO','category_id':1,'weighed':True,'addon_group':extras,'formats':[{'name':'KILO','price':price}]},1)['product_id']
  return next(p for p in self.s.state()['products'] if p['id']==pid)
 def test_percent_amount_and_clear_use_original_unit_price(self):
  lid=self.add(3);self.price(lid);self.assertEqual(self.line(lid)['price'],405);self.assertEqual(self.s.receipt(self.oid)['total'],1215)
  self.price(lid,value='20');self.assertEqual(self.line(lid)['price'],360)
  self.price(lid,kind='amount',value='.50');self.assertEqual(self.line(lid)['price'],400)
  self.price(lid,kind='clear',value='0');self.assertEqual(self.line(lid)['price'],450)
 def test_reject_excess_discount_partial_payment_and_stale_price(self):
  lid=self.add()
  for kind,value in [('percent','101'),('percent','NaN'),('percent','10.001'),('amount','5'),('amount','-1')]:
   with self.assertRaises(ValueError):self.price(lid,kind=kind,value=value)
  self.price(lid)
  with self.assertRaises(ValueError):self.price(lid,value='20',expected_revision=0)
  o=self.s.receipt(self.oid);self.s.mutate('pay',dict(order_id=self.oid,expected_total=o['total'],payment='card',amount=100,request_id=self.key()),1)
  with self.assertRaises(ValueError):self.price(lid)
 def test_weighted_portion_rounding_discounts_and_cash_are_exact(self):
  p=self.weighted('18.99');lid=self.s.mutate('add',{'order_id':self.oid,'format_id':p['formats'][0]['id'],'weight':'.250'},1)['line_id']
  self.assertEqual(self.line(lid)['price'],475);self.assertEqual(self.line(lid)['weight_label'],'0,250 KG')
  self.price(lid,value='10');self.assertEqual(self.line(lid)['price'],428)
  self.price(lid,value='.500',action='line_weight');self.assertEqual(self.line(lid)['base_price'],950);self.assertEqual(self.line(lid)['price'],855)
  self.price(lid,kind='clear');self.assertEqual(self.line(lid)['price'],950)
  o=self.s.receipt(self.oid);self.s.mutate('pay',dict(order_id=self.oid,expected_total=o['total'],payment='cash',tendered='10',request_id=self.key()),1)
  self.assertEqual(cash_register.report(self.s)['expected_cash'],10950)
 def test_weight_requires_enabled_product_valid_precision_and_not_prepared(self):
  lid=self.add()
  with self.assertRaises(ValueError):self.price(lid,value='.5',action='line_weight')
  p=self.weighted();fmt=p['formats'][0]['id']
  for value in [None,'0','-.1','NaN','.0001','1001']:
   with self.assertRaises(ValueError):self.s.mutate('add',dict(order_id=self.oid,format_id=fmt,weight=value),1)
  lid=self.s.mutate('add',dict(order_id=self.oid,format_id=fmt,weight='.5'),1)['line_id']
  with self.assertRaises(ValueError):self.s.mutate('quantity',{'line_id':lid,'qty':2},1)
  self.s.mutate('march',{'order_id':self.oid,'line_ids':[lid]},1)
  with self.assertRaises(ValueError):self.price(lid,value='.7',action='line_weight')
  self.price(lid,value='10');self.assertEqual(self.line(lid)['price'],900)
 def test_discounted_split_preserves_metadata_and_add_does_not_merge(self):
  lid=self.add(3);self.price(lid);second=self.add();self.assertNotEqual(lid,second)
  order=self.s.receipt(self.oid)
  child=self.s.mutate('split_pay',{'order_id':self.oid,'expected_total':order['total'],'expected_amount':405,'payment':'card','lines':[{'id':lid,'qty':1}],'request_id':self.key()},1)['receipt']
  self.assertEqual(child['lines'][0]['base_price'],450);self.assertEqual(child['lines'][0]['discount_label'],'DTO 10,00 %');self.assertEqual(child['total'],405)
  self.assertEqual(self.line(lid)['qty'],2)
 def test_weighted_extras_are_per_portion_and_kitchen_has_no_price(self):
  p=self.weighted('20','REFRESCOS');extra=next(e for e in self.s.state()['extras'] if e['name']=='RED BULL')
  lid=self.s.mutate('add',dict(order_id=self.oid,format_id=p['formats'][0]['id'],weight='.25',extras=[extra['id']]),1)['line_id']
  self.assertEqual(self.line(lid)['price'],600)
  order=self.s.receipt(self.oid);text=printing._format_kitchen(order,order['lines'],'COCINA')
  self.assertIn('0,250 KG',text);self.assertNotIn('EUR',text);self.assertNotIn('20,00',text)
 def test_calculator_visibility_is_per_profile_and_requires_bool(self):
  d=button_layout.read(self.s);d['calculator_enabled']=False;button_layout.save(self.s,d,1)
  self.assertFalse(button_layout.read(self.s)['calculator_enabled'])
  d=button_layout.read(self.s);d['calculator_enabled']='false'
  with self.assertRaises(ValueError):button_layout.save(self.s,d,1)
 def test_custom_profile_cannot_discount_and_audit_is_idempotent(self):
  lid=self.add();profile=permissions.save(self.s,{'name':'Solo tomar pedidos','permissions':['ticket_open','ticket_add']})['id']
  self.s.mutate('user',{'name':'ANA','pin':'1234','role':'staff','profile_id':profile},1);uid=next(u['id'] for u in self.s.users() if u['name']=='ANA')
  l=self.line(lid);data=dict(line_id=lid,kind='percent',value='10',expected_revision=0,expected_price=l['price'],expected_qty=1,request_id=self.key())
  with self.assertRaises(PermissionError):line_pricing.mutate(self.s,'line_discount',data,uid)
  line_pricing.mutate(self.s,'line_discount',data,1);line_pricing.mutate(self.s,'line_discount',data,1)
  with self.s.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM line_pricing_changes').fetchone()[0],1)

if __name__=='__main__':unittest.main()
