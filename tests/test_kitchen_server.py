import argparse
import tempfile
import unittest
from pathlib import Path

import cash_register
import kitchen
import server_config
from store import Store


class KitchenServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.s = Store(self.folder / 'db.sqlite')
        cash_register.mutate(self.s, 'cash_open', {'opening': '0', 'request_id': 'open-kitchen'}, 1)
        st = self.s.state()
        self.p = {p['name']: p for p in st['products']}
        self.tables = st['tables']

    def admin(self, action, **data):
        return kitchen.mutate(self.s, action, data, 1)

    def order(self, table, names):
        oid = self.s.mutate('open', {'table_id': self.tables[table]['id']}, 1)['order_id']
        for n in names:
            self.s.mutate('add', {'order_id': oid, 'format_id': self.p[n]['formats'][0]['id']}, 1)
        self.s.mutate('send', {'order_id': oid}, 1)
        return oid

    def test_prep_types_create_rename_and_protect(self):
        tid = self.admin('prep_type_save', name='fríos', color='#3366ff')['id']
        prod = self.s.mutate('product', {'name': 'GAZPACHO', 'category_id': 1, 'prep': 'FRÍOS', 'formats': [{'name': 'VASO', 'price': '4'}]}, 1)['product_id']
        with self.assertRaises(ValueError):
            self.s.mutate('product', {'name': 'X', 'category_id': 1, 'prep': 'NO EXISTE', 'formats': [{'name': 'U', 'price': '1'}]}, 1)
        mid = self.admin('monitor_save', name='Fríos', prep_types=['FRÍOS'])['id']
        self.admin('prep_type_save', id=tid, name='Fríos y ensaladas', color='#3366ff')
        with self.s.db() as c:
            self.assertEqual(c.execute('SELECT prep FROM products WHERE id=?', (prod,)).fetchone()[0], 'FRÍOS Y ENSALADAS')
            self.assertEqual(kitchen.monitor(c, mid)['prep_types'], ['FRÍOS Y ENSALADAS'])
        with self.assertRaises(ValueError):
            self.admin('prep_type_delete', id=tid)

    def test_board_ready_line_recall_and_settings(self):
        with self.s.db() as c:
            cocina = next(m for m in kitchen.monitors(c) if m['name'] == 'COCINA')
            barra = next(m for m in kitchen.monitors(c) if m['name'] == 'BARRA')
        oid = self.order(0, ['CARRILLADA', 'ENSALADILLA', 'COCA COLA'])
        board = kitchen.board(self.s, cocina['id'])
        self.assertEqual([len(o['lines']) for o in board['orders']], [2])
        self.assertEqual(len(kitchen.board(self.s, barra['id'])['orders'][0]['lines']), 1)
        line = board['orders'][0]['lines'][0]['id']
        self.assertEqual(kitchen.kds_action(self.s, 'line_ready', {'monitor_id': cocina['id'], 'line_id': line})['changed'], 1)
        self.assertEqual(kitchen.kds_action(self.s, 'ready', {'monitor_id': cocina['id'], 'order_id': oid})['changed'], 1)
        self.assertEqual(kitchen.board(self.s, cocina['id'])['orders'], [])
        self.assertEqual(len(kitchen.board(self.s, barra['id'])['orders']), 1)
        self.assertEqual(kitchen.kds_action(self.s, 'recall', {'monitor_id': cocina['id'], 'order_id': oid})['changed'], 2)
        kitchen.kds_action(self.s, 'settings', {'monitor_id': cocina['id'], 'layout': 'stack', 'volume': 35, 'sound': 'bell'})
        with self.s.db() as c:
            m = kitchen.monitor(c, cocina['id'])
        self.assertEqual((m['layout'], m['volume'], m['sound'], m['prep_types']), ('stack', 35, 'bell', ['COCINA']))
        with self.assertRaises(ValueError):
            kitchen.kds_action(self.s, 'settings', {'monitor_id': cocina['id'], 'layout': 'diagonal'})

    def test_sold_out_blocks_sales(self):
        kitchen.set_sold_out(self.s, self.p['CROQUETAS']['id'], True, 1)
        oid = self.s.mutate('open', {'direct': True}, 1)['order_id']
        with self.assertRaisesRegex(ValueError, 'AGOTADO'):
            self.s.mutate('add', {'order_id': oid, 'format_id': self.p['CROQUETAS']['formats'][0]['id']}, 1)
        kitchen.set_sold_out(self.s, self.p['CROQUETAS']['id'], False, 1)
        self.s.mutate('add', {'order_id': oid, 'format_id': self.p['CROQUETAS']['formats'][0]['id']}, 1)

    def test_close_shift_can_keep_open_accounts(self):
        oid = self.order(1, ['CARRILLADA'])
        r = cash_register.report(self.s)
        data = {'session_id': r['session_id'], 'expected_revision': r['revision'], 'counted_cash': f"{r['expected_cash'] / 100:.2f}", 'request_id': 'close-keep-1'}
        with self.assertRaises(ValueError):
            cash_register.mutate(self.s, 'cash_close', dict(data), 1)
        report = cash_register.mutate(self.s, 'cash_close', dict(data, keep_open=True), 1)['report']
        self.assertEqual([a['id'] for a in report['open_accounts']], [oid])
        self.assertEqual(report['open_accounts_due'], 1400)
        self.assertEqual(self.s.receipt(oid)['status'], 'open')
        self.assertIn('Cuentas que quedan abiertas', cash_register.text_report(report))

    def test_server_cfg_roles(self):
        args = argparse.Namespace(app='tpv', servidor=False, lan_host='0.0.0.0')
        self.assertEqual(server_config.network_port(self.folder, args, 8790), 8790)
        server_config.ensure(self.folder, 8800)
        self.assertIsNone(server_config.network_port(self.folder, args, 8790))
        self.assertEqual(server_config.network_port(self.folder, argparse.Namespace(app='tpv', servidor=True, lan_host='0.0.0.0'), None), 8800)
        self.assertEqual(server_config.summary(self.folder)['mode'], 'servidor')
        text = server_config.path(self.folder).read_text(encoding='utf-8').replace('servidor =\n', 'servidor = 192.168.1.10\n')
        server_config.path(self.folder).write_text(text, encoding='utf-8')
        self.assertEqual(server_config.client_url(self.folder), 'http://192.168.1.10:8790')
        self.assertEqual(server_config.summary(self.folder)['mode'], 'cliente')


if __name__ == '__main__':
    unittest.main()
