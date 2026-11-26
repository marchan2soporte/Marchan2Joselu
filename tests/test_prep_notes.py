import tempfile
import unittest
from pathlib import Path

import hospitality
from store import Store


class PrepNotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / 'db.sqlite')

    def notes(self):
        return hospitality.extend_state(self.s, self.s.state(), 1)['prep_notes']

    def test_defaults_save_clean_and_permissions(self):
        self.assertIn('SIN CEBOLLA', self.notes())
        saved = hospitality.mutate(self.s, 'prep_notes_save', {'notes': [' sin  picante ', 'SIN PICANTE', '', 'al punto']}, 1, 'admin')
        self.assertEqual(saved['notes'], ['SIN PICANTE', 'AL PUNTO'])
        self.assertEqual(self.notes(), ['SIN PICANTE', 'AL PUNTO'])
        with self.assertRaises(ValueError):
            hospitality.mutate(self.s, 'prep_notes_save', {'notes': ['x'] * 41}, 1, 'admin')
        with self.assertRaises(ValueError):
            hospitality.mutate(self.s, 'prep_notes_save', {'notes': ['x' * 41]}, 1, 'admin')
        with self.assertRaises(PermissionError):
            hospitality.mutate(self.s, 'prep_notes_save', {'notes': []}, 1, 'tpv')


if __name__ == '__main__':
    unittest.main()
