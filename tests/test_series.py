import tempfile
import unittest
from pathlib import Path

import series
from store import Store


class SeriesTests(unittest.TestCase):
    def test_create_edit_delete_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            series.initialize(store)
            self.assertEqual(series.list_all(store), [])
            identity = series.save(store, {'name': 'F2026', 'type': 'Factura',
                                           'next_number': '7', 'active': True})['id']
            series.save(store, {'id': identity, 'name': 'F2027', 'type': 'Factura',
                                'next_number': '8', 'active': False})
            self.assertEqual(series.list_all(Store(store.path))[0]['name'], 'F2027')
            self.assertEqual(series.list_all(store)[0]['next_number'], 8)
            series.delete(store, {'id': identity})
            self.assertEqual(series.list_all(store), [])

    def test_invalid_input_and_duplicate_do_not_change_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            series.initialize(store)
            series.save(store, {'name': 'F', 'type': 'Factura', 'next_number': 1})
            for data in ({'name': 'X', 'type': 'inventado', 'next_number': 1},
                         {'name': 'X', 'type': 'Factura', 'next_number': 0},
                         {'name': 'X', 'type': 'Factura', 'next_number': '1.5'}):
                with self.assertRaises(ValueError):
                    series.save(store, data)
            self.assertEqual(len(series.list_all(store)), 1)
