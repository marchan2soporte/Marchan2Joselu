from helpers import open_test_cash
import unittest,tempfile
from pathlib import Path
from store import Store
import inventory

class InventoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'x.db');inventory.initialize(self.store)
  open_test_cash(self.store)
  inventory.mutate(self.store,'supplier',{'name':'Proveedor'},1);inventory.mutate(self.store,'stock_item',{'name':'Harina','unit':'KG'},1)
 def tearDown(self):self.tmp.cleanup()
 def move(self,**kwargs):
  data=dict(item_id=1,supplier_id=1,qty='1,250',cost='2,40',kind='receipt',reference='ALB1',request_id='test1');data.update(kwargs)
  return inventory.mutate(self.store,'stock_move',data,1)
 def test_fractional_receipts_and_waste(self):
  self.move();self.move(kind='waste',qty='.250',request_id='test2')
  data=inventory.state(self.store);self.assertEqual(data['items'][0]['balance'],1000);self.assertEqual(data['moves'][0]['total'],-60)
 def test_invalid_and_duplicate_are_atomic(self):
  self.move()
  for values in [dict(request_id='test1'),dict(qty='100',kind='out',request_id='test2'),dict(qty='0.0001',request_id='test2'),dict(qty='NaN',request_id='test2'),dict(supplier_id=999,request_id='test2')]:
   with self.assertRaises(Exception):self.move(**values)
  self.assertEqual(len(inventory.state(self.store)['moves']),1)
 def test_report_stock_asof(self):
  self.move()
  r=inventory.report(self.store,'Stock por producto','2020-01-01','2020-01-01');self.assertEqual(r['rows'][0][2],0)
  r=inventory.report(self.store,'Stock por producto','2020-01-01','2029-01-01');self.assertEqual(r['rows'][0][2],1.25)

if __name__=='__main__':unittest.main()
