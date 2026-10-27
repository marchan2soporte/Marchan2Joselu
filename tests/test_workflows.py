from helpers import open_test_cash
import tempfile
from pathlib import Path
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from store import Store,LegacyStore


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db.sqlite';self.s=Store(self.path)
        open_test_cash(self.s)
        self.oid=self.s.mutate('open',{'table_id':1},1)['order_id']
        self.products=self.s.state()['products']

    def tearDown(self):self.tmp.cleanup()

    def add(self,name='JHONNY NEGRO',qty=1):
        p=next(p for p in self.products if p['name']==name)
        return self.s.mutate('add',dict(order_id=self.oid,format_id=p['formats'][0]['id'],qty=qty),1)['line_id']

    def pay(self,**kw):
        o=self.s.receipt(self.oid)
        return self.s.mutate('pay',dict(order_id=self.oid,expected_total=o['total'],expected_due=o['due'],payment='card',**kw),1)

    def test_explicit_direct_sale_required(self):
        with self.assertRaises(ValueError):self.s.mutate('open',{},1)
        self.assertTrue(self.s.mutate('open',{'direct':True},1)['order_id'])

    def test_prepare_all_march_only_selected(self):
        a=self.add();b=self.add('JAMÓN')
        self.s.mutate('march',dict(order_id=self.oid,line_ids=[a]),1)
        self.assertEqual([l['kitchen'] for l in self.s.receipt(self.oid)['lines']],['pending','new'])
        self.s.mutate('send',dict(order_id=self.oid),1)
        self.assertEqual([l['kitchen'] for l in self.s.receipt(self.oid)['lines']],['pending','pending'])
        self.s.mutate('march',dict(order_id=self.oid,line_ids=[a]),1)
        self.assertEqual(len(self.s.receipt(self.oid)['lines']),2)

    def test_selected_course_and_note_and_foreign_line(self):
        a=self.add();b=self.add('JAMÓN')
        self.s.mutate('course',dict(order_id=self.oid,line_ids=[b],course='SEGUNDO'),1)
        self.s.mutate('note',dict(order_id=self.oid,line_ids=[b],note='SIN SAL'),1)
        rows=self.s.receipt(self.oid)['lines'];self.assertEqual(rows[0]['course'],'BEBIDAS');self.assertEqual((rows[1]['course'],rows[1]['note']),('SEGUNDO','SIN SAL'))
        other=self.s.mutate('open',{'table_id':2},1)['order_id']
        with self.assertRaises(ValueError):self.s.mutate('march',dict(order_id=other,line_ids=[a]),1)

    def test_quick_add_merges_unprepared_but_not_prepared(self):
        a=self.add();b=self.add();self.assertEqual(a,b)
        self.assertEqual(self.s.receipt(self.oid)['lines'][0]['qty'],2)
        self.s.mutate('march',dict(order_id=self.oid,line_ids=[a]),1)
        self.assertNotEqual(self.add(),a)

    def test_concurrent_fast_adds_preserved(self):
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(lambda _:self.add(),range(15)))
        o=self.s.receipt(self.oid);self.assertEqual(len(o['lines']),1);self.assertEqual(o['lines'][0]['qty'],15);self.assertEqual(o['total'],13500)

    def test_move_preserves_identity_and_blocks_occupied(self):
        a=self.add();self.s.mutate('move',dict(order_id=self.oid,table_id=2),1)
        o=self.s.receipt(self.oid);self.assertEqual(o['table_id'],2);self.assertEqual(o['lines'][0]['id'],a)
        self.s.mutate('open',{'table_id':3},1)
        with self.assertRaises(ValueError):self.s.mutate('move',dict(order_id=self.oid,table_id=3),1)
        self.assertEqual(self.s.receipt(self.oid)['table_id'],2)

    def test_split_products_qty_and_payment_atomicity(self):
        a=self.add(qty=3);b=self.add('JAMÓN')
        original=self.s.receipt(self.oid)
        data=dict(order_id=self.oid,expected_total=4700,expected_amount=1800,lines=[dict(id=a,qty=2)],payment='cash',tendered='10',request_id='split-one')
        with self.assertRaises(ValueError):self.s.mutate('split_pay',data,1)
        self.assertEqual(self.s.receipt(self.oid),original)
        r=self.s.mutate('split_pay',dict(data,tendered='20'),1)
        self.assertEqual(r['receipt']['status'],'paid');self.assertEqual(r['change'],200)
        source=self.s.receipt(self.oid);self.assertEqual(source['total'],2900);self.assertEqual(source['lines'][0]['qty'],1)
        self.assertEqual(r['receipt']['parent_id'],self.oid);self.assertEqual(source['total']+r['receipt']['total'],4700)

    def test_split_paid_pending_kitchen_quantities_conserved(self):
        a=self.add(qty=3);self.s.mutate('send',dict(order_id=self.oid),1)
        self.s.mutate('split_pay',dict(order_id=self.oid,expected_total=2700,expected_amount=900,lines=[dict(id=a,qty=1)],payment='card'),1)
        self.assertEqual(sum(l['qty'] for o in self.s.preparation() for l in o['lines']),3)

    def test_equal_amounts_rounding_and_mixed_payments(self):
        a=self.add('FLAN DE CAFÉ')
        self.pay(amount=117,request_id='part1');self.pay(amount=117,request_id='part2')
        o=self.s.receipt(self.oid);self.assertEqual(o['due'],116);self.assertEqual(o['status'],'open')
        with self.assertRaises(ValueError):self.s.mutate('quantity',dict(line_id=a,qty=0),1)
        r=self.s.mutate('pay',dict(order_id=self.oid,expected_total=350,expected_due=116,payment='cash',tendered='2',request_id='part3'),1)
        self.assertEqual(r['change'],84);self.assertEqual(r['receipt']['payment'],'mixed');self.assertEqual(r['receipt']['due'],0)
        stats=self.s.state()['stats'];self.assertEqual((stats['revenue'],stats['cash'],stats['card']),(350,116,234))

    def test_stale_partial_and_duplicate_request_rejected(self):
        self.add();data=dict(order_id=self.oid,expected_total=900,expected_due=900,amount=300,payment='card',request_id='abc')
        self.s.mutate('pay',data,1)
        with self.assertRaises(ValueError):self.s.mutate('pay',data,1)
        with self.assertRaises(sqlite3.IntegrityError):self.s.mutate('pay',dict(data,expected_due=600),1)
        self.assertEqual(self.s.receipt(self.oid)['paid'],300)

    def test_user_pin_roles_last_admin_and_audit(self):
        self.assertEqual(self.s.authenticate(1,'1234')['role'],'admin')
        with self.assertRaises(ValueError):self.s.authenticate(1,'0000')
        self.s.mutate('user',dict(name='ANA',pin='4567',role='staff'),1)
        ana=next(u for u in self.s.users() if u['name']=='ANA')
        self.assertNotIn('pin_hash',ana);self.assertEqual(self.s.authenticate(ana['id'],'4567')['role'],'staff')
        with self.assertRaises(ValueError):self.s.mutate('user',dict(name='OTRO',pin='8888'),ana['id'])
        with self.assertRaises(ValueError):self.s.mutate('user',dict(id=1,name='ADMIN',role='staff'),1)
        self.s.mutate('user_disable',dict(id=ana['id']),1)
        with self.assertRaises(ValueError):self.s.authenticate(ana['id'],'4567')
        with self.s.db() as c:self.assertEqual(c.execute("SELECT user_id FROM audit WHERE action='open'").fetchone()[0],1)


class MigrationTests(unittest.TestCase):
    def test_v01_data_preserved_and_backed_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'marchan2.db';old=LegacyStore(path)
            with old.db() as c:
                pid=c.execute('SELECT id FROM products LIMIT 1').fetchone()[0]
                c.execute("INSERT INTO orders(table_id,status,created,paid_at,payment,total,tendered,change_due) VALUES(1,'paid',?,?,'cash',350,500,150)",(datetime.now().isoformat(),datetime.now().isoformat()))
                c.execute("INSERT INTO lines(order_id,product_id,format_id,name,format,price,qty,tax,prep,course) VALUES(1,?,1,'HISTÓRICO','UNIDAD',350,1,10,'COCINA','PRIMERO')",(pid,))
            new=Store(path);receipt=new.receipt(1)
            self.assertEqual((receipt['total'],receipt['paid'],receipt['due']),(350,350,0))
            self.assertEqual(receipt['lines'][0]['name'],'HISTÓRICO')
            self.assertEqual(len(list(Path(tmp).glob('marchan2-antes-v02-*.db'))),1)
            Store(path);self.assertEqual(len(new.receipt(1)['payments']),1)


if __name__=='__main__':unittest.main()
