import tempfile
import unittest
from pathlib import Path

import global_config
import series
from store import Store


class GlobalConfigTests(unittest.TestCase):
    def test_series_assignment_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            series.initialize(store)
            identity = series.save(store, {'name': 'F', 'type': 'Factura', 'next_number': 1})['id']
            values = dict.fromkeys(global_config.SERIES_TYPES)
            values['Factura'] = identity
            global_config.save(store, {'pos_series': values})
            self.assertEqual(global_config.read(Store(store.path))['pos_series']['Factura'], identity)
            values['Pedido'] = identity
            with self.assertRaises(ValueError):
                global_config.save(store, {'pos_series': values})
            self.assertIsNone(global_config.read(store)['pos_series']['Pedido'])
