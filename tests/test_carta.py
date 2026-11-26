import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import backup
import carta
import cash_register
import inventory
from analytics import report
from store import Store


class CartaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / 'db.sqlite')
        cash_register.mutate(self.s, 'cash_open', {'opening': '0', 'request_id': 'open-carta'}, 1)
        st = self.s.state()
        self.p = {p['name']: p for p in st['products']}
        self.cat = {c['name']: c['id'] for c in st['categories']}
        self.center = {c['name']: c['id'] for c in st['centers']}
        self.tables = st['tables']
        self.n = 0

    def admin(self, action, **data):
        return carta.mutate(self.s, action, data, 1, 'admin')

    def open(self, name):
        table = next(t for t in self.tables if t['name'] == name)
        return self.s.mutate('open', {'table_id': table['id']}, 1)['order_id']

    def pay(self, oid):
        self.n += 1
        o = self.s.receipt(oid)
        self.s.mutate('pay', dict(order_id=oid, expected_total=o['total'], payment='card', request_id=f'c-pay-{self.n}'), 1)

    def test_tariffs_by_center_time_and_category(self):
        self.admin('tariff_save', name='terraza', percent='10', centers=[self.center['TERRAZA']], priority=5)
        self.admin('tariff_save', name='happy', percent='-20', start_time='00:00', end_time='23:59', categories=[self.cat['REFRESCOS']], priority=1)
        with self.assertRaises(ValueError):
            self.admin('tariff_save', name='mal', percent='5', start_time='25:00', end_time='26:00')
        inside = self.open('T1')
        lid = self.s.mutate('add', {'order_id': inside, 'format_id': self.p['CROQUETAS']['formats'][0]['id']}, 1)['line_id']
        line = next(l for l in self.s.receipt(inside)['lines'] if l['id'] == lid)
        self.assertEqual((line['price'], line['reference_price'], line['tariff']), (715, 650, 'TERRAZA'))
        sala = self.open('M1')
        lid = self.s.mutate('add', {'order_id': sala, 'format_id': self.p['COCA COLA']['formats'][0]['id']}, 1)['line_id']
        line = next(l for l in self.s.receipt(sala)['lines'] if l['id'] == lid)
        self.assertEqual((line['price'], line['tariff']), (160, 'HAPPY'))
        with self.s.db() as c:
            night = datetime(2026, 1, 1, 23, 59, 30)
            self.assertIsNone(carta.matching_tariff(c, sala, self.cat['CAFÉS'], night))

    def test_menu_lines_kitchen_cancel_and_report(self):
        menu = self.s.mutate('product', {'name': 'MENÚ', 'category_id': self.cat['BRASA Y COCINA'], 'formats': [{'name': 'COMPLETO', 'price': '14'}]}, 1)['product_id']
        firsts = [self.p['ENSALADILLA']['id'], self.p['TOMATE AL CARBÓN']['id']]
        seconds = [self.p['CARRILLADA']['id']]
        with self.assertRaises(ValueError):
            self.admin('menu_save', product_id=menu, sections=[{'name': 'X', 'course': 'PRIMERO', 'options': [menu]}])
        self.admin('menu_save', product_id=menu, sections=[{'name': 'Primeros', 'course': 'PRIMERO', 'options': firsts},
                                                            {'name': 'Segundos', 'course': 'SEGUNDO', 'options': seconds}])
        fmt = next(p for p in self.s.state()['products'] if p['id'] == menu)['formats'][0]['id']
        oid = self.open('M2')
        with self.assertRaises(ValueError):
            self.s.mutate('add', {'order_id': oid, 'format_id': fmt}, 1)
        with self.assertRaises(ValueError):
            carta.mutate(self.s, 'add_menu', {'order_id': oid, 'format_id': fmt, 'choices': [seconds[0], seconds[0]]}, 1, 'tpv')
        parent = carta.mutate(self.s, 'add_menu', {'order_id': oid, 'format_id': fmt, 'choices': [firsts[1], seconds[0]]}, 1, 'tpv')['line_id']
        order = self.s.receipt(oid)
        self.assertEqual(order['total'], 1400)
        items = [l for l in order['lines'] if l['menu_role'] == 'item']
        self.assertEqual([(l['course'], l['price'], l['kitchen']) for l in items], [('PRIMERO', 0, 'new'), ('SEGUNDO', 0, 'new')])
        with self.assertRaises(ValueError):
            self.s.mutate('quantity', {'line_id': parent, 'delta': 1}, 1)
        with self.assertRaises(ValueError):
            self.s.mutate('cancel_line', {'order_id': oid, 'line_id': items[0]['id']}, 1)
        self.s.mutate('send', {'order_id': oid}, 1)
        sent = self.s.receipt(oid)['lines']
        self.assertTrue(all(l['sent_at'] for l in sent if l['menu_role'] == 'item'))
        self.s.mutate('ready', {'order_id': oid, 'prep': 'COCINA'}, 1)
        self.assertTrue(all(l['ready_at'] for l in self.s.receipt(oid)['lines'] if l['menu_role'] == 'item'))
        self.pay(oid)
        today = date.today().isoformat()
        rows = report(self.s, 'Productos en menús', today, today)['rows']
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(report(self.s, 'Tiempos de preparación', today, today)['rows']), 2)
        other = self.open('M3')
        parent = carta.mutate(self.s, 'add_menu', {'order_id': other, 'format_id': fmt, 'choices': [firsts[0], seconds[0]]}, 1, 'tpv')['line_id']
        self.s.mutate('cancel_line', {'order_id': other, 'line_id': parent, 'reason': 'test'}, 1)
        self.assertEqual(self.s.receipt(other)['lines'], [])

    def test_recipe_consumes_stock_once_and_reports_margin(self):
        inventory.mutate(self.s, 'stock_item', {'name': 'carne', 'unit': 'KG'}, 1)
        inventory.mutate(self.s, 'supplier', {'name': 'proveedor'}, 1)
        st = inventory.state(self.s)
        item, supplier = st['items'][0]['id'], st['suppliers'][0]['id']
        inventory.mutate(self.s, 'stock_move', {'kind': 'receipt', 'item_id': item, 'qty': '5', 'cost': '10', 'supplier_id': supplier, 'request_id': 'rec-1'}, 1)
        self.admin('recipe_save', product_id=self.p['CARRILLADA']['id'], format_id=None, items=[{'item_id': item, 'qty': '0,200'}])
        oid = self.open('M4')
        self.s.mutate('add', {'order_id': oid, 'format_id': self.p['CARRILLADA']['formats'][0]['id'], 'qty': 2}, 1)
        self.pay(oid)
        balance = inventory.state(self.s)['items'][0]['balance']
        self.assertEqual(balance, 5000 - 400)
        with self.s.db() as c:
            self.assertEqual(carta.consume(c, oid, 1), 0)
        today = date.today().isoformat()
        row = report(self.s, 'Rentabilidad de la carta', today, today)['rows'][0]
        self.assertEqual(row[4], 200)
        cat_rows = report(self.s, 'Márgenes por categorías', today, today)['rows']
        self.assertEqual(cat_rows[0][3], 400)

    def test_backups_create_list_prune_and_restore(self):
        first = backup.create(self.s, 'manual')['name']
        oid = self.open('M5')
        self.s.mutate('add', {'order_id': oid, 'format_id': 1}, 1)
        self.assertEqual(len(backup.listing(self.s)), 1)
        result = backup.restore(self.s, first)
        self.assertNotIn(oid, [o['id'] for o in self.s.state()['orders']])
        backup.restore(self.s, result['safety_copy'])
        self.assertIn(oid, [o['id'] for o in self.s.state()['orders']])
        with self.assertRaises(ValueError):
            backup.restore(self.s, '../db.sqlite')
        with self.assertRaises(ValueError):
            backup.save_config(self.s, {'folder': 'relativa', 'keep': 10})
        backup.save_config(self.s, {'folder': '', 'keep': 3})
        for _ in range(4):
            backup.create(self.s, 'manual')
        self.assertEqual(len(backup.listing(self.s)), 3)
        self.assertIsNone(backup.automatic(self.s))


if __name__ == '__main__':
    unittest.main()
