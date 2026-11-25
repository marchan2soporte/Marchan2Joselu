import tempfile
import unittest
from datetime import date
from pathlib import Path

import button_layout
import cash_register
import hospitality
import permissions
from analytics import report, report_catalog
from store import Store


class HospitalityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / 'db.sqlite')
        cash_register.mutate(self.s, 'cash_open', {'opening': '0', 'request_id': 'open-hospitality'}, 1)
        tables = self.s.state()['tables']
        self.oid = self.s.mutate('open', {'table_id': tables[0]['id']}, 1)['order_id']
        self.other = self.s.mutate('open', {'table_id': tables[1]['id']}, 1)['order_id']
        self.n = 0

    def do(self, action, app='tpv', **data):
        return hospitality.mutate(self.s, action, data, 1, app)

    def add(self, oid, fmt=1, qty=1):
        return self.s.mutate('add', {'order_id': oid, 'format_id': fmt, 'qty': qty}, 1)['line_id']

    def pay(self, oid):
        self.n += 1
        o = self.s.receipt(oid)
        self.s.mutate('pay', dict(order_id=oid, expected_total=o['total'], payment='card', request_id=f'h-pay-{self.n}'), 1)

    def test_guests_customer_service_and_reports(self):
        self.do('order_guests', order_id=self.oid, guests=4)
        cid = self.do('customer_save', name='ana garcía', phone='600', allergens=['gluten'], vip=True)['customer_id']
        self.do('order_customer', order_id=self.oid, customer_id=cid)
        with self.assertRaises(ValueError):
            self.do('order_service', order_id=self.oid, service_type='domicilio', address='')
        self.do('order_service', order_id=self.oid, service_type='llevar')
        self.add(self.oid, qty=2)
        self.pay(self.oid)
        order = self.s.receipt(self.oid)
        self.assertEqual((order['guests'], order['customer_id'], order['service_type']), (4, cid, 'llevar'))
        today = date.today().isoformat()
        guests = report(self.s, 'Comensales por centro de venta', today, today)['rows']
        self.assertEqual(guests[0][2], 4)
        sales = report(self.s, 'Ventas a cliente', today, today)['rows']
        self.assertEqual(sales[0][0], 'ANA GARCÍA')
        data = hospitality.extend_state(self.s, self.s.state(), 1)
        self.assertEqual(data['customers'][0]['visits'], 1)
        self.assertEqual(data['customers'][0]['allergens'], ['gluten'])
        with self.assertRaises(ValueError):
            self.do('customer_save', name='x', email='no-es-email')

    def test_invitation_and_ticket_discount(self):
        a = self.add(self.oid, qty=2)
        self.add(self.oid, fmt=2)
        with self.assertRaises(ValueError):
            self.do('invite', order_id=self.oid, line_ids=[a], reason='')
        self.do('invite', order_id=self.oid, line_ids=[a], reason='Cortesía')
        line = next(l for l in self.s.receipt(self.oid)['lines'] if l['id'] == a)
        self.assertEqual((line['price'], line['discount_label']), (0, 'INVITACIÓN'))
        before = self.s.receipt(self.oid)['total']
        self.do('ticket_discount', order_id=self.oid, kind='percent', value='10')
        after = self.s.receipt(self.oid)
        self.assertEqual(after['total'], (before * 9000 + 5000) // 10000)
        self.assertEqual(next(l for l in after['lines'] if l['id'] == a)['price'], 0)
        self.do('ticket_discount', order_id=self.oid, kind='clear')
        self.assertEqual(self.s.receipt(self.oid)['total'], before)
        today = date.today().isoformat()
        rows = report(self.s, 'Invitaciones', today, today)['rows']
        self.assertEqual(rows[0][5], 'Cortesía')
        with self.assertRaises(ValueError):
            self.do('ticket_discount', order_id=self.oid, kind='percent', value='120')

    def test_merge_clock_layout_and_permissions(self):
        self.add(self.oid)
        self.add(self.other, qty=3)
        self.do('order_guests', order_id=self.other, guests=2)
        self.do('merge', order_id=self.oid, source_order_id=self.other)
        merged = self.s.receipt(self.oid)
        self.assertEqual(sum(l['qty'] for l in merged['lines']), 4)
        self.assertEqual(merged['guests'], 2)
        self.assertEqual(self.s.receipt(self.other)['status'], 'void')
        self.assertTrue(self.do('clock', kind='in')['working'])
        with self.assertRaises(ValueError):
            self.do('clock', kind='in')
        self.assertFalse(self.do('clock', kind='out')['working'])
        table = self.s.state()['tables'][0]['id']
        self.do('table_layout', app='admin', tables=[{'id': table, 'x': 40, 'y': 60, 'shape': 'round', 'seats': 6}])
        with self.assertRaises(ValueError):
            self.do('table_layout', app='admin', tables=[{'id': table, 'x': 140, 'y': 0}])
        with self.assertRaises(PermissionError):
            self.do('table_layout', tables=[])
        self.assertIn('ticket_invite', permissions.ALL)
        self.assertNotIn('ticket_invite', permissions.WAITER)
        layout = button_layout.read(self.s)['layout']
        self.assertIn('invite', layout['right'] + layout['others'])
        available = {r['id'] for r in report_catalog() if r['available']}
        self.assertTrue(hospitality.REPORTS <= available)


if __name__ == '__main__':
    unittest.main()
