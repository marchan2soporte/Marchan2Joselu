import tempfile
import unittest
from pathlib import Path

import cash_register
import company
import verifactu
from store import Store


class VerifactuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / 'db.sqlite')
        cash_register.mutate(self.s, 'cash_open', {'opening': '0', 'request_id': 'open-verifactu'}, 1)
        self.n = 0

    def sale(self, fmt=1, qty=1):
        oid = self.s.mutate('open', {'direct': True}, 1)['order_id']
        self.s.mutate('add', {'order_id': oid, 'format_id': fmt, 'qty': qty}, 1)
        self.n += 1
        o = self.s.receipt(oid)
        self.s.mutate('pay', dict(order_id=oid, expected_total=o['total'], payment='card', request_id=f'vf-payment-{self.n}'), 1)
        return oid

    def test_aeat_published_fingerprint_example(self):
        digest = verifactu.fingerprint('89890001K', '12345678/G33', '01-01-2024', 'F1', 1235, 12345, '', '2024-01-01T19:20:30+01:00')
        self.assertEqual(digest, '3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60')

    def test_disabled_or_without_nif_records_nothing(self):
        self.sale()
        self.assertEqual(verifactu.status(self.s)['count'], 0)
        verifactu.set_enabled(self.s, True)
        self.sale()
        self.assertEqual(verifactu.status(self.s)['count'], 0)

    def test_chain_breakdown_and_tamper_detection(self):
        company.save(self.s, {'legal_name': 'BAR PRUEBA SL', 'tax_id': 'B12345678'})
        verifactu.set_enabled(self.s, True)
        self.sale(qty=2)
        self.sale(fmt=13)
        st = verifactu.status(self.s)
        self.assertEqual(st['count'], 2)
        self.assertTrue(st['chain']['ok'])
        first, second = sorted(st['records'], key=lambda r: r['id'])
        self.assertEqual(first['previous_hash'], '')
        self.assertEqual(second['previous_hash'], first['hash'])
        self.assertEqual(sum(b['total'] for b in first['breakdown']), first['total'])
        self.assertEqual(first['tax_total'], first['total'] - first['breakdown'][0]['base'])
        self.assertIn('prewww2.aeat.es', first['qr_test_url'])
        with self.s.db() as c:
            c.execute('UPDATE verifactu_records SET total=total+1 WHERE id=?', (first['id'],))
        self.assertFalse(verifactu.status(self.s)['chain']['ok'])


if __name__ == '__main__':
    unittest.main()
