import tempfile
import unittest
from pathlib import Path

import ticket_templates
import pos_profiles
from store import Store


class TicketTemplateTests(unittest.TestCase):
    def test_save_can_apply_design_to_active_tpv(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            ticket_templates.initialize(store)
            identity = ticket_templates.save(store, {'name': 'Mi ticket', 'base': '80 mm',
                'header': 'MI LOCAL', 'footer': 'Hasta pronto', 'show_time': True,
                'show_user': True, 'show_tax': True, 'is_default': False,
                'apply_to_active_profile': True})['id']
            self.assertEqual(pos_profiles.active(store)['options']['receipt_template_id'], identity)
            self.assertIsNone(ticket_templates.current(store))

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

    def test_paper_formats_and_print_options_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            ticket_templates.initialize(store)
            data = {'name': 'Barra 56', 'base': '56 mm · 32 caracteres',
                    'header': 'BAR', 'footer': 'Gracias', 'show_time': False,
                    'show_user': True, 'show_tax': False, 'show_notes': True,
                    'show_unit_price': True, 'line_order': 'Nombre', 'is_default': True,
                    'header_image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2+pXcAAAAASUVORK5CYII='}
            identity = ticket_templates.save(store, data)['id']
            ticket_templates.initialize(store)
            saved = ticket_templates.current(store)
            self.assertEqual(saved['id'], identity)
            self.assertEqual(saved['base'], data['base'])
            self.assertEqual(saved['show_notes'], 1)
            self.assertEqual(saved['show_unit_price'], 1)
            self.assertEqual(saved['line_order'], 'Nombre')
            self.assertEqual(saved['header_image'], data['header_image'])
            data['line_order'] = 'Inexistente'
            with self.assertRaises(ValueError):
                ticket_templates.save(store, data)
            self.assertEqual(ticket_templates.current(store), saved)
            data['line_order'] = 'Nombre'
            data['header_image'] = 'data:image/svg+xml;base64,PHN2Zz4='
            with self.assertRaises(ValueError):
                ticket_templates.save(store, data)
            self.assertEqual(ticket_templates.current(store), saved)
