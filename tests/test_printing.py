import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import printing
from store import Store


class PrintingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'test.db')
        self.profile = self.store.state()
        with self.store.db() as c:
            self.profile_id = c.execute('SELECT id FROM pos_profiles WHERE active=1').fetchone()[0]

    def route(self, prep, center_ids=None):
        return printing.save_kitchen(self.store, {'profile_id': self.profile_id,
            'name': prep, 'printer_name': 'Cola Windows Cocina',
            'prep_types': [prep], 'center_ids': center_ids or []})['id']

    def test_preparation_routes_and_no_duplicate_on_resend(self):
        self.route('COCINA', [1])
        self.route('BARRA', [2])
        kitchen = next(p for p in self.profile['products'] if p['prep'] == 'COCINA')
        bar = next(p for p in self.profile['products'] if p['prep'] == 'BARRA')
        order = self.store.mutate('open', {'table_id': 1}, actor=1)['order_id']
        for product in (kitchen, bar):
            self.store.mutate('add', {'order_id': order, 'format_id': product['formats'][0]['id']}, actor=1)
        self.store.mutate('send', {'order_id': order}, actor=1)
        jobs = printing.jobs(self.store)
        self.assertEqual(len(jobs), 1)
        with self.store.db() as c:
            self.assertIn(kitchen['name'], c.execute('SELECT payload FROM print_jobs').fetchone()[0])
        self.store.mutate('send', {'order_id': order}, actor=1)
        self.assertEqual(len(printing.jobs(self.store)), 1)

    def test_failed_job_preserved_then_retried(self):
        self.route('COCINA')
        product = next(p for p in self.profile['products'] if p['prep'] == 'COCINA')
        order = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        self.store.mutate('add', {'order_id': order, 'format_id': product['formats'][0]['id']}, actor=1)
        self.store.mutate('send', {'order_id': order}, actor=1)
        job_id = printing.jobs(self.store)[0]['id']
        with patch('printing.print_text', side_effect=ValueError('Cola desconectada')):
            self.assertIn('Cola desconectada', printing.dispatch(self.store, [job_id])[0])
        self.assertEqual(printing.jobs(self.store)[0]['status'], 'error')
        self.assertEqual(self.store.receipt(order)['status'], 'open')
        with patch('printing.print_text') as printed:
            self.assertEqual(printing.dispatch(self.store, [job_id]), [])
            printed.assert_called_once()
        self.assertEqual(printing.jobs(self.store)[0]['status'], 'sent')

    def test_one_kitchen_slip_groups_lines_for_same_route(self):
        route_id = self.route('BARRA')
        products = [p for p in self.profile['products'] if p['prep'] == 'BARRA'][:2]
        self.assertEqual(len(products), 2)
        order = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        for product in products:
            self.store.mutate('add', {'order_id': order, 'format_id': product['formats'][0]['id']}, actor=1)
        self.store.mutate('send', {'order_id': order}, actor=1)
        with self.store.db() as c:
            jobs = c.execute("SELECT id,payload FROM print_jobs WHERE kind='kitchen'").fetchall()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM print_job_lines WHERE route_id=?',
                                       (route_id,)).fetchone()[0], 2)
            for product in products: self.assertIn(product['name'], jobs[0]['payload'])
            self.assertIn('COMANDA INTERNA', jobs[0]['payload'])
            self.assertNotIn('EUR', jobs[0]['payload'])
        self.store.mutate('send', {'order_id': order}, actor=1)
        self.assertEqual(len(printing.jobs(self.store)), 1)

    def test_document_destination_and_automatic_receipt_once(self):
        printing.save_document(self.store, {'profile_id': self.profile_id,
            'kind': 'receipt', 'printer_name': 'Cola Windows Ticket', 'copies': 2,
            'print_mode': 'always'})
        product = self.profile['products'][0]
        order = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        self.store.mutate('add', {'order_id': order, 'format_id': product['formats'][0]['id']}, actor=1)
        amount = self.store.receipt(order)['total']
        self.store.mutate('pay', {'order_id': order, 'expected_total': amount,
            'payment': 'card', 'request_id': 'print-test'}, actor=1)
        self.assertTrue(printing.enqueue_receipt(self.store, order, automatic=True)['configured'])
        self.assertTrue(printing.enqueue_receipt(self.store, order, automatic=True)['duplicate'])
        job = printing.jobs(self.store)[0]
        with self.store.db() as c:
            self.assertEqual(c.execute('SELECT copies FROM print_jobs WHERE id=?', (job['id'],)).fetchone()[0], 2)

    def test_generic_text_driver_uses_raw_and_graphic_driver_uses_gdi(self):
        with patch('printing.sys.platform', 'win32'), patch('printing._printer_driver', return_value='Generic / Text Only'), \
             patch('printing.print_raw') as raw, patch('printing.print_gdi') as gdi:
            printing.print_text('Concod', 'Línea', 2)
            raw.assert_called_once_with('Concod', 'Línea', 2, 48, 4, 'none')
            gdi.assert_not_called()
        with patch('printing.sys.platform', 'win32'), patch('printing._printer_driver', return_value='Vendor Graphics'), \
             patch('printing.print_raw') as raw, patch('printing.print_gdi') as gdi:
            printing.print_text('Otra', 'Ticket', 1)
            gdi.assert_called_once_with('Otra', 'Ticket', 1)
            raw.assert_not_called()
        self.assertEqual(printing._raw_bytes('España\nTotal'),
                         b'Espa\xa4a\r\nTotal\r\n\r\n\r\n\r\n\r\n')
        cut = printing._raw_bytes('1234567890\n' + '-' * 48, 32, 2, 'partial')
        self.assertIn(b'1234567890\r\n', cut)
        self.assertIn(b'-' * 32 + b'\r\n', cut)
        self.assertTrue(cut.endswith(b'\r\n\r\n\r\n\x1d\x56\x01'))

    def test_selected_backend_is_kept_for_ticket_z_and_kitchen(self):
        for kind in ('receipt', 'z_report'):
            printing.save_document(self.store, {'profile_id': self.profile_id,
                'kind': kind, 'printer_name': 'Concod', 'copies': 1, 'backend': 'raw'})
        with patch('printing.installed_printers', return_value=['Concod']):
            self.assertEqual(printing.configuration(self.store, self.profile_id)['documents']['receipt']['backend'], 'raw')
        self.route('COCINA')
        order = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        self.assertTrue(printing.enqueue_receipt(self.store, order)['configured'])
        self.assertTrue(printing.enqueue_text(self.store, 'z_report', 'Z de prueba')['configured'])
        with self.store.db() as c:
            backends = [row[0] for row in c.execute('SELECT backend FROM print_jobs ORDER BY id')]
        self.assertEqual(backends, ['raw', 'raw'])

    def test_paper_settings_follow_job_and_validate_limits(self):
        printing.save_document(self.store, {'profile_id': self.profile_id, 'kind': 'receipt',
            'printer_name': 'Concod', 'copies': 1, 'backend': 'raw',
            'raw_columns': 48, 'feed_lines': 5, 'cut_mode': 'partial'})
        order = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        job_id = printing.enqueue_receipt(self.store, order)['job_id']
        with self.store.db() as c:
            job = c.execute('SELECT raw_columns,feed_lines,cut_mode FROM print_jobs WHERE id=?',
                            (job_id,)).fetchone()
        self.assertEqual(tuple(job), (48, 5, 'partial'))
        with self.assertRaises(ValueError):
            printing.save_document(self.store, {'profile_id': self.profile_id, 'kind': 'receipt',
                'printer_name': 'Concod', 'copies': 1, 'raw_columns': 100})

    def test_text_only_ticket_respects_selected_template(self):
        order = self.store.mutate('open', {'direct': True}, actor=1)['order_id']
        product = self.profile['products'][0]
        self.store.mutate('add', {'order_id': order, 'format_id': product['formats'][0]['id']}, actor=1)
        with self.store.db() as c:
            snapshot = self.store.order(c, order)
        template = {'base': '56 mm · 32 caracteres', 'header': 'MI CABECERA',
                    'footer': 'MI PIE', 'show_order_id': 0, 'show_location': 0,
                    'show_time': 0, 'show_tax': 0, 'show_unpaid': 1}
        text = printing._format_receipt(snapshot, {'tax_id': 'B123'}, template)
        self.assertIn('MI CABECERA', text)
        self.assertIn('MI PIE', text)
        self.assertIn('PENDIENTE DE COBRO', text)
        self.assertNotIn('Cuenta #', text)
        self.assertNotIn('VENTA DIRECTA', text)
        self.assertIn('B123', text)
        self.assertIn('JUSTIFICANTE DE VENTA', text)
        self.assertIn('DOCUMENTO DE PRUEBA', text)
        self.assertIn('UDS  PRODUCTO', text)
        self.assertNotIn('FACTURA SIMPLIFICADA', text)


if __name__ == '__main__': unittest.main()
