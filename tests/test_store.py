from helpers import open_test_cash
import unittest
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from store import Store, money


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'test.db'
        self.store=Store(self.path)
        open_test_cash(self.store)
        self.catalog=self.store.state()

    def tearDown(self):self.temp.cleanup()

    def product(self,name):return next(p for p in self.catalog['products'] if p['name']==name)

    def open(self):return self.store.mutate('open',{'table_id':1})['order_id']

    def add(self,oid,name='JHONNY NEGRO',fmt='COPA',extras=None):
        p=self.product(name);f=next(f for f in p['formats'] if f['name']==fmt)
        self.store.mutate('add',dict(order_id=oid,format_id=f['id'],extras=extras or []))

    def test_single_product_multiple_formats(self):
        p=self.product('JHONNY NEGRO')
        self.assertEqual([(f['name'],f['price']) for f in p['formats']],[('COPA',900),('BOTELLA',12000)])

    def test_addon_prices_from_database(self):
        oid=self.open();red=next(e for e in self.catalog['extras'] if e['name']=='RED BULL')
        self.add(oid,extras=[red['id']]);self.assertEqual(self.store.receipt(oid)['total'],1000)
        with self.assertRaises(ValueError):self.add(oid,extras=[red['id'],red['id']])
        bread=next(e for e in self.catalog['extras'] if e['group_name']=='TIPO PAN')
        with self.assertRaises(ValueError):self.add(oid,extras=[bread['id']])

    def test_cash_payment_and_persistence(self):
        oid=self.open();self.add(oid)
        r=self.store.mutate('pay',dict(order_id=oid,expected_total=900,payment='cash',tendered='10'))['receipt']
        self.assertEqual(r['change_due'],100)
        s=Store(self.path).state();self.assertFalse(s['orders']);self.assertEqual(s['stats']['revenue'],900)
        self.assertNotEqual(self.open(),oid)

    def test_payment_rejects_stale_total_and_insufficient_cash(self):
        oid=self.open();self.add(oid)
        for total,cash in [(100,10),(900,5)]:
            with self.assertRaises(ValueError):self.store.mutate('pay',dict(order_id=oid,expected_total=total,payment='cash',tendered=cash))
        self.assertEqual(self.store.receipt(oid)['status'],'open')

    def test_double_payment_and_closed_mutation_blocked(self):
        oid=self.open();self.add(oid)
        pay=dict(order_id=oid,expected_total=900,payment='card')
        self.store.mutate('pay',pay)
        with self.assertRaises(ValueError):self.store.mutate('pay',pay)
        with self.assertRaises(ValueError):self.add(oid)

    def test_sent_lines_immutable_and_paid_kitchen_visible(self):
        oid=self.open();self.add(oid)
        self.store.mutate('send',dict(order_id=oid))
        line=self.store.receipt(oid)['lines'][0]
        with self.assertRaises(ValueError):self.store.mutate('quantity',dict(line_id=line['id'],qty=0))
        self.store.mutate('pay',dict(order_id=oid,expected_total=900,payment='card'))
        self.assertEqual(len(self.store.preparation()),1)
        self.store.mutate('ready',dict(order_id=oid,prep='BARRA'))
        self.assertEqual(self.store.preparation(),[])

    def test_catalog_edit_preserves_sale_snapshot(self):
        oid=self.open();self.add(oid);p=self.product('JHONNY NEGRO')
        self.store.mutate('product',dict(id=p['id'],name='JHONNY NUEVO',category_id=p['category_id'],tax=21,prep='BARRA',course='BEBIDAS',formats=[dict(name='COPA',price=12)]))
        sale=self.store.receipt(oid)['lines'][0]
        self.assertEqual((sale['name'],sale['price'],sale['tax']),('JHONNY NEGRO',900,10))

    def test_duplicate_format_rolls_back_product_edit(self):
        p=self.product('JHONNY NEGRO')
        with self.assertRaises(ValueError):self.store.mutate('product',dict(id=p['id'],name='CAMBIO',category_id=p['category_id'],formats=[dict(name='COPA',price=2),dict(name='copa',price=3)]))
        self.assertEqual(self.store.state()['products'],self.catalog['products'])

    def test_concurrent_table_open_returns_single_order(self):
        with ThreadPoolExecutor(max_workers=4) as pool:ids=list(pool.map(lambda _:self.open(),range(12)))
        self.assertEqual(len(set(ids)),1)

    def test_decimal_validation_and_rounding(self):
        self.assertEqual(money('3,50'),350);self.assertEqual(money('2.205'),221)
        for value in ('NaN','Infinity','-1','x'):
            with self.assertRaises(ValueError):money(value)

    def test_automatic_table_range(self):
        self.store.mutate('center',dict(name='porche',prefix='p',start=3,end=6))
        state=self.store.state();cid=next(c['id'] for c in state['centers'] if c['name']=='PORCHE')
        self.assertEqual([t['name'] for t in state['tables'] if t['center_id']==cid],['P3','P4','P5','P6'])


if __name__=='__main__':unittest.main()
