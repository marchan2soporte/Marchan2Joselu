from helpers import open_test_cash
import unittest,tempfile
from pathlib import Path
from datetime import date
from store import Store
import inventory
from analytics import dashboard,report,report_catalog

class AnalyticsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'data.db');inventory.initialize(self.store)
  open_test_cash(self.store)
 def tearDown(self):self.tmp.cleanup()
 def sale(self,when,total,method='card'):
  with self.store.db() as c:
   oid=c.execute("INSERT INTO orders(status,created,paid_at,total,created_by,table_id) VALUES('paid',?,?,?,?,1)",(when,when,total,1)).lastrowid
   c.execute("INSERT INTO lines(order_id,product_id,format_id,name,format,price,qty,tax,prep,course) VALUES(?,1,1,'PRODUCTO','UNIDAD',?,1,10,'COCINA','PRIMERO')",(oid,total))
   c.execute('INSERT INTO payments(order_id,amount,method,tendered,change_due,created,user_id) VALUES(?,?,?,?,0,?,1)',(oid,total,method,total,when))
  return oid
 def test_period_boundaries(self):
  self.sale('2026-10-23T12:00:00',1000);self.sale('2026-10-19T10:00:00',2000);self.sale('2026-10-18T10:00:00',4000);self.sale('2026-01-01T00:00:00',8000);self.sale('2025-12-31T23:59:59',16000)
  d=dashboard(self.store,date(2026,10,23));self.assertEqual([r['sales'] for r in d['cards']],[1000,3000,7000,15000])
 def test_partial_payment_is_not_a_closed_sale(self):
  oid=self.store.mutate('open',{'direct':True})['order_id'];self.store.mutate('add',{'order_id':oid,'format_id':1})
  with self.store.db() as c:c.execute("INSERT INTO payments(order_id,amount,method,tendered,change_due,created,user_id) VALUES(?,100,'card',100,0,'2026-10-23T12:00:00',1)",(oid,))
  d=dashboard(self.store,date(2026,10,23));self.assertEqual(d['cards'][0]['sales'],0);self.assertEqual(d['cards'][0]['collected'],100);self.assertEqual(d['pending'],350)
  r=report(self.store,'Formas de pago','2026-10-23','2026-10-23');self.assertEqual(r['rows'],[['TARJETA',1,100]])
 def test_end_inclusive_and_next_day_excluded(self):
  self.sale('2026-10-23T23:59:59',999);self.sale('2026-10-24T00:00:00',777)
  r=report(self.store,'Ventas diarias','2026-10-23','2026-10-23');self.assertEqual(r['rows'],[['2026-10-23',999]])
 def test_all_available_reports_and_tax_reconciliation(self):
  self.sale('2026-10-23T12:00:00',101)
  for entry in report_catalog():
   result=report(self.store,entry['id'],'2026-10-23','2026-10-23')
   self.assertEqual(result['available'],entry['available'])
   if not entry['available']:self.assertEqual(result['rows'],[]);self.assertTrue(result['note'])
  r=report(self.store,'Resumen de impuestos','2026-10-23','2026-10-23')['rows'][0];self.assertEqual(r[1]+r[2],r[3]);self.assertEqual(r[3],101)
 def test_comparison_and_zero_days(self):
  self.sale('2025-10-23T12:00:00',333)
  r=report(self.store,'Comparativa interanual','2026-10-22','2026-10-23');self.assertEqual(r['rows'],[['2026-10-22',0,'2025-10-22',0],['2026-10-23',0,'2025-10-23',333]])
 def test_invalid_ranges_and_ids(self):
  for start,end in [('2026-10-24','2026-10-23'),('invalid','2026-10-23'),('2000-01-01','2026-01-01')]:
   with self.assertRaises(ValueError):report(self.store,'Ventas diarias',start,end)
  with self.assertRaises(ValueError):report(self.store,'unknown','2026-10-23','2026-10-23')

if __name__=='__main__':unittest.main()
