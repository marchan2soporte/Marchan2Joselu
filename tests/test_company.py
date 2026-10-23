import tempfile
import unittest
from pathlib import Path

import company
from store import Store


class CompanyTests(unittest.TestCase):
    def test_profile_persists_and_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.db'
            store = Store(path)
            self.assertEqual(company.read(store), dict.fromkeys(company.FIELDS, ''))
            values = dict.fromkeys(company.FIELDS, 'Prueba ñ & "')
            values['email'] = 'contacto@example.com'
            values['postal_code'] = '01001'
            company.save(store, values)
            self.assertEqual(company.read(Store(path)), values)
            company.save(store, {})
            self.assertEqual(company.read(store), dict.fromkeys(company.FIELDS, ''))

    def test_invalid_update_preserves_saved_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            saved = company.save(store, {'legal_name': 'Empresa'})
            for invalid in ({'email': 'invalid'}, {'phone': []}, {'legal_name': 'a' * 161}):
                with self.assertRaises(ValueError):
                    company.save(store, invalid)
                self.assertEqual(company.read(store), saved)
