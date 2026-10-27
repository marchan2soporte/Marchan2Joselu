from helpers import open_test_cash
import tempfile
import unittest
from pathlib import Path

import pos_profiles
import ticket_templates
from store import Store


class PosProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'test.db')
        open_test_cash(self.store)
        ticket_templates.initialize(self.store)

    def test_profiles_persist_and_guard_active_deletion(self):
        first = pos_profiles.active(self.store)
        self.assertEqual(first['name'], 'TPV principal')
        created = pos_profiles.save(self.store, {'name': 'Barra', 'group_name': 'Servicio',
            'options': {'allow_pay': False, 'network_printer': '192.168.1.40', 'scale_port': 'COM3'}})['id']
        pos_profiles.activate(self.store, {'id': created})
        self.assertFalse(pos_profiles.active(Store(self.store.path))['options']['allow_pay'])
        with self.assertRaises(ValueError):
            pos_profiles.delete(self.store, {'id': created})
        pos_profiles.activate(self.store, {'id': first['id']})
        pos_profiles.delete(self.store, {'id': created})
        self.assertEqual(len(pos_profiles.list_all(self.store)), 1)

    def test_active_profile_controls_payment_and_preparation(self):
        profile = pos_profiles.active(self.store)
        opts = {**profile['options'], 'allow_pay': False, 'auto_prepare': True}
        pos_profiles.save(self.store, {**profile, 'options': opts})
        order = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        fmt = self.store.state()['products'][0]['formats'][0]['id']
        line = self.store.mutate('add', {'order_id': order, 'format_id': fmt}, actor=1)['line_id']
        with self.store.db() as c:
            self.assertEqual(c.execute('SELECT kitchen FROM lines WHERE id=?', (line,)).fetchone()[0], 'pending')
        with self.store.db() as c:
            total = self.store.order(c, order)['total']
        with self.assertRaisesRegex(ValueError, 'desactivados'):
            self.store.mutate('pay', {'order_id': order, 'expected_total': total,
                'payment': 'cash', 'tendered': '100'}, actor=1)
        self.assertEqual(self.store.state()['orders'][0]['due'], total)

    def test_invalid_device_and_template_do_not_change_profile(self):
        profile = pos_profiles.active(self.store)
        for options in ({'scale_port': 'USB0'}, {'receipt_template_id': 999}, {'allow_pay': 'yes'}):
            with self.assertRaises(ValueError):
                pos_profiles.save(self.store, {**profile, 'options': {**profile['options'], **options}})
        self.assertEqual(pos_profiles.active(self.store), profile)


if __name__ == '__main__':
    unittest.main()
