import tempfile
import unittest
from pathlib import Path

import ticket_templates
from store import Store


class TicketTemplateTests(unittest.TestCase):
    def test_default_selection_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            ticket_templates.initialize(store)
            first = ticket_templates.save(store, {'name': 'Principal', 'base': '80 mm',
                'header': 'Mi local', 'footer': 'Gracias', 'show_time': True,
                'show_user': True, 'show_tax': True, 'is_default': True})['id']
            second = ticket_templates.save(store, {'name': 'A4', 'base': 'A4',
                'header': '', 'footer': '', 'show_time': False,
                'show_user': False, 'show_tax': False, 'is_default': True})['id']
            self.assertEqual(ticket_templates.current(Store(store.path))['id'], second)
            self.assertEqual(sum(x['is_default'] for x in ticket_templates.list_all(store)), 1)
            ticket_templates.delete(store, {'id': second})
            self.assertIsNone(ticket_templates.current(store))
            self.assertEqual(ticket_templates.list_all(store)[0]['id'], first)

    def test_invalid_template_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            ticket_templates.initialize(store)
            with self.assertRaises(ValueError):
                ticket_templates.save(store, {'name': 'X', 'base': 'inventado'})
            self.assertEqual(ticket_templates.list_all(store), [])
