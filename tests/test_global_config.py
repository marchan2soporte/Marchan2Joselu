from helpers import open_test_cash
import tempfile
import unittest
from pathlib import Path

import global_config
import daily_close
import series
import ticket_templates
from store import Store


class GlobalConfigTests(unittest.TestCase):
    def test_command_template_selection_and_daily_summary_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            open_test_cash(store)
            series.initialize(store)
            ticket_templates.initialize(store)
            template_id = ticket_templates.save(store, {'name': 'Comanda interna', 'base': '80 mm',
                'header': 'COCINA', 'footer': 'Preparar', 'show_time': True,
                'show_user': True, 'show_tax': False, 'is_default': False})['id']
            config = global_config.read(store)
            config['preferences']['command_template'] = str(template_id)
            config['preferences']['include_center_sales'] = True
            config['preferences']['include_pending'] = True
            global_config.save(store, config)
            self.assertEqual(global_config.read(store)['preferences']['command_template'], str(template_id))
            order_id = store.mutate('open', {'direct': True})['order_id']
            summary = daily_close.preview(store)
            self.assertEqual(summary['sales'], 0)
            self.assertEqual([section['title'] for section in summary['sections']],
                             ['Ventas por centro', 'Cuentas pendientes ahora'])
            self.assertEqual(summary['sections'][1]['rows'][0][0], order_id)
            config['preferences']['command_template'] = '99999'
            with self.assertRaises(ValueError):
                global_config.save(store, config)

    def test_series_assignment_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            open_test_cash(store)
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

    def test_preferences_are_saved_and_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            open_test_cash(store)
            series.initialize(store)
            payload = global_config.read(store)
            payload['preferences']['stock_warning'] = True
            payload['preferences']['service_charge_percent'] = '2.5'
            global_config.save(store, payload)
            saved = global_config.read(Store(store.path))
            self.assertTrue(saved['preferences']['stock_warning'])
            self.assertEqual(saved['preferences']['service_charge_percent'], '2.5')
            payload['preferences']['service_charge_percent'] = '200'
            with self.assertRaises(ValueError):
                global_config.save(store, payload)
            self.assertEqual(global_config.read(store), saved)

    def test_consolidation_setting_changes_tpv_line_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            open_test_cash(store)
            series.initialize(store)
            order_id = store.mutate('open', {'direct': True})['order_id']
            product = next(p for p in store.state()['products'] if p['formats'])
            format_id = product['formats'][0]['id']
            store.mutate('add', {'order_id': order_id, 'format_id': format_id})
            store.mutate('add', {'order_id': order_id, 'format_id': format_id})
            self.assertEqual(len(store.state()['orders'][0]['lines']), 1)
            settings = global_config.read(store)
            settings['preferences']['consolidate_lines'] = False
            global_config.save(store, settings)
            store.mutate('add', {'order_id': order_id, 'format_id': format_id})
            self.assertEqual(len(store.state()['orders'][0]['lines']), 2)

    def test_prepared_line_requires_reason_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            open_test_cash(store)
            series.initialize(store)
            settings = global_config.read(store)
            settings['preferences']['cancel_reason'] = True
            global_config.save(store, settings)
            order_id = store.mutate('open', {'direct': True})['order_id']
            format_id = store.state()['products'][0]['formats'][0]['id']
            store.mutate('add', {'order_id': order_id, 'format_id': format_id})
            line_id = store.state()['orders'][0]['lines'][0]['id']
            store.mutate('send', {'order_id': order_id})
            with self.assertRaises(ValueError):
                store.mutate('cancel_line', {'order_id': order_id, 'line_id': line_id})
            store.mutate('cancel_line', {'order_id': order_id, 'line_id': line_id,
                                         'reason': 'Cliente cambia pedido'})
            self.assertEqual(store.state()['orders'][0]['lines'], [])
            with store.db() as c:
                self.assertEqual(c.execute('SELECT reason FROM line_cancellations').fetchone()[0],
                                 'Cliente cambia pedido')

    def test_paid_test_receipts_get_unique_internal_series_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            open_test_cash(store)
            series.initialize(store)
            identity = series.save(store, {'name': 'T', 'type': 'Fra. Simp.',
                                           'next_number': 12})['id']
            settings = global_config.read(store)
            settings['pos_series']['Fra. Simp.'] = identity
            global_config.save(store, settings)
            format_id = store.state()['products'][0]['formats'][0]['id']
            numbers = []
            for index in range(2):
                order_id = store.mutate('open', {'direct': True}, actor=1)['order_id']
                store.mutate('add', {'order_id': order_id, 'format_id': format_id}, actor=1)
                order = store.state()['orders'][0]
                result = store.mutate('pay', {'order_id': order_id,
                    'expected_total': order['total'], 'expected_due': order['due'],
                    'payment': 'card', 'request_id': str(index)}, actor=1)
                numbers.append(result['receipt']['series_number'])
            self.assertEqual(numbers, [12, 13])
            self.assertEqual(series.list_all(store)[0]['next_number'], 14)

    def test_tip_is_recorded_separately_from_sale_and_close_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.db')
            open_test_cash(store)
            series.initialize(store)
            settings = global_config.read(store)
            settings['preferences']['include_tips'] = True
            global_config.save(store, settings)
            order_id = store.mutate('open', {'direct': True})['order_id']
            format_id = store.state()['products'][0]['formats'][0]['id']
            store.mutate('add', {'order_id': order_id, 'format_id': format_id})
            order = store.receipt(order_id)
            result = store.mutate('pay', {'order_id': order_id,
                'expected_total': order['total'], 'expected_due': order['due'],
                'payment': 'cash', 'tendered': str((order['total'] + 150) / 100),
                'tip': '1.50', 'request_id': 'tip-test'})
            self.assertEqual(result['receipt']['total'], order['total'])
            self.assertEqual(result['receipt']['payments'][0]['tip'], 150)
            self.assertEqual(result['change'], 0)
            summary = daily_close.preview(store)
            self.assertEqual(summary['sales'], order['total'])
            self.assertEqual(summary['sections'][0]['rows'], [['EFECTIVO', 150]])
