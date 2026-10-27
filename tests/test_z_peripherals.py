from helpers import open_test_cash
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import peripherals
import pos_profiles
import z_report
from store import Store


class ZAndPeripheralTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'test.db')
        open_test_cash(self.store)

    def update_options(self, **values):
        profile = pos_profiles.active(self.store)
        profile['options'].update(values)
        pos_profiles.save(self.store, profile)

    def test_z_sections_use_real_payments_and_profile_selection(self):
        fmt = self.store.state()['products'][0]['formats'][0]['id']
        oid = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        self.store.mutate('add', {'order_id': oid, 'format_id': fmt}, actor=1)
        amount = self.store.receipt(oid)['total']
        self.store.mutate('pay', {'order_id': oid, 'expected_total': amount,
            'payment': 'card', 'request_id': 'z-test'}, actor=1)
        opts = pos_profiles.active(self.store)['options']['z_options']
        self.update_options(z_options={**opts, 'sales_by_center': False})
        report = z_report.preview(self.store)
        titles = [section['title'] for section in report['sections']]
        self.assertEqual(report['sales'], amount)
        self.assertIn('Cobros por forma de pago', titles)
        self.assertNotIn('Ventas por centro', titles)
        self.assertEqual(next(s for s in report['sections'] if s['title'] == 'Cobros por forma de pago')['rows'],
                         [['TARJETA', 1, amount]])
        self.assertIn('No ejecuta un cierre de caja', report['note'])

    def test_printer_probe_connects_only_to_local_ip(self):
        self.update_options(network_printer='192.168.1.40', printer_port=9100)
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): return False
        with patch('peripherals.socket.create_connection', return_value=Connection()) as connect:
            self.assertTrue(peripherals.printer_probe(self.store)['ok'])
            connect.assert_called_once_with(('192.168.1.40', 9100), timeout=2)
        self.update_options(network_printer='8.8.8.8')
        with self.assertRaises(ValueError): peripherals.printer_probe(self.store)

    def test_com_diagnostic_parses_text_without_touching_sales(self):
        self.update_options(scale_port='COM3', scale_baud=9600)
        class Port:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def readline(self, limit): return b'ST,GS, 1.250 kg\r\n'
        fake = types.SimpleNamespace(Serial=lambda **kwargs: Port(), SerialException=OSError)
        with patch.dict(sys.modules, {'serial': fake}):
            result = peripherals.scale_probe(self.store)
        self.assertEqual(result['weight_kg'], 1.25)
        self.assertEqual(result['port'], 'COM3')


if __name__ == '__main__': unittest.main()
